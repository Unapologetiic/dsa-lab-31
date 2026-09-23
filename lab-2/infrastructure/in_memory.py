from uuid import UUID

# --- library ---
from domain.library.book import Book
from domain.library.loan import Loan

# --- scooter ---
from domain.scooter.scooter import Scooter
from domain.scooter.trip import Trip

# --- meeting_room ---
from domain.meeting_room.booking import Booking
from domain.meeting_room.room import Room

# --- parking ---
from domain.parking.parking_session import ParkingSession
from domain.parking.parking_spot import ParkingSpot


# =========================== library ===========================

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


# =========================== scooter ===========================

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


# ========================= meeting_room ========================

class InMemoryRoomRepository:
    def __init__(self) -> None:
        self._data: dict[UUID, Room] = {}

    def get(self, room_id: UUID) -> Room | None:
        return self._data.get(room_id)

    def save(self, room: Room) -> None:
        self._data[room.id] = room


class InMemoryBookingRepository:
    def __init__(self) -> None:
        self._data: dict[UUID, Booking] = {}

    def get(self, booking_id: UUID) -> Booking | None:
        return self._data.get(booking_id)

    def save(self, booking: Booking) -> None:
        self._data[booking.id] = booking

    def find_by_room(self, room_id: UUID) -> list[Booking]:
        return [b for b in self._data.values() if b.room_id == room_id]


# ========================== parking ============================

class InMemoryParkingSpotRepository:
    def __init__(self) -> None:
        self._data: dict[UUID, ParkingSpot] = {}

    def get(self, spot_id: UUID) -> ParkingSpot | None:
        return self._data.get(spot_id)

    def save(self, spot: ParkingSpot) -> None:
        self._data[spot.id] = spot


class InMemoryParkingSessionRepository:
    def __init__(self) -> None:
        self._data: dict[UUID, ParkingSession] = {}

    def get(self, session_id: UUID) -> ParkingSession | None:
        return self._data.get(session_id)

    def save(self, session: ParkingSession) -> None:
        self._data[session.id] = session

    def find_active_by_spot(self, spot_id: UUID) -> ParkingSession | None:
        for s in self._data.values():
            if s.spot_id == spot_id and not s.is_closed:
                return s
        return None