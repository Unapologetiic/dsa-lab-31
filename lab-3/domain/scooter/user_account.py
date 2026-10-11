from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from domain.exceptions import DomainInvariantViolation
from domain.shared.money import Money


@dataclass
class UserAccount:
    """Агрегат «Аккаунт клиента»: задолженность и блокировка."""

    id: UUID
    debt: Money = field(default_factory=lambda: Money(Decimal("0")))
    blocked: bool = False

    def has_debt(self) -> bool:
        return self.debt.amount > 0

    def register_debt(self, amount: Money) -> None:
        if amount.amount <= 0:
            raise DomainInvariantViolation("Сумма задолженности должна быть положительной")
        self.debt = self.debt + amount

    def block(self) -> None:
        self.blocked = True

    def ensure_can_book(self) -> None:
        if self.blocked:
            raise DomainInvariantViolation("Аккаунт заблокирован до погашения задолженности")
