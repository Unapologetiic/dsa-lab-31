from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from domain.exceptions import DomainError
from domain.library.book import Book
from domain.library.factories import BookFactory
from domain.library.services import CheckoutService, ReturnService
from domain.library.value_objects import LoanPeriod, ReaderId
from domain.scooter.factories import ScooterFactory
from domain.scooter.scooter import Scooter
from domain.scooter.services import FinishTripService, StartTripService
from domain.scooter.value_objects import (
    BatteryLevel,
    Tariff as ScooterTariff,
)
from domain.shared.money import Money
from infrastructure.in_memory import (
    InMemoryBookRepository,
    InMemoryLoanRepository,
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

    # Проверка фабрики: повреждённые данные отклоняются
    try:
        BookFactory.restore(
            id=uuid4(),
            title="DDD",
            total_copies=1,
            available_copies=5,
        )
    except DomainError as e:
        print(f"Фабрика отклонила повреждённые данные: {e}")


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

    # Проверка фабрики: повреждённые данные отклоняются
    try:
        ScooterFactory.restore(
            id=uuid4(),
            battery_percent=150,   # некорректно, максимум 100
        )
    except DomainError as e:
        print(f"Фабрика отклонила повреждённые данные: {e}")


if __name__ == "__main__":
    demo_library()
    demo_scooter()