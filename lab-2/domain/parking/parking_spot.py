from dataclasses import dataclass
from uuid import UUID

from domain.exceptions import DomainInvariantViolation
from domain.parking.value_objects import SpotStatus


@dataclass
class ParkingSpot:
    """Агрегат «Парковочное место»."""

    id: UUID
    number: str
    status: SpotStatus = SpotStatus.FREE

    def occupy(self) -> None:
        if self.status == SpotStatus.OCCUPIED:
            raise DomainInvariantViolation("Место уже занято")
        self.status = SpotStatus.OCCUPIED

    def release(self) -> None:
        if self.status == SpotStatus.FREE:
            raise DomainInvariantViolation("Место уже свободно")
        self.status = SpotStatus.FREE