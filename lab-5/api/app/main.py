import logging
import pathlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from . import config
from .broker import Broker
from .models import Account, OperationRow
from .schemas import OperationIn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s api: %(message)s")
log = logging.getLogger("api")

STATIC = pathlib.Path(__file__).parent / "static"

engine = create_async_engine(config.DATABASE_URL, pool_pre_ping=True)
sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
broker = Broker()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await broker.start()
    log.info("api запущен")
    yield
    await broker.close()
    await engine.dispose()


app = FastAPI(title="Бонусная программа: api", lifespan=lifespan)


def event_view(row: OperationRow) -> dict:
    """Формат события раздела III."""
    return {
        "operation_id": row.operation_id,
        "type": row.type,
        "customer_id": row.customer_id,
        "store_id": row.store_id,
        "status": row.status,
        "points_delta": int(row.points_delta),
        "balance_after": int(row.balance_after),
        "reject_reason": row.reject_reason,
        "processed_at": row.processed_at.isoformat(),
    }


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(STATIC / "index.html")


@app.post("/operations", status_code=202)
async def accept_operation(op: OperationIn):
    payload = op.model_dump(mode="json", exclude_none=True)   # Decimal -> строка, datetime -> ISO
    try:
        await broker.publish_operation(payload)
    except Exception as exc:  # noqa: BLE001
        log.error("публикация %s не подтверждена: %s", op.operation_id, exc)
        raise HTTPException(status_code=503, detail="Брокер не подтвердил публикацию")
    return {"operation_id": op.operation_id}


@app.get("/operations/{operation_id}")
async def get_operation(operation_id: str):
    async with sessionmaker() as session:
        row = await session.get(OperationRow, operation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Операция ещё не обработана")
    return event_view(row)


@app.get("/accounts/{customer_id}")
async def get_account(customer_id: str):
    async with sessionmaker() as session:
        account = await session.get(Account, customer_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Счёт не найден")
        rows = (await session.scalars(
            select(OperationRow)
            .where(OperationRow.customer_id == customer_id)
            .order_by(OperationRow.processed_at.desc())
            .limit(20)
        )).all()
    operations = []
    for row in rows:
        item = event_view(row)
        item.update(
            check_number=row.check_number,
            amount=str(row.amount) if row.amount is not None else None,
            occurred_at=row.occurred_at.isoformat(),
        )
        operations.append(item)
    return {"customer_id": account.customer_id, "balance": int(account.balance), "operations": operations}


@app.get("/health")
async def health():
    problems = {}
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        problems["database"] = str(exc)
    try:
        await broker.ping()
    except Exception as exc:  # noqa: BLE001
        problems["broker"] = str(exc)
    if problems:
        return JSONResponse(status_code=503, content={"status": "unavailable", **problems})
    return {"status": "ok", "database": "ok", "broker": "ok"}
