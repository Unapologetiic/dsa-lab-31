"""Задача 4.2: полностью асинхронная версия (httpx + SQLAlchemy asyncpg)."""
import asyncio
import datetime as dt
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from common import (
    ASYNC_DB_URL, FLIGHTS_SQL, PROVIDERS, PROVIDER_TIMEOUT, RETRY_PAUSE,
    day_bounds, flight_from_json, make_response, provider_url,
)
from routes import Flight


@asynccontextmanager
async def lifespan(app: FastAPI):
    # клиент и движок создаются один раз при запуске
    app.state.client = httpx.AsyncClient(
        limits=httpx.Limits(max_connections=None, max_keepalive_connections=None)
    )
    app.state.engine = create_async_engine(ASYNC_DB_URL)
    yield
    await app.state.client.aclose()
    await app.state.engine.dispose()


app = FastAPI(lifespan=lifespan)


async def load_own(engine, date):
    start, end = day_bounds(date)
    async with engine.connect() as conn:
        result = await conn.execute(text(FLIGHTS_SQL), {"start": start, "end": end})
        rows = result.all()
    return [Flight(*row) for row in rows]


async def fetch_provider(client, name, date):
    started = time.monotonic()
    async with asyncio.timeout(PROVIDER_TIMEOUT):        # один срок на запрос, паузу и повтор
        for attempt in (1, 2):
            try:
                r = await client.get(provider_url(name), params={"date": date.isoformat()})
                r.raise_for_status()
                return [flight_from_json(f) for f in r.json()]
            except httpx.HTTPError:
                if attempt == 2 or time.monotonic() - started + RETRY_PAUSE >= PROVIDER_TIMEOUT:
                    raise
                await asyncio.sleep(RETRY_PAUSE)


@app.get("/search")
async def search(request: Request, origin: str, destination: str, date: dt.date):
    started = time.monotonic()
    own, *provider_results = await asyncio.gather(
        load_own(request.app.state.engine, date),
        *(fetch_provider(request.app.state.client, name, date) for name in PROVIDERS),
        return_exceptions=True,          # ошибка одного поставщика не прерывает остальных
    )
    if isinstance(own, Exception):
        raise own
    results = {
        name: (None if isinstance(r, Exception) else r)
        for name, r in zip(PROVIDERS, provider_results)
    }
    return make_response(origin, destination, own, results, started)


@app.get("/health")
async def health():
    return {"status": "ok"}
