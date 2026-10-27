"""Задача 3.3: синхронная версия (обработчики через def)."""
import datetime as dt

from fastapi import FastAPI

from sync_impl import search_sync

app = FastAPI()


@app.get("/search")
def search(origin: str, destination: str, date: dt.date):
    return search_sync(origin, destination, date)


@app.get("/health")
def health():
    return {"status": "ok"}
