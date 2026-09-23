from dataclasses import dataclass
from uuid import UUID

from domain.exceptions import DomainInvariantViolation
from domain.meeting_room.value_objects import Capacity, WorkingHours
from domain.shared.time_period import TimePeriod


@dataclass
class Booking:
    """Агрегат «Бронь». Ссылается на Room по room_id."""

    id: UUID
    room_id: UUID
    employee_id: UUID
    period: TimePeriod
    participants: int
    is_cancelled: bool = False

    def validate_against_room(
        self, capacity: Capacity, hours: WorkingHours
    ) -> None:
        if self.is_cancelled:
            raise DomainInvariantViolation("Бронь отменена")
        if not capacity.can_fit(self.participants):
            raise DomainInvariantViolation(
                "Число участников превышает вместимость комнаты"
            )
        if not hours.contains(self.period):
            raise DomainInvariantViolation(
                "Бронь выходит за пределы часов работы офиса"
            )

    def cancel(self) -> None:
        if self.is_cancelled:
            raise DomainInvariantViolation("Бронь уже отменена")
        self.is_cancelled = True