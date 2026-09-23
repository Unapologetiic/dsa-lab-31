from dataclasses import dataclass
from decimal import Decimal

from domain.exceptions import InvalidValueObject


@dataclass(frozen=True)
class Money:
    """Денежная сумма. Всегда неотрицательна."""

    amount: Decimal
    currency: str = "RUB"

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise InvalidValueObject("Money.amount должен быть Decimal")
        if self.amount < 0:
            raise InvalidValueObject("Money.amount не может быть отрицательным")
        if not self.currency or len(self.currency) != 3:
            raise InvalidValueObject("Валюта должна быть трёхбуквенным кодом")

    def __add__(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise InvalidValueObject("Нельзя складывать разные валюты")
        return Money(self.amount + other.amount, self.currency)

    def __mul__(self, factor: Decimal) -> "Money":
        if factor < 0:
            raise InvalidValueObject("Множитель не может быть отрицательным")
        return Money(self.amount * factor, self.currency)