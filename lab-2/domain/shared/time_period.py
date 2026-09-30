from dataclasses import dataclass
from datetime import datetime

from domain.exceptions import InvalidValueObject


@dataclass(frozen=True)
class TimePeriod:
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise InvalidValueObject("Конец интервала должен быть позже начала")

    def overlaps(self, other: "TimePeriod") -> bool:
        return self.start < other.end and other.start < self.end