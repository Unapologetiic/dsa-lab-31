"""Генератор рейсов собственной базы (120 дней) и загрузка в PostgreSQL.

Запуск с компьютера (БД из docker compose опубликована на порту 5432):
    pip install "psycopg[binary]"
    python db/generate.py
Повторный запуск очищает таблицу и создаёт те же рейсы (seed = 42).
"""
import datetime as dt
import os
import random

import psycopg

DSN = os.getenv("DB_DSN", "postgresql://postgres:postgres@localhost:5432/flights")

START_DATE = dt.date(2026, 11, 1)   # то же значение в load.py
DAYS = 120
FLIGHTS_PER_DAY = 1500

AIRPORTS = [
    "SVO", "DME", "VKO", "LED", "AER", "KZN", "OVB", "SVX", "KRR", "ROV",
    "UFA", "KGD", "GOJ", "MRV", "KUF", "CEK", "IKT", "KJA", "VVO", "KHV",
    "MMK", "ARH", "PEE", "TJM", "OMS", "TOF", "UUD", "YKS", "VOG", "VOZ",
]


def generate_flights():
    rnd = random.Random(42)
    for day in range(DAYS):
        midnight = dt.datetime.combine(START_DATE + dt.timedelta(days=day), dt.time.min)
        for _ in range(FLIGHTS_PER_DAY):
            origin, destination = rnd.sample(AIRPORTS, 2)
            departure = midnight + dt.timedelta(minutes=rnd.randrange(24 * 60))
            arrival = departure + dt.timedelta(minutes=rnd.randint(60, 360))  # 1..6 ч
            yield (
                "own",
                f"OW{rnd.randint(100, 9999)}",
                origin,
                destination,
                departure,
                arrival,
                rnd.randint(2000, 20000),
            )


def main():
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE flights")
        with cur.copy(
            "COPY flights (carrier, flight_no, origin, destination, departure, arrival, price) "
            "FROM STDIN"
        ) as copy:
            for row in generate_flights():
                copy.write_row(row)
        cur.execute("SELECT count(*) FROM flights")
        print("Загружено рейсов:", cur.fetchone()[0])


if __name__ == "__main__":
    main()
