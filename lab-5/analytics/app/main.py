"""analytics: события из analytics.events -> статистика по магазинам (в памяти)."""
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

import aio_pika
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s analytics: %(message)s")
log = logging.getLogger("analytics")

RABBITMQ_URL = os.environ["RABBITMQ_URL"]
EXCHANGE, QUEUE = "loyalty.events", "analytics.events"

stores: dict[str, dict] = {}
stats = {"events_received": 0}
seen: set[str] = set()   # защита от повторной доставки одного и того же события


def new_store(store_id: str) -> dict:
    return {
        "store_id": store_id,
        "purchases_accepted": 0, "returns_accepted": 0, "redeems_accepted": 0,
        "operations_rejected": 0,
        "points_accrued": 0,     # начислено за покупки
        "points_returned": 0,    # списано при возвратах
        "points_redeemed": 0,    # потрачено на оплату покупок
    }


def apply_event(event: dict) -> None:
    op_id = event["operation_id"]
    if op_id in seen:
        log.info("событие %s уже учтено, пропуск", op_id)
        return
    seen.add(op_id)
    stats["events_received"] += 1
    store = stores.setdefault(event["store_id"], new_store(event["store_id"]))
    if event["status"] != "applied":
        store["operations_rejected"] += 1   # отклонённые суммы не меняют
        return
    delta = abs(int(event["points_delta"]))
    if event["type"] == "purchase":
        store["purchases_accepted"] += 1
        store["points_accrued"] += delta
    elif event["type"] == "return":
        store["returns_accepted"] += 1
        store["points_returned"] += delta
    elif event["type"] == "redeem":
        store["redeems_accepted"] += 1
        store["points_redeemed"] += delta


async def declare(channel: aio_pika.abc.AbstractChannel) -> aio_pika.abc.AbstractQueue:
    exchange = await channel.declare_exchange(EXCHANGE, aio_pika.ExchangeType.FANOUT, durable=True)
    queue = await channel.declare_queue(QUEUE, durable=True, arguments={"x-queue-type": "quorum"})
    await queue.bind(exchange)
    return queue


async def consume_events(connection: aio_pika.abc.AbstractRobustConnection) -> None:
    while True:
        try:
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=10)
            queue = await declare(channel)
            async with queue.iterator() as messages:
                async for message in messages:
                    async with message.process():   # ack при успешном выходе
                        try:
                            apply_event(json.loads(message.body.decode("utf-8")))
                        except Exception:  # noqa: BLE001
                            log.exception("не удалось обработать событие %s", message.message_id)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("потребитель событий упал, перезапуск через 3 с")
            await asyncio.sleep(3)


async def connect() -> aio_pika.abc.AbstractRobustConnection:
    for attempt in range(1, 61):
        try:
            return await aio_pika.connect_robust(RABBITMQ_URL)
        except Exception as exc:  # noqa: BLE001
            log.warning("RabbitMQ недоступен (%d/60): %s", attempt, exc)
            await asyncio.sleep(2)
    raise RuntimeError("RabbitMQ недоступен")


@asynccontextmanager
async def lifespan(app: FastAPI):
    connection = await connect()
    task = asyncio.create_task(consume_events(connection))   # в фоне, HTTP не блокируется
    log.info("analytics запущен")
    yield
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await connection.close()


app = FastAPI(title="Бонусная программа: analytics", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


@app.get("/stores")
async def get_stores():
    return list(stores.values())


@app.get("/stores/{store_id}")
async def get_store(store_id: str):
    if store_id not in stores:
        raise HTTPException(status_code=404, detail="Нет событий по магазину")
    return stores[store_id]


@app.get("/stats")
async def get_stats():
    return stats
