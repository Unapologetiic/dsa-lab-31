from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from domain.exceptions import InvalidValueObject
from domain.shared.money import Money


class ScooterStatus(str, Enum):
    FREE = "free"
    RESERVED = "reserved"
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
class Location:
    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        if not (-90 <= self.latitude <= 90) or not (-180 <= self.longitude <= 180):
            raise InvalidValueObject("Некорректные координаты")


@dataclass(frozen=True)
class Tariff:
    price_per_minute: Money
    min_price: Money
    pause_price_per_minute: Money | None = None

    def __post_init__(self) -> None:
        if self.min_price.amount < self.price_per_minute.amount:
            raise InvalidValueObject(
                "Минимальная стоимость не может быть меньше цены за минуту"
            )
        if self.pause_price_per_minute is None:
            object.__setattr__(self, "pause_price_per_minute", self.price_per_minute)
        elif self.pause_price_per_minute.amount > self.price_per_minute.amount:
            raise InvalidValueObject("Ставка паузы не может быть выше обычной")

    def calculate(self, minutes: int, paused_minutes: int = 0) -> Money:
        if minutes < 0:
            raise InvalidValueObject("Число минут не может быть отрицательным")
        if paused_minutes < 0 or paused_minutes > minutes:
            raise InvalidValueObject("Минуты паузы должны быть в [0; минуты поездки]")
        raw = self.price_per_minute * Decimal(minutes - paused_minutes)
        raw = raw + self.pause_price_per_minute * Decimal(paused_minutes)
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
        return max(1, int(delta.total_seconds() // 60) + (1 if delta.seconds % 60 else 0))
