from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from domain.exceptions import InvalidValueObject
from domain.shared.money import Money


@dataclass(frozen=True)
class ReaderId:
    value: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.value, UUID):
            raise InvalidValueObject("ReaderId должен быть UUID")


@dataclass(frozen=True)
class LoanPeriod:
    issue_date: datetime
    due_date: datetime

    def __post_init__(self) -> None:
        if self.due_date <= self.issue_date:
            raise InvalidValueObject("Срок возврата должен быть позже выдачи")

    def is_overdue(self, returned_at: datetime) -> bool:
        return returned_at > self.due_date


@dataclass(frozen=True)
class Fine:
    amount: Money

    def __post_init__(self) -> None:
        if self.amount.amount < 0:
            raise InvalidValueObject("Штраф не может быть отрицательным")