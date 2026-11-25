"""Схема GraphQL и обработчики (resolvers).

Файл нельзя называть graphql.py: так называется библиотека graphql-core,
на которой построен Strawberry. Обработчики не содержат SQL и бизнес-правил:
запросы читают данные через модуль db, мутации вызывают модуль services.
"""
import logging
import os
from datetime import datetime
from decimal import Decimal
from typing import AsyncGenerator, Iterator

import strawberry
from graphql import GraphQLError
from strawberry.dataloader import DataLoader
from strawberry.extensions import SchemaExtension
from strawberry.types import Info

from app import db, events, services

log = logging.getLogger(__name__)

# USE_DATALOADERS=0 включает связанные поля без загрузчиков
USE_LOADERS = os.getenv("USE_DATALOADERS", "1") != "0"

OrderStatus = strawberry.enum(db.OrderStatus)
FINAL_STATES = {db.OrderStatus.DELIVERED, db.OrderStatus.CANCELLED}


# --- идентификаторы и ошибки ----------------------------------------------

def to_int_id(value: str) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if 0 < number <= 2**31 - 1 else None


def require_id(value: str) -> int:
    number = to_int_id(value)
    if number is None:
        raise GraphQLError(
            f"Некорректный идентификатор: {value}",
            extensions={"code": "NOT_FOUND"})
    return number


ERROR_CODES = {
    services.NotFound: "NOT_FOUND",
    services.TransitionNotAllowed: "TRANSITION_NOT_ALLOWED",
    services.OrderValidationError: "VALIDATION_ERROR",
}


async def call(operation):
    """Выполняет бизнес-операцию, исключения services -> GraphQLError."""
    try:
        return await operation
    except tuple(ERROR_CODES) as exc:
        raise GraphQLError(
            str(exc), extensions={"code": ERROR_CODES[type(exc)]})
    except Exception:
        log.exception("Ошибка при выполнении операции")
        raise GraphQLError(
            "Internal error", extensions={"code": "INTERNAL_ERROR"})


class InternalErrors(SchemaExtension):
    """Заменяет текст непредвиденных исключений (SQL, пути к файлам)
    на «Internal error». Ошибки валидации запроса и GraphQLError
    из обработчиков остаются без изменений."""

    def on_operation(self) -> Iterator[None]:
        yield
        result = self.execution_context.result
        if result is not None and result.errors:
            result.errors = [self._mask(e) for e in result.errors]

    @staticmethod
    def _mask(error: GraphQLError) -> GraphQLError:
        original = error.original_error
        if original is None or isinstance(original, GraphQLError):
            return error
        log.error("Необработанная ошибка в поле %s", error.path,
                  exc_info=original)
        return GraphQLError(
            "Internal error", nodes=error.nodes, source=error.source,
            positions=error.positions, path=error.path,
            extensions={"code": "INTERNAL_ERROR"})


# --- доступ к связанным данным --------------------------------------------

async def _restaurant(info: Info, rid: int) -> db.RestaurantRow | None:
    if USE_LOADERS:
        return await info.context["restaurants"].load(rid)
    return await db.get_restaurant(rid)


async def _dish(info: Info, did: int) -> db.DishRow | None:
    if USE_LOADERS:
        return await info.context["dishes"].load(did)
    return await db.get_dish(did)


async def _items(info: Info, oid: int) -> list[db.ItemRow]:
    if USE_LOADERS:
        return await info.context["items"].load(oid)
    return await db.get_items(oid)


async def _menu(info: Info, rid: int) -> list[db.DishRow]:
    if USE_LOADERS:
        return await info.context["menus"].load(rid)
    return (await db.get_dishes_by_restaurants([rid])).get(rid, [])


# --- типы -----------------------------------------------------------------

@strawberry.type
class Restaurant:
    id: strawberry.ID
    name: str
    address: str

    @strawberry.field
    async def dishes(self, info: Info) -> list["Dish"]:
        rows = await _menu(info, int(self.id))
        return [to_dish(r) for r in rows]


@strawberry.type
class Dish:
    id: strawberry.ID
    name: str
    price: Decimal
    restaurant_id: strawberry.Private[int]

    @strawberry.field
    async def restaurant(self, info: Info) -> Restaurant:
        return to_restaurant(await _restaurant(info, self.restaurant_id))


@strawberry.type
class OrderItem:
    quantity: int
    price: Decimal
    dish_id: strawberry.Private[int]

    @strawberry.field
    async def dish(self, info: Info) -> Dish:
        return to_dish(await _dish(info, self.dish_id))

    @strawberry.field
    def amount(self) -> Decimal:
        return self.price * self.quantity


@strawberry.type
class Order:
    id: strawberry.ID
    status: OrderStatus
    total: Decimal
    created_at: datetime
    customer_name: str
    delivery_address: str
    cancel_reason: str | None
    restaurant_id: strawberry.Private[int]

    @strawberry.field
    async def restaurant(self, info: Info) -> Restaurant:
        return to_restaurant(await _restaurant(info, self.restaurant_id))

    @strawberry.field
    async def items(self, info: Info) -> list[OrderItem]:
        rows = await _items(info, int(self.id))
        return [to_item(r) for r in rows]


def to_restaurant(row: db.RestaurantRow) -> Restaurant:
    return Restaurant(
        id=strawberry.ID(str(row.id)), name=row.name, address=row.address)


def to_dish(row: db.DishRow) -> Dish:
    return Dish(
        id=strawberry.ID(str(row.id)), name=row.name, price=row.price,
        restaurant_id=row.restaurant_id)


def to_item(row: db.ItemRow) -> OrderItem:
    return OrderItem(
        quantity=row.quantity, price=row.price, dish_id=row.dish_id)


def to_order(row: db.OrderRow) -> Order:
    return Order(
        id=strawberry.ID(str(row.id)),
        status=row.status,
        total=row.total,
        created_at=row.created_at,
        customer_name=row.customer_name,
        delivery_address=row.delivery_address,
        cancel_reason=row.cancel_reason,
        restaurant_id=row.restaurant_id,
    )


# --- входные типы ---------------------------------------------------------

@strawberry.input
class OrderItemInput:
    dish_id: strawberry.ID
    quantity: int


@strawberry.input
class CreateOrderInput:
    restaurant_id: strawberry.ID
    customer_name: str
    delivery_address: str
    items: list[OrderItemInput]


# --- запросы, мутации, подписка -------------------------------------------

@strawberry.type
class Query:
    @strawberry.field
    async def order(self, id: strawberry.ID) -> Order | None:
        oid = to_int_id(id)
        row = await db.get_order(oid) if oid is not None else None
        return to_order(row) if row else None

    @strawberry.field
    async def orders(self, status: OrderStatus | None = None) -> list[Order]:
        return [to_order(r) for r in await db.list_orders(status)]

    @strawberry.field
    async def restaurants(self) -> list[Restaurant]:
        return [to_restaurant(r) for r in await db.list_restaurants()]


# Результат мутаций объявлен как Order | None (в схеме Order без «!»):
# при ошибке null получает только поле мутации, а не весь ответ data.
@strawberry.type
class Mutation:
    @strawberry.mutation
    async def create_order(self, input: CreateOrderInput) -> Order | None:
        row = await call(services.create_order(
            require_id(input.restaurant_id),
            input.customer_name,
            input.delivery_address,
            [(require_id(i.dish_id), i.quantity) for i in input.items],
        ))
        return to_order(row)

    @strawberry.mutation
    async def accept_order(self, id: strawberry.ID) -> Order | None:
        return to_order(await call(services.accept(require_id(id))))

    @strawberry.mutation
    async def mark_order_ready(self, id: strawberry.ID) -> Order | None:
        return to_order(await call(services.mark_ready(require_id(id))))

    @strawberry.mutation
    async def mark_order_delivered(self, id: strawberry.ID) -> Order | None:
        return to_order(await call(services.mark_delivered(require_id(id))))

    @strawberry.mutation
    async def cancel_order(
        self, id: strawberry.ID, reason: str
    ) -> Order | None:
        return to_order(await call(services.cancel(require_id(id), reason)))


@strawberry.type
class Subscription:
    @strawberry.subscription
    async def order_status_changed(
        self, order_id: strawberry.ID
    ) -> AsyncGenerator[Order, None]:
        oid = require_id(order_id)
        # очередь регистрируется ДО чтения текущего состояния,
        # иначе событие между чтением и регистрацией будет потеряно
        queue = events.subscribe(oid)
        try:
            row = await db.get_order(oid)
            if row is None:
                raise GraphQLError(
                    f"Заказ {oid} не найден",
                    extensions={"code": "NOT_FOUND"})
            yield to_order(row)  # текущее состояние
            status = row.status
            while status not in FINAL_STATES:
                event = await queue.get()
                status = event.status  # состояние берём из события,
                row = await db.get_order(oid)  # а не из базы данных
                if row is None:
                    break
                order = to_order(row)
                yield order
        except GraphQLError:
            raise
        except Exception:
            log.exception("Ошибка в подписке")
            raise GraphQLError(
                "Internal error", extensions={"code": "INTERNAL_ERROR"})
        finally:
            events.unsubscribe(oid, queue)


# --- загрузчики и контекст ------------------------------------------------

async def load_restaurants(ids: list[int]) -> list[db.RestaurantRow | None]:
    found = await db.get_restaurants(ids)
    return [found.get(i) for i in ids]


async def load_dishes(ids: list[int]) -> list[db.DishRow | None]:
    found = await db.get_dishes(ids)
    return [found.get(i) for i in ids]


async def load_items(order_ids: list[int]) -> list[list[db.ItemRow]]:
    found = await db.get_items_by_orders(order_ids)
    return [found.get(i, []) for i in order_ids]


async def load_menus(restaurant_ids: list[int]) -> list[list[db.DishRow]]:
    found = await db.get_dishes_by_restaurants(restaurant_ids)
    return [found.get(i, []) for i in restaurant_ids]


async def get_context() -> dict:
    # вызывается для каждого GraphQL-запроса: загрузчики кэшируют результаты,
    # поэтому общий (глобальный) загрузчик показывал бы устаревшие данные
    return {
        "restaurants": DataLoader(load_fn=load_restaurants),
        "dishes": DataLoader(load_fn=load_dishes),
        "items": DataLoader(load_fn=load_items),
        "menus": DataLoader(load_fn=load_menus),
    }


schema = strawberry.Schema(
    query=Query, mutation=Mutation, subscription=Subscription,
    extensions=[InternalErrors],
)
