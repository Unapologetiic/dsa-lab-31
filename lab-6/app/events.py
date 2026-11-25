"""Передача событий подписчикам внутри одного процесса."""
import asyncio
from collections import defaultdict
from dataclasses import dataclass

from app.db import OrderStatus


@dataclass(frozen=True)
class OrderStatusChanged:
    order_id: int
    status: OrderStatus


_queues: dict[int, set[asyncio.Queue]] = defaultdict(set)


def subscribe(order_id: int) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue()
    _queues[order_id].add(queue)
    return queue


def unsubscribe(order_id: int, queue: asyncio.Queue) -> None:
    queues = _queues.get(order_id)
    if queues is None:
        return
    queues.discard(queue)
    if not queues:
        del _queues[order_id]


def publish(event: OrderStatusChanged) -> None:
    for queue in list(_queues.get(event.order_id, ())):
        queue.put_nowait(event)
