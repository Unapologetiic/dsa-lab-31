from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Numeric, String, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"

    customer_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 0), nullable=False, default=Decimal(0))


class OperationRow(Base):
    __tablename__ = "operations"

    operation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    customer_id: Mapped[str] = mapped_column(String(64), nullable=False)
    store_id: Mapped[str] = mapped_column(String(64), nullable=False)
    check_number: Mapped[str] = mapped_column(String(64), nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    points: Mapped[Decimal | None] = mapped_column(Numeric(18, 0))   # запрошенные баллы (оплата баллами)
    points_delta: Mapped[Decimal] = mapped_column(Numeric(18, 0), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(18, 0), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    reject_reason: Mapped[str | None] = mapped_column(String(32))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_operations_type_check", "type", "check_number"),
        Index("ix_operations_customer_processed", "customer_id", "processed_at"),
        # страховка на уровне БД: одна принятая покупка и один принятый возврат на чек
        Index("uq_applied_purchase_check", "check_number", unique=True,
              postgresql_where=text("type = 'purchase' AND status = 'applied'")),
        Index("uq_applied_return_check", "check_number", unique=True,
              postgresql_where=text("type = 'return' AND status = 'applied'")),
    )
