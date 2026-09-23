from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from domain.exceptions import InvalidValueObject
from domain.shared.money import Money


class ScooterStatus(str, Enum):
    FREE = "free"
    RENTED = "rented"
    MAINTENANCE = "maintenance"


@dataclass(frozen=True)
class BatteryLevel:
    percent: int

    def __post_init__(self) -> None:
        if not (0 <= self.percent <= 100):
            raise InvalidValueObject("Уровень заряда должен быть в [0; 100]")

    def is_below(self, threshold: "BatteryLevel") -> bool:
        return self.percent < threshold.percent


@dataclass(frozen=True)
class Tariff:
    price_per_minute: Money
    min_price: Money

    def __post_init__(self) -> None:
        if self.min_price.amount < self.price_per_minute.amount:
            raise InvalidValueObject(
                "Минимальная стоимость не может быть меньше цены за минуту"
            )

    def calculate(self, minutes: int) -> Money:
        if minutes < 0:
            raise InvalidValueObject("Число минут не может быть отрицательным")
        raw = self.price_per_minute * Decimal(minutes)
        if raw.amount < self.min_price.amount:
            return self.min_price
        return raw


@dataclass(frozen=True)
class TripPeriod:
    started_at: datetime
    finished_at: datetime

    def __post_init__(self) -> None:
        if self.finished_at <= self.started_at:
            raise InvalidValueObject("Поездка не может закончиться раньше начала")

    @property
    def minutes(self) -> int:
        delta = self.finished_at - self.started_at
        # округление вверх до полной минуты
        return max(1, int(delta.total_seconds() // 60) + (1 if delta.seconds % 60 else 0))