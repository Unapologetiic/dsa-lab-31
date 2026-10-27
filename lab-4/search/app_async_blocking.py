"""Задача 4.1: те же обработчики через async def, остальной код не изменён."""
import datetime as dt

from fastapi import FastAPI

from sync_impl import search_sync

app = FastAPI()


@app.get("/search")
async def search(origin: str, destination: str, date: dt.date):
    return search_sync(origin, destination, date)


@app.get("/health")
async def health():
    return {"status": "ok"}
