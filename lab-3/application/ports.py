from datetime import datetime
from typing import Protocol
from uuid import UUID

from domain.scooter.value_objects import Location
from domain.shared.money import Money


class Clock(Protocol):
    """Источник текущего времени. datetime.now() в домене и сервисах не используется."""

    def now(self) -> datetime: ...


class PaymentGateway(Protocol):
    """Внешний участник «Платёжная система»."""

    def preauthorize(self, user_id: UUID, amount: Money) -> bool: ...
    def charge(self, user_id: UUID, amount: Money) -> bool: ...


class ScooterLock(Protocol):
    """Замок самоката."""

    def unlock(self, scooter_id: UUID) -> None: ...


class ParkingZones(Protocol):
    """Справочник разрешённых зон парковки."""

    def is_allowed(self, location: Location) -> bool: ...
