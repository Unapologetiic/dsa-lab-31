"""Доменный слой: расчёт баллов. Не импортирует aio-pika и SQLAlchemy."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_DOWN, Decimal

ACCRUAL_RATE = Decimal("0.05")   # 5 % от суммы чека
REDEEM_LIMIT = Decimal("0.30")   # не более 30 % суммы чека баллами

PURCHASE, RETURN, REDEEM = "purchase", "return", "redeem"
OPERATION_TYPES = (PURCHASE, RETURN, REDEEM)

APPLIED, REJECTED = "applied", "rejected"

DUPLICATE_PURCHASE = "duplicate_purchase"
PURCHASE_NOT_FOUND = "purchase_not_found"
CUSTOMER_MISMATCH = "customer_mismatch"
ALREADY_RETURNED = "already_returned"
LIMIT_EXCEEDED = "limit_exceeded"
INSUFFICIENT_BALANCE = "insufficient_balance"


@dataclass(frozen=True)
class Operation:
    operation_id: str
    type: str
    customer_id: str
    store_id: str
    check_number: str
    occurred_at: datetime
    amount: Decimal | None = None
    points: int | None = None


@dataclass(frozen=True)
class PurchaseInfo:
    """Принятая покупка, на которую ссылается возврат."""
    customer_id: str
    points_awarded: int


@dataclass(frozen=True)
class Context:
    """Всё, что нужно знать о состоянии, чтобы принять решение."""
    balance: Decimal
    accepted_purchase_exists: bool = False     # для покупки
    purchase: PurchaseInfo | None = None       # для возврата
    already_returned: bool = False             # для возврата


@dataclass(frozen=True)
class Decision:
    status: str
    points_delta: int
    reject_reason: str | None = None


def _reject(reason: str) -> Decision:
    return Decision(REJECTED, 0, reason)


def parse_operation(data: dict) -> Operation:
    """Разбор и проверка тела сообщения. ValueError / KeyError / ArithmeticError при ошибке."""
    op_type = data["type"]
    if op_type not in OPERATION_TYPES:
        raise ValueError(f"unknown type {op_type!r}")
    strings = {}
    for key in ("operation_id", "customer_id", "store_id", "check_number"):
        value = data[key]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"bad field {key}")
        strings[key] = value.strip()
    occurred_at = datetime.fromisoformat(str(data["occurred_at"]))

    amount = None
    if data.get("amount") is not None:
        amount = Decimal(str(data["amount"]))
        if not amount.is_finite() or amount <= 0:
            raise ValueError("amount must be positive")
    points = data.get("points")
    if points is not None:
        if isinstance(points, bool) or not isinstance(points, int) or points <= 0:
            raise ValueError("points must be a positive integer")
    if op_type in (PURCHASE, REDEEM) and amount is None:
        raise ValueError("amount is required")
    if op_type == REDEEM and points is None:
        raise ValueError("points is required")
    return Operation(type=op_type, occurred_at=occurred_at, amount=amount, points=points, **strings)


def decide(op: Operation, ctx: Context) -> Decision:
    """Чистая функция: операция + состояние -> решение. Причины проверяются в порядке таблицы 3."""
    if op.type == PURCHASE:
        if ctx.accepted_purchase_exists:
            return _reject(DUPLICATE_PURCHASE)
        earned = int((op.amount * ACCRUAL_RATE).to_integral_value(rounding=ROUND_DOWN))
        return Decision(APPLIED, earned)

    if op.type == RETURN:
        if ctx.purchase is None:
            return _reject(PURCHASE_NOT_FOUND)
        if ctx.purchase.customer_id != op.customer_id:
            return _reject(CUSTOMER_MISMATCH)
        if ctx.already_returned:
            return _reject(ALREADY_RETURNED)
        return Decision(APPLIED, -ctx.purchase.points_awarded)

    # REDEEM
    if Decimal(op.points) > op.amount * REDEEM_LIMIT:
        return _reject(LIMIT_EXCEEDED)
    if Decimal(op.points) > ctx.balance:
        return _reject(INSUFFICIENT_BALANCE)
    return Decision(APPLIED, -op.points)
