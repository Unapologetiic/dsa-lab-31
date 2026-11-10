"""notifier: события из notifier.events -> уведомления покупателям (в памяти)."""
import asyncio
import json
import logging
import os
import random
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import aio_pika
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s notifier: %(message)s")
log = logging.getLogger("notifier")

RABBITMQ_URL = os.environ["RABBITMQ_URL"]
MIN_DELAY_MS = int(os.getenv("MIN_DELAY_MS", "200"))
MAX_DELAY_MS = int(os.getenv("MAX_DELAY_MS", "1500"))
UNSUBSCRIBED = {c.strip() for c in os.getenv("UNSUBSCRIBED", "").split(",") if c.strip()}

EXCHANGE, QUEUE = "loyalty.events", "notifier.events"

notifications: dict[str, list[dict]] = defaultdict(list)
stats = {"events_received": 0, "notifications_sent": 0}
seen: set[str] = set()   # защита от повторной доставки одного и того же события


def build_text(event: dict) -> str:
    if event["status"] == "rejected":
        return f"Операция отклонена: {event['reject_reason']}"
    points, balance = abs(int(event["points_delta"])), int(event["balance_after"])
    if event["type"] == "purchase":
        return f"Начислено {points} баллов, баланс {balance}"
    return f"Списано {points} баллов, баланс {balance}"


async def handle_event(event: dict) -> None:
    op_id = event["operation_id"]
    if op_id in seen:
        log.info("событие %s уже обработано, пропуск", op_id)
        return
    seen.add(op_id)
    stats["events_received"] += 1
    customer = event["customer_id"]
    if customer in UNSUBSCRIBED:
        log.info("%s отписан, уведомление по %s не отправляется", customer, op_id)
        return
    text = build_text(event)
    await asyncio.sleep(random.randint(MIN_DELAY_MS, MAX_DELAY_MS) / 1000)   # имитация отправки
    notifications[customer].append({
        "operation_id": op_id, "customer_id": customer, "text": text,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    })
    stats["notifications_sent"] += 1
    log.info("-> %s: %s", customer, text)


async def declare(channel: aio_pika.abc.AbstractChannel) -> aio_pika.abc.AbstractQueue:
    exchange = await channel.declare_exchange(EXCHANGE, aio_pika.ExchangeType.FANOUT, durable=True)
    queue = await channel.declare_queue(QUEUE, durable=True, arguments={"x-queue-type": "quorum"})
    await queue.bind(exchange)
    return queue


async def consume_events(connection: aio_pika.abc.AbstractRobustConnection) -> None:
    while True:
        try:
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=1)
            queue = await declare(channel)
            async with queue.iterator() as messages:
                async for message in messages:
                    async with message.process():   # ack при успешном выходе
                        try:
                            await handle_event(json.loads(message.body.decode("utf-8")))
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
    log.info("notifier запущен")
    yield
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await connection.close()


app = FastAPI(title="Бонусная программа: notifier", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


@app.get("/notifications")
async def get_notifications(customer_id: str):
    return notifications.get(customer_id, [])


@app.get("/stats")
async def get_stats():
    return stats
