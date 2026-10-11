"""Демонстрация процесса: основной путь P1 и срабатывание таймера брони (P2)."""
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from application.rental_process import RentalProcess
from domain.scooter.factories import ScooterFactory
from domain.scooter.user_account import UserAccount
from domain.scooter.value_objects import Location, Tariff
from domain.shared.money import Money
from infrastructure.in_memory import (InMemoryParkingZones, ManualClock, InMemoryPaymentGateway,
                                      InMemoryScooterLock, InMemoryScooterRepository,
                                      InMemoryTripRepository, InMemoryUserAccountRepository)


def build():
    scooters, accounts = InMemoryScooterRepository(), InMemoryUserAccountRepository()
    clock = ManualClock(datetime(2026, 10, 1, 10, 0))
    tariff = Tariff(Money(Decimal("5")), Money(Decimal("10")), Money(Decimal("2")))
    process = RentalProcess(scooters, InMemoryTripRepository(), accounts, InMemoryPaymentGateway(),
                            InMemoryScooterLock(), InMemoryParkingZones([(55.0, 55.1, 82.8, 83.0)]),
                            clock, tariff)
    user, scooter = uuid4(), uuid4()
    accounts.save(UserAccount(user))
    scooters.save(ScooterFactory.restore(scooter, 80))
    return process, clock, user, scooter


def show(trip):
    print(f"Состояние: {trip.status}; допустимые события: {sorted(trip.allowed_events)}")
    for e in trip.events:
        print("  ", type(e).__name__, e.occurred_at.strftime("%H:%M"))


if __name__ == "__main__":
    process, clock, user, scooter = build()
    print("P1: основной путь")
    trip = process.book_scooter(user, scooter)
    clock.advance(timedelta(minutes=2))
    process.request_ride_start(trip.id)
    clock.advance(timedelta(minutes=30))
    process.receive_client_request(trip.id, "finish", Location(55.03, 82.92))
    show(process.receive_finish_photo(trip.id, "photo.jpg"))

    process, clock, user, scooter = build()
    print("\nP2: бронь без поездки")
    trip = process.book_scooter(user, scooter)
    clock.advance(timedelta(minutes=10))
    process.on_tick()
    show(process._trip(trip.id))
