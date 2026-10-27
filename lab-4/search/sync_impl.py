"""Синхронная логика поиска: requests + SQLAlchemy Core (psycopg)."""
import time

import requests
from sqlalchemy import create_engine, text

from common import (
    PROVIDERS, PROVIDER_TIMEOUT, RETRY_PAUSE, SYNC_DB_URL, FLIGHTS_SQL,
    day_bounds, flight_from_json, make_response, provider_url,
)
from routes import Flight

engine = create_engine(SYNC_DB_URL)


def load_own(date):
    start, end = day_bounds(date)
    with engine.connect() as conn:
        rows = conn.execute(text(FLIGHTS_SQL), {"start": start, "end": end}).all()
    return [Flight(*row) for row in rows]


def fetch_provider(name, date):
    deadline = time.monotonic() + PROVIDER_TIMEOUT      # общий срок на запрос и повтор
    for attempt in (1, 2):
        try:
            r = requests.get(
                provider_url(name),
                params={"date": date.isoformat()},
                timeout=max(deadline - time.monotonic(), 0.001),
            )
            r.raise_for_status()
            return [flight_from_json(f) for f in r.json()]
        except requests.RequestException:
            # повтор один раз через 200 мс, только если после паузы ещё остаётся время
            if attempt == 2 or time.monotonic() + RETRY_PAUSE >= deadline:
                raise
            time.sleep(RETRY_PAUSE)


def search_sync(origin, destination, date):
    started = time.monotonic()
    own = load_own(date)
    results = {}
    for name in PROVIDERS:                               # по очереди
        try:
            results[name] = fetch_provider(name, date)
        except requests.RequestException:
            results[name] = None
    return make_response(origin, destination, own, results, started)
