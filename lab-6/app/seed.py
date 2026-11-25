"""Заполнение базы: python -m app.seed

5 ресторанов, по 10 блюд, 100 заказов в разных состояниях.
Перед заполнением таблицы очищаются, поэтому команду можно запускать повторно.
"""
import asyncio
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import insert, text

from app import db
from app.db import OrderStatus

RESTAURANTS = [
    ("Пицца Рома", "ул. Ленина, 10", [
        "Маргарита", "Пепперони", "Четыре сыра", "Гавайская", "Диабло",
        "Карбонара", "Цезарь", "Тирамису", "Лимонад", "Морс клюквенный"]),
    ("Суши-Бар Токио", "пр. Карла Маркса, 25", [
        "Филадельфия", "Калифорния", "Ролл с угрём", "Мисо-суп", "Рамен",
        "Гёдза", "Сашими лосось", "Чука", "Зелёный чай", "Моти"]),
    ("Бургерная Гриль", "ул. Советская, 5", [
        "Классический бургер", "Чизбургер", "Двойной бургер", "Куриный бургер",
        "Картофель фри", "Луковые кольца", "Наггетсы", "Молочный коктейль",
        "Кола", "Брауни"]),
    ("Хинкальная Тбилиси", "ул. Красный проспект, 40", [
        "Хинкали с говядиной", "Хинкали с сыром", "Хачапури по-аджарски",
        "Хачапури по-имеретински", "Шашлык из баранины", "Харчо", "Лобио",
        "Пхали", "Тархун", "Чурчхела"]),
    ("Домашняя кухня", "ул. Кирова, 17", [
        "Борщ", "Пельмени", "Котлета с пюре", "Гречка с грибами", "Оливье",
        "Блины с мясом", "Сырники", "Компот", "Чай с лимоном", "Пирожок с вишней"]),
]
NAMES = ["Анна", "Борис", "Виктория", "Глеб", "Дарья", "Егор", "Елена",
         "Иван", "Мария", "Николай", "Ольга", "Павел", "Софья", "Тимур"]
STREETS = ["ул. Ленина", "ул. Кирова", "пр. Дзержинского", "ул. Гоголя",
           "ул. Депутатская", "ул. Орджоникидзе", "ул. Нарымская"]
REASONS = ["Долго ждать", "Передумал", "Ошибся адресом", "Заказал по ошибке",
           "Нашёл вариант дешевле"]
STATUS_COUNTS = [
    (OrderStatus.CREATED, 15), (OrderStatus.ACCEPTED, 15),
    (OrderStatus.READY, 15), (OrderStatus.DELIVERED, 40),
    (OrderStatus.CANCELLED, 15),
]


async def main() -> None:
    rnd = random.Random(2026)
    db.engine.sync_engine.echo = False  # не засорять вывод
    await db.create_tables()
    now = datetime.now(timezone.utc)

    async with db.SessionLocal() as s:
        async with s.begin():
            await s.execute(text(
                "TRUNCATE order_items, orders, dishes, restaurants "
                "RESTART IDENTITY CASCADE"))

            menus: dict[int, list[tuple[int, Decimal]]] = {}
            for name, address, dish_names in RESTAURANTS:
                rid = (await s.execute(
                    insert(db.restaurants)
                    .values(name=name, address=address)
                    .returning(db.restaurants.c.id))).scalar_one()
                rows = (await s.execute(
                    insert(db.dishes).values([
                        {"restaurant_id": rid, "name": d,
                         "price": Decimal(rnd.randint(15, 95) * 10)}
                        for d in dish_names
                    ]).returning(db.dishes.c.id, db.dishes.c.price))).all()
                menus[rid] = [(r.id, r.price) for r in rows]

            statuses = [st for st, n in STATUS_COUNTS for _ in range(n)]
            rnd.shuffle(statuses)
            for status in statuses:
                rid = rnd.choice(list(menus))
                picked = rnd.sample(menus[rid], rnd.randint(1, 4))
                lines = [(d, rnd.randint(1, 5), p) for d, p in picked]
                total = sum((p * q for _, q, p in lines), Decimal("0"))
                created = now - timedelta(minutes=rnd.randint(5, 14 * 24 * 60))
                oid = (await s.execute(
                    insert(db.orders).values(
                        restaurant_id=rid,
                        customer_name=rnd.choice(NAMES),
                        delivery_address=(
                            f"{rnd.choice(STREETS)}, {rnd.randint(1, 120)}"),
                        status=status.value,
                        cancel_reason=(rnd.choice(REASONS)
                                       if status is OrderStatus.CANCELLED
                                       else None),
                        total=total,
                        created_at=created,
                    ).returning(db.orders.c.id))).scalar_one()
                await s.execute(insert(db.order_items), [
                    {"order_id": oid, "dish_id": d, "quantity": q, "price": p}
                    for d, q, p in lines])

    await db.engine.dispose()
    print("Готово: 5 ресторанов, 50 блюд, 100 заказов")


if __name__ == "__main__":
    asyncio.run(main())
