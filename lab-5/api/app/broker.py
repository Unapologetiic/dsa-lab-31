import asyncio
import json
import logging

import aio_pika

from . import config

log = logging.getLogger("api.broker")


class Broker:
    def __init__(self) -> None:
        self.connection: aio_pika.abc.AbstractRobustConnection | None = None
        self.channel: aio_pika.abc.AbstractChannel | None = None
        self.exchange: aio_pika.abc.AbstractExchange | None = None

    async def start(self, attempts: int = 60) -> None:
        for attempt in range(1, attempts + 1):
            try:
                self.connection = await aio_pika.connect_robust(config.RABBITMQ_URL)
                break
            except Exception as exc:  # noqa: BLE001
                log.warning("RabbitMQ недоступен (%d/%d): %s", attempt, attempts, exc)
                await asyncio.sleep(2)
        else:
            raise RuntimeError("RabbitMQ недоступен")
        self.channel = await self.connection.channel(publisher_confirms=True, on_return_raises=True)
        await self.declare()

    async def declare(self) -> None:
        self.exchange = await self.channel.declare_exchange(
            config.OPERATIONS_EXCHANGE, aio_pika.ExchangeType.DIRECT, durable=True)
        queue = await self.channel.declare_queue(
            config.OPERATIONS_QUEUE, durable=True, arguments={"x-queue-type": "quorum"})
        await queue.bind(self.exchange, routing_key=config.OPERATIONS_KEY)

    async def publish_operation(self, payload: dict) -> None:
        """Публикация с подтверждением брокера. Любая ошибка -> исключение (api вернёт 503)."""
        message = aio_pika.Message(
            body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            content_type="application/json",
            message_id=payload["operation_id"],
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await asyncio.wait_for(
            self.exchange.publish(message, routing_key=config.OPERATIONS_KEY, mandatory=True),
            timeout=5,
        )

    async def ping(self) -> None:
        """Идемпотентное повторное объявление обменника требует живого канала."""
        await asyncio.wait_for(
            self.channel.declare_exchange(
                config.OPERATIONS_EXCHANGE, aio_pika.ExchangeType.DIRECT, durable=True),
            timeout=3,
        )

    async def close(self) -> None:
        if self.connection is not None:
            await self.connection.close()
