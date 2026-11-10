import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from datetime import datetime, timezone
from decimal import Decimal as D

from app.domain import *

NOW = datetime.now(timezone.utc)


def op(t, amount=None, points=None, customer="C1", check="K1"):
    return Operation("id", t, customer, "S1", check, NOW, D(amount) if amount else None, points)


def test_purchase_floor():
    assert decide(op(PURCHASE, "2490.00"), Context(D(0))).points_delta == 124   # 124.5 -> 124
    assert decide(op(PURCHASE, "19.99"), Context(D(0))).points_delta == 0


def test_purchase_duplicate():
    d = decide(op(PURCHASE, "100"), Context(D(0), accepted_purchase_exists=True))
    assert (d.status, d.reject_reason, d.points_delta) == (REJECTED, DUPLICATE_PURCHASE, 0)


def test_return_reasons_order():
    assert decide(op(RETURN), Context(D(0))).reject_reason == PURCHASE_NOT_FOUND
    other = PurchaseInfo("C2", 50)
    assert decide(op(RETURN), Context(D(0), purchase=other, already_returned=True)).reject_reason == CUSTOMER_MISMATCH
    mine = PurchaseInfo("C1", 50)
    assert decide(op(RETURN), Context(D(0), purchase=mine, already_returned=True)).reject_reason == ALREADY_RETURNED
    d = decide(op(RETURN), Context(D(10), purchase=mine))
    assert (d.status, d.points_delta) == (APPLIED, -50)   # баланс уйдёт в минус: 10 - 50


def test_redeem():
    assert decide(op(REDEEM, "1000", 300), Context(D(500))).status == APPLIED          # ровно 30 %
    assert decide(op(REDEEM, "1000", 301), Context(D(500))).reject_reason == LIMIT_EXCEEDED
    assert decide(op(REDEEM, "1000", 300), Context(D(299))).reject_reason == INSUFFICIENT_BALANCE
    assert decide(op(REDEEM, "1000", 301), Context(D(5))).reject_reason == LIMIT_EXCEEDED   # первая по таблице
    assert decide(op(REDEEM, "100", 10), Context(D(-40))).reject_reason == INSUFFICIENT_BALANCE


def test_parse():
    o = parse_operation({"operation_id": "a", "type": "purchase", "customer_id": "c", "store_id": "s",
                         "check_number": "k", "amount": "2490.00", "occurred_at": "2026-11-10T14:32:05+07:00"})
    assert o.amount == D("2490.00")
    for bad in ({"type": "x"}, ):
        try:
            parse_operation(bad); assert False
        except (ValueError, KeyError):
            pass


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
