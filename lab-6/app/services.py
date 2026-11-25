"""Бизнес-операции. Модуль не импортирует Strawberry."""
from decimal import Decimal

from app import db, events
from app.db import OrderStatus

MIN_ITEMS, MAX_ITEMS = 1, 10
MIN_QTY, MAX_QTY = 1, 20
MIN_REASON, MAX_REASON = 3, 200


class NotFound(Exception):
    """Сущность не найдена."""


class TransitionNotAllowed(Exception):
    """Событие недопустимо в текущем состоянии заказа."""


class OrderValidationError(Exception):
    """Нарушено правило оформления заказа."""


# Таблица 3: событие -> (допустимые исходные состояния, новое состояние)
TRANSITIONS: dict[str, tuple[tuple[OrderStatus, ...], OrderStatus]] = {
    "accept": ((OrderStatus.CREATED,), OrderStatus.ACCEPTED),
    "mark_ready": ((OrderStatus.ACCEPTED,), OrderStatus.READY),
    "mark_delivered": ((OrderStatus.READY,), OrderStatus.DELIVERED),
    "cancel": ((OrderStatus.CREATED, OrderStatus.ACCEPTED),
               OrderStatus.CANCELLED),
}


async def create_order(
    restaurant_id: int,
    customer_name: str,
    delivery_address: str,
    items: list[tuple[int, int]],  # (dish_id, quantity)
) -> db.OrderRow:
    customer_name = customer_name.strip()
    delivery_address = delivery_address.strip()
    if not customer_name:
        raise OrderValidationError("Не указано имя клиента")
    if not delivery_address:
        raise OrderValidationError("Не указан адрес доставки")
    if not MIN_ITEMS <= len(items) <= MAX_ITEMS:
        raise OrderValidationError(
            f"В заказе должно быть от {MIN_ITEMS} до {MAX_ITEMS} позиций")
    for dish_id, quantity in items:
        if not MIN_QTY <= quantity <= MAX_QTY:
            raise OrderValidationError(
                f"Количество порций блюда {dish_id} должно быть "
                f"от {MIN_QTY} до {MAX_QTY}")

    if await db.get_restaurant(restaurant_id) is None:
        raise NotFound(f"Ресторан {restaurant_id} не найден")

    found = await db.get_dishes(sorted({d for d, _ in items}))
    prepared: list[tuple[int, int, Decimal]] = []
    for dish_id, quantity in items:
        dish = found.get(dish_id)
        if dish is None:
            raise NotFound(f"Блюдо {dish_id} не найдено")
        if dish.restaurant_id != restaurant_id:
            raise OrderValidationError(
                f"Блюдо {dish_id} не принадлежит ресторану {restaurant_id}")
        prepared.append((dish_id, quantity, dish.price))  # цена фиксируется

    total = sum((p * q for _, q, p in prepared), Decimal("0"))
    return await db.insert_order(
        restaurant_id, customer_name, delivery_address, prepared, total)


async def _apply(order_id: int, event: str,
                 cancel_reason: str | None = None) -> db.OrderRow:
    allowed, new_status = TRANSITIONS[event]
    order = await db.get_order(order_id)
    if order is None:
        raise NotFound(f"Заказ {order_id} не найден")
    if order.status not in allowed:
        raise TransitionNotAllowed(
            f"Событие {event} недопустимо в состоянии {order.status.value}")
    updated = await db.transition_order(
        order_id, allowed, new_status, cancel_reason)
    if updated is None:  # состояние успел изменить другой запрос
        raise TransitionNotAllowed(
            f"Событие {event} недопустимо: состояние заказа изменилось")
    events.publish(events.OrderStatusChanged(updated.id, updated.status))
    return updated


async def accept(order_id: int) -> db.OrderRow:
    return await _apply(order_id, "accept")


async def mark_ready(order_id: int) -> db.OrderRow:
    return await _apply(order_id, "mark_ready")


async def mark_delivered(order_id: int) -> db.OrderRow:
    return await _apply(order_id, "mark_delivered")


async def cancel(order_id: int, reason: str) -> db.OrderRow:
    reason = reason.strip()
    if not MIN_REASON <= len(reason) <= MAX_REASON:
        raise OrderValidationError(
            f"Причина отмены должна содержать от {MIN_REASON} "
            f"до {MAX_REASON} символов")
    return await _apply(order_id, "cancel", reason)
