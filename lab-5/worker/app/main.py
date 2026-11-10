"""worker: операции из очереди -> расчёт -> БД -> событие в fanout -> ack."""
import asyncio
import json
import logging
import pathlib
import signal

import aio_pika
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from . import config
from .domain import parse_operation
from .models import Base
from .repository import process_operation

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s worker: %(message)s")
log = logging.getLogger("worker")


async def retry(what: str, func, delay: float = 2.0, attempts: int = 60):
    for attempt in range(1, attempts + 1):
        try:
            return await func()
        except Exception as exc:  # noqa: BLE001
            log.warning("%s: попытка %d/%d не удалась: %s", what, attempt, attempts, exc)
            await asyncio.sleep(delay)
    raise RuntimeError(f"{what}: недоступно")


async def declare_topology(channel: aio_pika.abc.AbstractChannel):
    """Объявляем всё ДО начала обработки: события не должны теряться, пока нет подписчиков."""
    ops_exchange = await channel.declare_exchange(
        config.OPERATIONS_EXCHANGE, aio_pika.ExchangeType.DIRECT, durable=True)
    ops_queue = await channel.declare_queue(
        config.OPERATIONS_QUEUE, durable=True, arguments={"x-queue-type": "quorum"})
    await ops_queue.bind(ops_exchange, routing_key=config.OPERATIONS_KEY)

    events_exchange = await channel.declare_exchange(
        config.EVENTS_EXCHANGE, aio_pika.ExchangeType.FANOUT, durable=True)
    for name in config.EVENT_QUEUES:
        queue = await channel.declare_queue(
            name, durable=True, arguments={"x-queue-type": "quorum"})
        await queue.bind(events_exchange)
    return ops_queue, events_exchange


async def publish_event(exchange: aio_pika.abc.AbstractExchange, event: dict) -> None:
    message = aio_pika.Message(
        body=json.dumps(event, ensure_ascii=False).encode("utf-8"),
        content_type="application/json",
        message_id=event["operation_id"],
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
    )
    # publisher confirms: await вернётся после подтверждения брокером;
    # mandatory + on_return_raises: ошибка, если событие не попало ни в одну очередь
    await exchange.publish(message, routing_key="", mandatory=True)


async def handle_message(message: aio_pika.abc.AbstractIncomingMessage, sessionmaker, events_exchange):
    try:
        op = parse_operation(json.loads(message.body.decode("utf-8")))
    except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
        # «ядовитое» сообщение: повторять бессмысленно
        log.error("некорректное сообщение %s отброшено: %s", message.message_id, exc)
        await message.reject(requeue=False)
        return

    delay = 1.0
    while True:   # сбой БД/брокера: сообщение остаётся неподтверждённым, пробуем снова
        try:
            event = await process_operation(sessionmaker, op)   # транзакция зафиксирована
            await publish_event(events_exchange, event)         # брокер подтвердил публикацию
            break
        except Exception as exc:  # noqa: BLE001
            log.error("операция %s: %s; повтор через %.0f с", op.operation_id, exc, delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 15)

    try:
        await message.ack()   # ack — только после коммита и подтверждения публикации события
    except Exception as exc:  # noqa: BLE001
        # канал оборвался: сообщение придёт повторно, process_operation идемпотентна
        log.warning("ack %s не удался: %s", op.operation_id, exc)
        return
    log.info("операция %s: %s, %+d баллов, баланс %d", op.operation_id,
             event["status"], event["points_delta"], event["balance_after"])


async def consume(ops_queue, sessionmaker, events_exchange):
    async with ops_queue.iterator() as messages:
        async for message in messages:
            await handle_message(message, sessionmaker, events_exchange)


async def main():
    engine = create_async_engine(config.DATABASE_URL, pool_pre_ping=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async def create_tables():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    await retry("создание таблиц", create_tables)
    log.info("таблицы готовы")

    connection = await retry("подключение к RabbitMQ", lambda: aio_pika.connect_robust(config.RABBITMQ_URL))
    async with connection:
        channel = await connection.channel(publisher_confirms=True, on_return_raises=True)
        await channel.set_qos(prefetch_count=1)
        ops_queue, events_exchange = await declare_topology(channel)

        pathlib.Path(config.READY_FILE).touch()
        log.info("worker готов, жду операции")

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        task = asyncio.create_task(consume(ops_queue, sessionmaker, events_exchange))
        stopper = asyncio.create_task(stop.wait())
        await asyncio.wait({task, stopper}, return_when=asyncio.FIRST_COMPLETED)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
