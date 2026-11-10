"""Отображение таблиц, которые создаёт worker. api их не создаёт, только читает."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"

    customer_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 0))


class OperationRow(Base):
    __tablename__ = "operations"

    operation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(16))
    customer_id: Mapped[str] = mapped_column(String(64))
    store_id: Mapped[str] = mapped_column(String(64))
    check_number: Mapped[str] = mapped_column(String(64))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    points_delta: Mapped[Decimal] = mapped_column(Numeric(18, 0))
    balance_after: Mapped[Decimal] = mapped_column(Numeric(18, 0))
    status: Mapped[str] = mapped_column(String(16))
    reject_reason: Mapped[str | None] = mapped_column(String(32))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
