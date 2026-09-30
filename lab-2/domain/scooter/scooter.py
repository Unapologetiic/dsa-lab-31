from dataclasses import dataclass
from uuid import UUID

from domain.exceptions import DomainInvariantViolation
from domain.scooter.value_objects import BatteryLevel, ScooterStatus

MIN_BATTERY_TO_RENT = BatteryLevel(20)


@dataclass
class Scooter:
    """Агрегат «Самокат»."""

    id: UUID
    battery: BatteryLevel
    status: ScooterStatus = ScooterStatus.FREE

    def start_rent(self) -> None:
        if self.status != ScooterStatus.FREE:
            raise DomainInvariantViolation(
                f"Нельзя арендовать самокат в статусе {self.status.value}"
            )
        if self.battery.is_below(MIN_BATTERY_TO_RENT):
            raise DomainInvariantViolation("Уровень заряда ниже минимального порога")
        self.status = ScooterStatus.RENTED

    def finish_rent(self) -> None:
        if self.status != ScooterStatus.RENTED:
            raise DomainInvariantViolation("Самокат не арендован")
        self.status = ScooterStatus.FREE

    def send_to_maintenance(self) -> None:
        if self.status == ScooterStatus.RENTED:
            raise DomainInvariantViolation(
                "Нельзя отправить на обслуживание арендованный самокат"
            )
        self.status = ScooterStatus.MAINTENANCE