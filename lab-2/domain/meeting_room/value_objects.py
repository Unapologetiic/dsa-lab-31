from dataclasses import dataclass
from datetime import time

from domain.exceptions import InvalidValueObject
from domain.shared.time_period import TimePeriod


@dataclass(frozen=True)
class Capacity:
    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise InvalidValueObject("Вместимость должна быть > 0")

    def can_fit(self, participants: int) -> bool:
        return participants <= self.value


@dataclass(frozen=True)
class WorkingHours:
    open_at: time
    close_at: time

    def __post_init__(self) -> None:
        if self.close_at <= self.open_at:
            raise InvalidValueObject("Время закрытия должно быть позже открытия")

    def contains(self, period: TimePeriod) -> bool:
        return (
            self.open_at <= period.start.time()
            and period.end.time() <= self.close_at
        )