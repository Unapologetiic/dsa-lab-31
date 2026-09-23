from dataclasses import dataclass
from uuid import UUID

from domain.exceptions import DomainInvariantViolation


@dataclass
class Book:
    """Агрегат «Книга». Инвариант: 0 <= available_copies <= total_copies."""

    id: UUID
    title: str
    total_copies: int
    available_copies: int

    def __post_init__(self) -> None:
        if self.total_copies <= 0:
            raise DomainInvariantViolation("Всего экземпляров должно быть > 0")
        if not (0 <= self.available_copies <= self.total_copies):
            raise DomainInvariantViolation(
                "Доступных экземпляров должно быть в [0; total_copies]"
            )

    def checkout(self) -> None:
        if self.available_copies <= 0:
            raise DomainInvariantViolation(
                "Нельзя выдать книгу: нет свободных экземпляров"
            )
        self.available_copies -= 1

    def return_copy(self) -> None:
        if self.available_copies >= self.total_copies:
            raise DomainInvariantViolation(
                "Все экземпляры уже в библиотеке"
            )
        self.available_copies += 1