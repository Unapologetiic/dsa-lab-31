"""Таблицы и функции доступа к данным. Модуль не импортирует Strawberry."""
import enum
import os
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Column, DateTime, ForeignKey, Integer, MetaData, Numeric, String, Table,
    func, insert, select, update,
)
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://app:app@localhost:5432/delivery")

# echo=True: каждый SQL-запрос попадает в журнал приложения 
engine = create_async_engine(DATABASE_URL, echo=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class OrderStatus(enum.Enum):
    CREATED = "CREATED"
    ACCEPTED = "ACCEPTED"
    READY = "READY"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


metadata = MetaData()

restaurants = Table(
    "restaurants", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(100), nullable=False),
    Column("address", String(200), nullable=False),
)
dishes = Table(
    "dishes", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("restaurant_id", Integer, ForeignKey("restaurants.id"),
           nullable=False, index=True),
    Column("name", String(100), nullable=False),
    Column("price", Numeric(10, 2), nullable=False),
)
orders = Table(
    "orders", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("restaurant_id", Integer, ForeignKey("restaurants.id"),
           nullable=False, index=True),
    Column("customer_name", String(100), nullable=False),
    Column("delivery_address", String(200), nullable=False),
    Column("status", String(20), nullable=False, index=True),
    Column("cancel_reason", String(200), nullable=True),
    Column("total", Numeric(12, 2), nullable=False),
    Column("created_at", DateTime(timezone=True),
           server_default=func.now(), nullable=False, index=True),
)
order_items = Table(
    "order_items", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("order_id", Integer, ForeignKey("orders.id"),
           nullable=False, index=True),
    Column("dish_id", Integer, ForeignKey("dishes.id"), nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("price", Numeric(10, 2), nullable=False),  # цена на момент заказа
)


@dataclass(frozen=True)
class RestaurantRow:
    id: int
    name: str
    address: str


@dataclass(frozen=True)
class DishRow:
    id: int
    restaurant_id: int
    name: str
    price: Decimal


@dataclass(frozen=True)
class OrderRow:
    id: int
    restaurant_id: int
    customer_name: str
    delivery_address: str
    status: OrderStatus
    cancel_reason: str | None
    total: Decimal
    created_at: datetime


@dataclass(frozen=True)
class ItemRow:
    order_id: int
    dish_id: int
    quantity: int
    price: Decimal


def _restaurant(r) -> RestaurantRow:
    return RestaurantRow(r.id, r.name, r.address)


def _dish(r) -> DishRow:
    return DishRow(r.id, r.restaurant_id, r.name, r.price)


def _order(r) -> OrderRow:
    return OrderRow(
        r.id, r.restaurant_id, r.customer_name, r.delivery_address,
        OrderStatus(r.status), r.cancel_reason, r.total, r.created_at)


def _item(r) -> ItemRow:
    return ItemRow(r.order_id, r.dish_id, r.quantity, r.price)


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)


# --- чтение по одному идентификатору -------------------------------------

async def get_restaurant(restaurant_id: int) -> RestaurantRow | None:
    async with SessionLocal() as s:
        r = (await s.execute(
            select(restaurants).where(restaurants.c.id == restaurant_id)
        )).one_or_none()
    return _restaurant(r) if r else None


async def get_dish(dish_id: int) -> DishRow | None:
    async with SessionLocal() as s:
        r = (await s.execute(
            select(dishes).where(dishes.c.id == dish_id))).one_or_none()
    return _dish(r) if r else None


async def get_order(order_id: int) -> OrderRow | None:
    async with SessionLocal() as s:
        r = (await s.execute(
            select(orders).where(orders.c.id == order_id))).one_or_none()
    return _order(r) if r else None


async def get_items(order_id: int) -> list[ItemRow]:
    async with SessionLocal() as s:
        rows = (await s.execute(
            select(order_items)
            .where(order_items.c.order_id == order_id)
            .order_by(order_items.c.id)
        )).all()
    return [_item(r) for r in rows]


# --- чтение по списку идентификаторов (один SQL-запрос) -------------------

async def get_restaurants(ids: list[int]) -> dict[int, RestaurantRow]:
    if not ids:
        return {}
    async with SessionLocal() as s:
        rows = (await s.execute(
            select(restaurants).where(restaurants.c.id.in_(ids)))).all()
    return {r.id: _restaurant(r) for r in rows}


async def get_dishes(ids: list[int]) -> dict[int, DishRow]:
    if not ids:
        return {}
    async with SessionLocal() as s:
        rows = (await s.execute(
            select(dishes).where(dishes.c.id.in_(ids)))).all()
    return {r.id: _dish(r) for r in rows}


async def get_items_by_orders(order_ids: list[int]) -> dict[int, list[ItemRow]]:
    if not order_ids:
        return {}
    async with SessionLocal() as s:
        rows = (await s.execute(
            select(order_items)
            .where(order_items.c.order_id.in_(order_ids))
            .order_by(order_items.c.id)
        )).all()
    result: dict[int, list[ItemRow]] = {}
    for r in rows:
        result.setdefault(r.order_id, []).append(_item(r))
    return result


async def get_dishes_by_restaurants(
        restaurant_ids: list[int]) -> dict[int, list[DishRow]]:
    """Дополнительная функция: меню ресторанов (поле Restaurant.dishes)."""
    if not restaurant_ids:
        return {}
    async with SessionLocal() as s:
        rows = (await s.execute(
            select(dishes)
            .where(dishes.c.restaurant_id.in_(restaurant_ids))
            .order_by(dishes.c.id)
        )).all()
    result: dict[int, list[DishRow]] = {}
    for r in rows:
        result.setdefault(r.restaurant_id, []).append(_dish(r))
    return result


# --- списки ----------------------------------------------------------------

async def list_restaurants() -> list[RestaurantRow]:
    async with SessionLocal() as s:
        rows = (await s.execute(
            select(restaurants).order_by(restaurants.c.id))).all()
    return [_restaurant(r) for r in rows]


async def list_orders(status: OrderStatus | None = None) -> list[OrderRow]:
    stmt = select(orders)
    if status is not None:
        stmt = stmt.where(orders.c.status == status.value)
    stmt = stmt.order_by(orders.c.created_at.desc(), orders.c.id.desc())
    async with SessionLocal() as s:
        rows = (await s.execute(stmt)).all()
    return [_order(r) for r in rows]


# --- запись (используется только модулем services) -------------------------

async def insert_order(
    restaurant_id: int,
    customer_name: str,
    delivery_address: str,
    items: list[tuple[int, int, Decimal]],  # (dish_id, quantity, price)
    total: Decimal,
) -> OrderRow:
    """Создаёт заказ и его позиции в одной транзакции."""
    async with SessionLocal() as s:
        async with s.begin():
            row = (await s.execute(
                insert(orders).values(
                    restaurant_id=restaurant_id,
                    customer_name=customer_name,
                    delivery_address=delivery_address,
                    status=OrderStatus.CREATED.value,
                    cancel_reason=None,
                    total=total,
                ).returning(orders)
            )).one()
            await s.execute(
                insert(order_items),
                [{"order_id": row.id, "dish_id": d, "quantity": q, "price": p}
                 for d, q, p in items],
            )
    return _order(row)


async def transition_order(
    order_id: int,
    allowed_from: tuple[OrderStatus, ...],
    new_status: OrderStatus,
    cancel_reason: str | None = None,
) -> OrderRow | None:
    """Меняет состояние, только если заказ ещё в одном из allowed_from.

    Условие в WHERE защищает от гонки двух одновременных событий.
    Возвращает None, если заказ не найден или состояние уже другое.
    """
    values: dict = {"status": new_status.value}
    if new_status is OrderStatus.CANCELLED:
        values["cancel_reason"] = cancel_reason
    stmt = (
        update(orders)
        .where(orders.c.id == order_id,
               orders.c.status.in_([s.value for s in allowed_from]))
        .values(**values)
        .returning(orders)
    )
    async with SessionLocal() as s:
        async with s.begin():
            row = (await s.execute(stmt)).one_or_none()
    return _order(row) if row else None
