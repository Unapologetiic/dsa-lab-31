from uuid import UUID, uuid4

from domain.exceptions import DomainInvariantViolation, EntityNotFound
from domain.meeting_room.booking import Booking
from domain.meeting_room.repositories import BookingRepository, RoomRepository
from domain.shared.time_period import TimePeriod


class CreateBookingService:
    """Создание брони: затрагивает Room и Booking, а также проверяет
    пересечения с другими бронями той же комнаты."""

    def __init__(self, rooms: RoomRepository, bookings: BookingRepository) -> None:
        self._rooms = rooms
        self._bookings = bookings

    def create(
        self,
        room_id: UUID,
        employee_id: UUID,
        period: TimePeriod,
        participants: int,
    ) -> Booking:
        room = self._rooms.get(room_id)
        if room is None:
            raise EntityNotFound("Комната не найдена")

        booking = Booking(
            id=uuid4(),
            room_id=room_id,
            employee_id=employee_id,
            period=period,
            participants=participants,
        )
        booking.validate_against_room(room.capacity, room.working_hours)

        for existing in self._bookings.find_by_room(room_id):
            if existing.is_cancelled:
                continue
            if existing.period.overlaps(period):
                raise DomainInvariantViolation(
                    "Бронь пересекается с уже существующей"
                )

        self._bookings.save(booking)
        return booking