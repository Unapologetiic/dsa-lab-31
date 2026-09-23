from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_CEILING
from enum import Enum

from domain.exceptions import InvalidValueObject
from domain.shared.money import Money


class SpotStatus(str, Enum):
    FREE = "free"
    OCCUPIED = "occupied"


@dataclass(frozen=True)
class Tariff:
    price_per_hour: Money

    def __post_init__(self) -> None:
        if self.price_per_hour.amount <= 0:
            raise InvalidValueObject("Цена за час должна быть > 0")

    def calculate(self, hours: Decimal) -> Money:
        if hours <= 0:
            raise InvalidValueObject("Длительность должна быть > 0")
        rounded = hours.to_integral_value(rounding=ROUND_CEILING)
        return self.price_per_hour * rounded


@dataclass(frozen=True)
class ParkingPeriod:
    entered_at: datetime
    exited_at: datetime

    def __post_init__(self) -> None:
        if self.exited_at <= self.entered_at:
            raise InvalidValueObject("Выезд не может быть раньше въезда")

    @property
    def hours(self) -> Decimal:
        seconds = (self.exited_at - self.entered_at).total_seconds()
        return Decimal(seconds) / Decimal(3600)