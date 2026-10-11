class DomainError(Exception):
    """Базовое исключение доменного слоя."""


class DomainInvariantViolation(DomainError):
    """Нарушен инвариант агрегата."""


class InvalidValueObject(DomainError):
    """Некорректное значение value object."""


class EntityNotFound(DomainError):
    """Сущность не найдена в репозитории."""


class TransitionNotAllowed(DomainError):
    """Событие недопустимо в текущем состоянии сущности."""

    def __init__(self, state: str, event: str) -> None:
        self.state = state
        self.event = event
        super().__init__(f"Событие {event} недопустимо в состоянии «{state}»")
