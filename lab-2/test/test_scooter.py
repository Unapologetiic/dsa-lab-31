from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from domain.exceptions import DomainInvariantViolation, InvalidValueObject
from domain.scooter.scooter import Scooter
from domain.scooter.services import FinishTripService, StartTripService
from domain.scooter.trip import Trip
from domain.scooter.value_objects import (
    BatteryLevel,
    ScooterStatus,
    Tariff,
    TripPeriod,
)
from domain.shared.money import Money
from infrastructure.in_memory import (
    InMemoryScooterRepository,
    InMemoryTripRepository,
)


def make_tariff() -> Tariff:
    return Tariff(
        price_per_minute=Money(Decimal("5")),
        min_price=Money(Decimal("30")),
    )


# ---------- Value objects ----------

def test_battery_level_range():
    BatteryLevel(0)
    BatteryLevel(100)
    with pytest.raises(InvalidValueObject):
        BatteryLevel(-1)
    with pytest.raises(InvalidValueObject):
        BatteryLevel(101)


def test_tariff_min_greater_than_per_minute():
    with pytest.raises(InvalidValueObject):
        Tariff(
            price_per_minute=Money(Decimal("10")),
            min_price=Money(Decimal("5")),
        )


def test_tariff_calculate_min_price():
    t = make_tariff()
    assert t.calculate(1).amount == Decimal("30")


def test_tariff_calculate_regular():
    t = make_tariff()
    assert t.calculate(12).amount == Decimal("60")


def test_trip_period_invalid():
    with pytest.raises(InvalidValueObject):
        TripPeriod(datetime(2026, 9, 1, 12, 0), datetime(2026, 9, 1, 11, 0))


# ---------- Агрегат Scooter ----------

def test_scooter_start_rent_ok():
    s = Scooter(id=uuid4(), battery=BatteryLevel(80))
    s.start_rent()
    assert s.status == ScooterStatus.RENTED


def test_scooter_low_battery_rejected():
    s = Scooter(id=uuid4(), battery=BatteryLevel(10))
    with pytest.raises(DomainInvariantViolation):
        s.start_rent()


def test_scooter_double_rent_fails():
    s = Scooter(id=uuid4(), battery=BatteryLevel(80))
    s.start_rent()
    with pytest.raises(DomainInvariantViolation):
        s.start_rent()


def test_scooter_finish_rent_ok():
    s = Scooter(id=uuid4(), battery=BatteryLevel(80))
    s.start_rent()
    s.finish_rent()
    assert s.status == ScooterStatus.FREE


def test_scooter_finish_when_not_rented():
    s = Scooter(id=uuid4(), battery=BatteryLevel(80))
    with pytest.raises(DomainInvariantViolation):
        s.finish_rent()


def test_scooter_maintenance_when_rented():
    s = Scooter(id=uuid4(), battery=BatteryLevel(80))
    s.start_rent()
    with pytest.raises(DomainInvariantViolation):
        s.send_to_maintenance()


# ---------- Агрегат Trip ----------

def test_trip_finish_before_start_fails():
    t0 = datetime(2026, 9, 1, 12, 0)
    trip = Trip(
        id=uuid4(),
        scooter_id=uuid4(),
        user_id=uuid4(),
        tariff=make_tariff(),
        started_at=t0,
    )
    with pytest.raises(DomainInvariantViolation):
        trip.finish(t0 - timedelta(minutes=1))


def test_trip_finish_twice_fails():
    t0 = datetime(2026, 9, 1, 12, 0)
    trip = Trip(
        id=uuid4(),
        scooter_id=uuid4(),
        user_id=uuid4(),
        tariff=make_tariff(),
        started_at=t0,
    )
    trip.finish(t0 + timedelta(minutes=10))
    with pytest.raises(DomainInvariantViolation):
        trip.finish(t0 + timedelta(minutes=20))


# ---------- Доменные сервисы ----------

def test_start_and_finish_trip_full_flow():
    scooters = InMemoryScooterRepository()
    trips = InMemoryTripRepository()
    s = Scooter(id=uuid4(), battery=BatteryLevel(80))
    scooters.save(s)

    start = StartTripService(scooters, trips)
    finish = FinishTripService(scooters, trips)
    t0 = datetime(2026, 9, 1, 12, 0)

    trip = start.start(s.id, uuid4(), make_tariff(), t0)
    assert scooters.get(s.id).status == ScooterStatus.RENTED

    trip = finish.finish(trip.id, t0 + timedelta(minutes=12))
    assert scooters.get(s.id).status == ScooterStatus.FREE
    assert trip.cost.amount == Decimal("60")


def test_start_trip_on_low_battery_fails():
    scooters = InMemoryScooterRepository()
    trips = InMemoryTripRepository()
    s = Scooter(id=uuid4(), battery=BatteryLevel(5))
    scooters.save(s)

    start = StartTripService(scooters, trips)
    with pytest.raises(DomainInvariantViolation):
        start.start(s.id, uuid4(), make_tariff(), datetime(2026, 9, 1, 12, 0))