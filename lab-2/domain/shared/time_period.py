from dataclasses import dataclass
from datetime import datetime

from domain.exceptions import InvalidValueObject


@dataclass(frozen=True)
class TimePeriod:
    """Интервал времени [start, end). start < end."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise InvalidValueObject(
                "Конец интервала должен быть позже начала"
            )

    def overlaps(self, other: "TimePeriod") -> bool:
        return self.start < other.end and other.start < self.end

    def contains(self, moment: datetime) -> bool:
        return self.start <= moment < self.end

    def is_inside(self, outer: "TimePeriod") -> bool:
        return outer.start <= self.start and self.end <= outer.end