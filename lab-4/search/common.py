"""Общий код трёх версий сервиса поиска."""
import datetime as dt
import os
import time

from fastapi import HTTPException

from routes import Flight, build_routes, route_to_dict

PROVIDERS = os.getenv("PROVIDERS", "provider1,provider2,provider3").split(",")
PROVIDER_TIMEOUT = 2.0      # с, на поставщика, включая повторный запрос
RETRY_PAUSE = 0.2           # с, пауза перед повтором

DB_DSN = os.getenv("DB_DSN", "postgres:postgres@db:5432/flights")
SYNC_DB_URL = f"postgresql+psycopg://{DB_DSN}"
ASYNC_DB_URL = f"postgresql+asyncpg://{DB_DSN}"

FLIGHTS_SQL = (
    "SELECT carrier, flight_no, origin, destination, departure, arrival, price "
    "FROM flights WHERE departure >= :start AND departure < :end"
)


def provider_url(name: str) -> str:
    return f"http://{name}:8000/flights"


def day_bounds(date: dt.date) -> tuple[dt.datetime, dt.datetime]:
    start = dt.datetime.combine(date, dt.time.min)
    return start, start + dt.timedelta(days=1)


def flight_from_json(d: dict) -> Flight:
    return Flight(
        d["carrier"], d["flight_no"], d["origin"], d["destination"],
        dt.datetime.fromisoformat(d["departure"]),
        dt.datetime.fromisoformat(d["arrival"]),
        d["price"],
    )


def make_response(origin, destination, own_flights, results, started):
    """results: {имя поставщика: список рейсов или None, если не ответил}."""
    failed = [name for name, flights in results.items() if flights is None]
    if len(failed) == len(results) and not own_flights:
        raise HTTPException(
            status_code=503,
            detail={"message": "Поиск временно недоступен", "failed_providers": failed},
        )
    flights = list(own_flights)
    for provider_flights in results.values():
        if provider_flights is not None:
            flights += provider_flights
    routes = build_routes(flights, origin, destination)
    return {
        "routes": [route_to_dict(r) for r in routes],
        "failed_providers": failed,
        "elapsed_ms": round((time.monotonic() - started) * 1000, 1),
    }
