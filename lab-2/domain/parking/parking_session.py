from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from domain.exceptions import DomainInvariantViolation
from domain.parking.value_objects import ParkingPeriod, Tariff
from domain.shared.money import Money


@dataclass
class ParkingSession:
    """Агрегат «Парковочная сессия». Ссылается на ParkingSpot по spot_id."""

    id: UUID
    spot_id: UUID
    vehicle_plate: str
    tariff: Tariff
    entered_at: datetime
    exited_at: datetime | None = None
    cost: Money | None = None

    @property
    def is_closed(self) -> bool:
        return self.exited_at is not None

    def close(self, exited_at: datetime) -> None:
        if self.is_closed:
            raise DomainInvariantViolation("Сессия уже закрыта")
        period = ParkingPeriod(self.entered_at, exited_at)
        self.exited_at = exited_at
        self.cost = self.tariff.calculate(period.hours)