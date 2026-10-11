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

    def _check_battery(self) -> None:
        if self.battery.is_below(MIN_BATTERY_TO_RENT):
            raise DomainInvariantViolation("Уровень заряда ниже минимального порога")

    def reserve(self) -> None:
        if self.status != ScooterStatus.FREE:
            raise DomainInvariantViolation(
                f"Нельзя забронировать самокат в статусе {self.status.value}"
            )
        self._check_battery()
        self.status = ScooterStatus.RESERVED

    def release_reservation(self) -> None:
        if self.status != ScooterStatus.RESERVED:
            raise DomainInvariantViolation("Самокат не забронирован")
        self.status = ScooterStatus.FREE

    def start_rent(self) -> None:
        if self.status not in (ScooterStatus.FREE, ScooterStatus.RESERVED):
            raise DomainInvariantViolation(
                f"Нельзя арендовать самокат в статусе {self.status.value}"
            )
        self._check_battery()
        self.status = ScooterStatus.RENTED

    def finish_rent(self) -> None:
        if self.status != ScooterStatus.RENTED:
            raise DomainInvariantViolation("Самокат не арендован")
        self.status = ScooterStatus.FREE

    def send_to_maintenance(self) -> None:
        if self.status in (ScooterStatus.RENTED, ScooterStatus.RESERVED):
            raise DomainInvariantViolation(
                "Нельзя отправить на обслуживание арендованный самокат"
            )
        self.status = ScooterStatus.MAINTENANCE
