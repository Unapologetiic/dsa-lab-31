"""Иерархия доменных исключений.

Технические ошибки (FileNotFoundError, ConnectionError и т.п.)
сюда не входят — они не относятся к бизнес-правилам.
"""


class DomainError(Exception):
    """Базовое исключение доменного слоя."""


class DomainInvariantViolation(DomainError):
    """Нарушен инвариант агрегата."""


class InvalidValueObject(DomainError):
    """Некорректное значение value object."""


class EntityNotFound(DomainError):
    """Сущность не найдена в репозитории."""