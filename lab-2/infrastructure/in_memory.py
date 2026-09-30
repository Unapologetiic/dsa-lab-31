from uuid import UUID

from domain.library.book import Book
from domain.library.loan import Loan
from domain.scooter.scooter import Scooter
from domain.scooter.trip import Trip


class InMemoryBookRepository:
    def __init__(self) -> None:
        self._data: dict[UUID, Book] = {}

    def get(self, book_id: UUID) -> Book | None:
        return self._data.get(book_id)

    def save(self, book: Book) -> None:
        self._data[book.id] = book


class InMemoryLoanRepository:
    def __init__(self) -> None:
        self._data: dict[UUID, Loan] = {}

    def get(self, loan_id: UUID) -> Loan | None:
        return self._data.get(loan_id)

    def save(self, loan: Loan) -> None:
        self._data[loan.id] = loan

    def find_open_loan(self, book_id: UUID, reader_id: UUID) -> Loan | None:
        for loan in self._data.values():
            if (loan.book_id == book_id
                    and loan.reader_id.value == reader_id
                    and not loan.is_closed):
                return loan
        return None


class InMemoryScooterRepository:
    def __init__(self) -> None:
        self._data: dict[UUID, Scooter] = {}

    def get(self, scooter_id: UUID) -> Scooter | None:
        return self._data.get(scooter_id)

    def save(self, scooter: Scooter) -> None:
        self._data[scooter.id] = scooter


class InMemoryTripRepository:
    def __init__(self) -> None:
        self._data: dict[UUID, Trip] = {}

    def get(self, trip_id: UUID) -> Trip | None:
        return self._data.get(trip_id)

    def save(self, trip: Trip) -> None:
        self._data[trip.id] = trip

    def find_active_by_scooter(self, scooter_id: UUID) -> Trip | None:
        for trip in self._data.values():
            if trip.scooter_id == scooter_id and trip.finished_at is None:
                return trip
        return None