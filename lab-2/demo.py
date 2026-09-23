from datetime import datetime, time as dtime, timedelta
from decimal import Decimal
from uuid import uuid4

from domain.exceptions import DomainError

# --- library ---
from domain.library.book import Book
from domain.library.services import CheckoutService, ReturnService
from domain.library.value_objects import LoanPeriod, ReaderId

# --- scooter ---
from domain.scooter.scooter import Scooter
from domain.scooter.services import FinishTripService, StartTripService
from domain.scooter.value_objects import (
    BatteryLevel,
    ScooterStatus,
    Tariff as ScooterTariff,
)

# --- meeting_room ---
from domain.meeting_room.room import Room
from domain.meeting_room.services import CreateBookingService
from domain.meeting_room.value_objects import Capacity, WorkingHours

# --- parking ---
from domain.parking.parking_spot import ParkingSpot
from domain.parking.services import CloseParkingService, StartParkingService
from domain.parking.value_objects import Tariff as ParkingTariff

from domain.shared.money import Money
from domain.shared.time_period import TimePeriod

from infrastructure.in_memory import (
    InMemoryBookRepository,
    InMemoryBookingRepository,
    InMemoryLoanRepository,
    InMemoryParkingSessionRepository,
    InMemoryParkingSpotRepository,
    InMemoryRoomRepository,
    InMemoryScooterRepository,
    InMemoryTripRepository,
)


def demo_library() -> None:
    print("=== Библиотека ===")
    books = InMemoryBookRepository()
    loans = InMemoryLoanRepository()
    book_id = uuid4()
    books.save(Book(id=book_id, title="DDD", total_copies=1, available_copies=1))

    checkout = CheckoutService(books, loans)
    return_svc = ReturnService(books, loans)
    reader = ReaderId(uuid4())
    issue = datetime(2026, 9, 1, 10, 0)
    due = issue + timedelta(days=14)

    loan = checkout.checkout(book_id, reader, LoanPeriod(issue, due))
    print(f"Выдана книга, loan.id={loan.id}")

    try:
        checkout.checkout(book_id, ReaderId(uuid4()), LoanPeriod(issue, due))
    except DomainError as e:
        print(f"Ожидаемая ошибка: {e}")

    returned_at = due + timedelta(days=3)
    loan = return_svc.return_book(book_id, reader, returned_at)
    print(f"Штраф: {loan.fine.amount.amount} {loan.fine.amount.currency}")


def demo_scooter() -> None:
    print("\n=== Прокат самокатов ===")
    scooters = InMemoryScooterRepository()
    trips = InMemoryTripRepository()
    scooter_id = uuid4()
    scooters.save(Scooter(id=scooter_id, battery=BatteryLevel(80)))

    tariff = ScooterTariff(
        price_per_minute=Money(Decimal("5")),
        min_price=Money(Decimal("30")),
    )
    start = StartTripService(scooters, trips)
    finish = FinishTripService(scooters, trips)
    started = datetime(2026, 9, 1, 12, 0)

    trip = start.start(scooter_id, uuid4(), tariff, started)
    print(f"Поездка начата, trip.id={trip.id}")

    finished = started + timedelta(minutes=12)
    trip = finish.finish(trip.id, finished)
    print(f"Стоимость поездки: {trip.cost.amount} {trip.cost.currency}")


def demo_meeting_room() -> None:
    print("\n=== Бронирование переговорных ===")
    rooms = InMemoryRoomRepository()
    bookings = InMemoryBookingRepository()

    room_id = uuid4()
    rooms.save(Room(
        id=room_id,
        name="Переговорная №1",
        capacity=Capacity(10),
        working_hours=WorkingHours(dtime(9, 0), dtime(18, 0)),
    ))

    svc = CreateBookingService(rooms, bookings)

    b1 = svc.create(
        room_id=room_id,
        employee_id=uuid4(),
        period=TimePeriod(
            datetime(2026, 9, 1, 10, 0),
            datetime(2026, 9, 1, 11, 0),
        ),
        participants=4,
    )
    print(f"Бронь создана, booking.id={b1.id}")

    try:
        svc.create(
            room_id=room_id,
            employee_id=uuid4(),
            period=TimePeriod(
                datetime(2026, 9, 1, 10, 30),
                datetime(2026, 9, 1, 11, 30),
            ),
            participants=4,
        )
    except DomainError as e:
        print(f"Ожидаемая ошибка: {e}")

    try:
        svc.create(
            room_id=room_id,
            employee_id=uuid4(),
            period=TimePeriod(
                datetime(2026, 9, 1, 14, 0),
                datetime(2026, 9, 1, 15, 0),
            ),
            participants=99,
        )
    except DomainError as e:
        print(f"Ожидаемая ошибка: {e}")


def demo_parking() -> None:
    print("\n=== Парковка ===")
    spots = InMemoryParkingSpotRepository()
    sessions = InMemoryParkingSessionRepository()
    spot_id = uuid4()
    spots.save(ParkingSpot(id=spot_id, number="A-1"))

    tariff = ParkingTariff(price_per_hour=Money(Decimal("100")))
    start = StartParkingService(spots, sessions)
    close = CloseParkingService(spots, sessions)

    entered = datetime(2026, 9, 1, 9, 0)
    session = start.start(spot_id, "A123BC", tariff, entered)
    print(f"Сессия открыта, session.id={session.id}")

    exited = entered + timedelta(hours=1, minutes=30)
    session = close.close(session.id, exited)
    print(f"Стоимость стоянки: {session.cost.amount} {session.cost.currency}")


if __name__ == "__main__":
    demo_library()
    demo_scooter()
    demo_meeting_room()
    demo_parking()