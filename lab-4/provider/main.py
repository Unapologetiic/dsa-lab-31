"""Заглушка поставщика. Параметры задаются переменными окружения."""
import asyncio
import datetime as dt
import os
import random

from fastapi import FastAPI, HTTPException

NAME = os.getenv("PROVIDER_NAME", "provider1")
DELAY_MS = float(os.getenv("DELAY_MS", "300"))              # средняя задержка, ±30 %
ERROR_PERCENT = float(os.getenv("ERROR_PERCENT", "5"))      # ответы с ошибкой 500, %
SLOW_PERCENT = float(os.getenv("SLOW_PERCENT", "0"))        # ответы с задержкой 3 с, %
FLIGHTS_PER_DAY = int(os.getenv("FLIGHTS_PER_DAY", "500"))

AIRPORTS = [
    "SVO", "DME", "VKO", "LED", "AER", "KZN", "OVB", "SVX", "KRR", "ROV",
    "UFA", "KGD", "GOJ", "MRV", "KUF", "CEK", "IKT", "KJA", "VVO", "KHV",
    "MMK", "ARH", "PEE", "TJM", "OMS", "TOF", "UUD", "YKS", "VOG", "VOZ",
]

app = FastAPI()


def generate_flights(date: dt.date) -> list[dict]:
    # генератор данных зависит только от поставщика и даты -> для одной даты рейсы одинаковые
    rnd = random.Random(f"{NAME}-{date.isoformat()}")
    midnight = dt.datetime.combine(date, dt.time.min)
    flights = []
    for _ in range(FLIGHTS_PER_DAY):
        origin, destination = rnd.sample(AIRPORTS, 2)
        departure = midnight + dt.timedelta(minutes=rnd.randrange(24 * 60))
        arrival = departure + dt.timedelta(minutes=rnd.randint(60, 360))
        flights.append({
            "carrier": NAME,
            "flight_no": f"{NAME}-{rnd.randint(100, 9999)}",
            "origin": origin,
            "destination": destination,
            "departure": departure.isoformat(),
            "arrival": arrival.isoformat(),
            "price": rnd.randint(2000, 20000),
        })
    return flights


@app.get("/flights")
async def flights(date: dt.date):
    # задержки и ошибки определяются модулем random без seed (отдельно от данных)
    if random.random() < SLOW_PERCENT / 100:
        await asyncio.sleep(3)
    else:
        await asyncio.sleep(DELAY_MS / 1000 * random.uniform(0.7, 1.3))
    if random.random() < ERROR_PERCENT / 100:
        raise HTTPException(status_code=500, detail="provider error")
    return generate_flights(date)


@app.get("/health")
async def health():
    return {"status": "ok"}
