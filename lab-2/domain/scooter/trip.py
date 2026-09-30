from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from domain.exceptions import DomainInvariantViolation
from domain.scooter.value_objects import Tariff, TripPeriod
from domain.shared.money import Money


@dataclass
class Trip:
    """Агрегат «Поездка». Ссылается на Scooter по scooter_id."""

    id: UUID
    scooter_id: UUID
    user_id: UUID
    tariff: Tariff
    started_at: datetime
    finished_at: datetime | None = None
    cost: Money | None = None

    def finish(self, finished_at: datetime) -> None:
        if self.finished_at is not None:
            raise DomainInvariantViolation("Поездка уже завершена")
        if finished_at < self.started_at:
            raise DomainInvariantViolation("Завершение раньше начала")
        period = TripPeriod(self.started_at, finished_at)
        self.finished_at = finished_at
        self.cost = self.tariff.calculate(period.minutes)