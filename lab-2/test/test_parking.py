from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from domain.exceptions import DomainInvariantViolation, InvalidValueObject
from domain.parking.parking_session import ParkingSession
from domain.parking.parking_spot import ParkingSpot
from domain.parking.services import CloseParkingService, StartParkingService
from domain.parking.value_objects import (
    ParkingPeriod,
    SpotStatus,
    Tariff,
)
from domain.shared.money import Money
from infrastructure.in_memory import (
    InMemoryParkingSessionRepository,
    InMemoryParkingSpotRepository,
)


def make_tariff() -> Tariff:
    return Tariff(price_per_hour=Money(Decimal("100")))


# ---------- Value objects ----------

def test_tariff_positive():
    with pytest.raises(InvalidValueObject):
        Tariff(price_per_hour=Money(Decimal("0")))


def test_tariff_round_up():
    t = make_tariff()
    assert t.calculate(Decimal("1.1")).amount == Decimal("200")
    assert t.calculate(Decimal("2.0")).amount == Decimal("200")
    assert t.calculate(Decimal("0.5")).amount == Decimal("100")


def test_parking_period_invalid():
    with pytest.raises(InvalidValueObject):
        ParkingPeriod(
            entered_at=datetime(2026, 9, 1, 12, 0),
            exited_at=datetime(2026, 9, 1, 11, 0),
        )


# ---------- Агрегат ParkingSpot ----------

def test_spot_occupy_and_release():
    s = ParkingSpot(id=uuid4(), number="A-1")
    s.occupy()
    assert s.status == SpotStatus.OCCUPIED
    s.release()
    assert s.status == SpotStatus.FREE


def test_spot_occupy_twice_fails():
    s = ParkingSpot(id=uuid4(), number="A-1")
    s.occupy()
    with pytest.raises(DomainInvariantViolation):
        s.occupy()


def test_spot_release_when_free_fails():
    s = ParkingSpot(id=uuid4(), number="A-1")
    with pytest.raises(DomainInvariantViolation):
        s.release()


# ---------- Агрегат ParkingSession ----------

def test_session_close_twice_fails():
    t0 = datetime(2026, 9, 1, 9, 0)
    session = ParkingSession(
        id=uuid4(),
        spot_id=uuid4(),
        vehicle_plate="A123BC",
        tariff=make_tariff(),
        entered_at=t0,
    )
    session.close(t0 + timedelta(hours=1))
    with pytest.raises(DomainInvariantViolation):
        session.close(t0 + timedelta(hours=2))


def test_session_close_before_enter_fails():
    t0 = datetime(2026, 9, 1, 9, 0)
    session = ParkingSession(
        id=uuid4(),
        spot_id=uuid4(),
        vehicle_plate="A123BC",
        tariff=make_tariff(),
        entered_at=t0,
    )
    with pytest.raises(InvalidValueObject):
        session.close(t0 - timedelta(minutes=1))


# ---------- Доменные сервисы ----------

def test_parking_full_flow():
    spots = InMemoryParkingSpotRepository()
    sessions = InMemoryParkingSessionRepository()
    spot = ParkingSpot(id=uuid4(), number="A-1")
    spots.save(spot)

    start = StartParkingService(spots, sessions)
    close = CloseParkingService(spots, sessions)

    t_in = datetime(2026, 9, 1, 9, 0)
    session = start.start(spot.id, "A123BC", make_tariff(), t_in)
    assert spots.get(spot.id).status == SpotStatus.OCCUPIED

    session = close.close(session.id, t_in + timedelta(hours=1, minutes=30))
    assert session.cost.amount == Decimal("200")
    assert spots.get(spot.id).status == SpotStatus.FREE


def test_spot_already_occupied_fails():
    spots = InMemoryParkingSpotRepository()
    sessions = InMemoryParkingSessionRepository()
    spot = ParkingSpot(id=uuid4(), number="A-1")
    spots.save(spot)

    start = StartParkingService(spots, sessions)
    t_in = datetime(2026, 9, 1, 9, 0)
    start.start(spot.id, "A123BC", make_tariff(), t_in)

    with pytest.raises(DomainInvariantViolation):
        start.start(spot.id, "B456CD", make_tariff(), t_in)
