from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from domain.exceptions import DomainInvariantViolation
from domain.library.value_objects import Fine, LoanPeriod, ReaderId


@dataclass
class Loan:
    """Агрегат «Выдача». Ссылается на Book по book_id."""

    id: UUID
    book_id: UUID
    reader_id: ReaderId
    period: LoanPeriod
    returned_at: datetime | None = None
    fine: Fine | None = None

    @property
    def is_closed(self) -> bool:
        return self.returned_at is not None

    def close(self, returned_at: datetime, fine: Fine | None = None) -> None:
        if self.is_closed:
            raise DomainInvariantViolation("Выдача уже закрыта возвратом")
        if returned_at < self.period.issue_date:
            raise DomainInvariantViolation("Возврат раньше выдачи")
        if self.period.is_overdue(returned_at) and fine is None:
            raise DomainInvariantViolation(
                "Просроченный возврат должен сопровождаться штрафом"
            )
        self.returned_at = returned_at
        self.fine = fine