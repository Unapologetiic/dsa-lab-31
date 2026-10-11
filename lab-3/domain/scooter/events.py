from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from domain.scooter.value_objects import Location
from domain.shared.money import Money


@dataclass(frozen=True)
class ReservationConfirmed:
    """Сообщение клиенту: подтверждение брони."""

    trip_id: UUID
    occurred_at: datetime
    scooter_id: UUID

@dataclass(frozen=True)
class ReservationExpired:
    """Сработал таймер 10 минут."""

    trip_id: UUID
    occurred_at: datetime

@dataclass(frozen=True)
class RideRejectedByDebt:
    """Отказ: у клиента есть задолженность."""

    trip_id: UUID
    occurred_at: datetime

@dataclass(frozen=True)
class RideRejectedByPayment:
    """Отказ: предавторизация не прошла."""

    trip_id: UUID
    occurred_at: datetime

@dataclass(frozen=True)
class PreauthorizationApproved:
    """Платёжная система подтвердила предавторизацию."""

    trip_id: UUID
    occurred_at: datetime
    amount: Money

@dataclass(frozen=True)
class LockUnlocked:
    """Замок разблокирован."""

    trip_id: UUID
    occurred_at: datetime

@dataclass(frozen=True)
class BillingStarted:
    """Тарификация запущена."""

    trip_id: UUID
    occurred_at: datetime

@dataclass(frozen=True)
class RideStarted:
    """Поездка начата."""

    trip_id: UUID
    occurred_at: datetime

@dataclass(frozen=True)
class RidePaused:
    """Поездка поставлена на паузу."""

    trip_id: UUID
    occurred_at: datetime

@dataclass(frozen=True)
class BillingRateChanged:
    """Смена ставки: pause или regular."""

    trip_id: UUID
    occurred_at: datetime
    rate: str

@dataclass(frozen=True)
class RideResumed:
    """Поездка возобновлена."""

    trip_id: UUID
    occurred_at: datetime

@dataclass(frozen=True)
class ParkingZoneViolation:
    """Сообщение клиенту: запрещённая зона."""

    trip_id: UUID
    occurred_at: datetime
    location: Location

@dataclass(frozen=True)
class FinishPhotoReceived:
    """Получено фото самоката."""

    trip_id: UUID
    occurred_at: datetime
    photo_ref: str

@dataclass(frozen=True)
class RideFinished:
    """Поездка завершена."""

    trip_id: UUID
    occurred_at: datetime

@dataclass(frozen=True)
class CostCalculated:
    """Стоимость рассчитана."""

    trip_id: UUID
    occurred_at: datetime
    cost: Money

@dataclass(frozen=True)
class TripCharged:
    """Стоимость списана."""

    trip_id: UUID
    occurred_at: datetime
    amount: Money

@dataclass(frozen=True)
class ChargeFailed:
    """Списание не прошло."""

    trip_id: UUID
    occurred_at: datetime
    amount: Money

@dataclass(frozen=True)
class AccountBlockedNotified:
    """Сообщение клиенту: аккаунт заблокирован."""

    trip_id: UUID
    occurred_at: datetime

@dataclass(frozen=True)
class OperatorNotified:
    """Оператор уведомлён: поездка дольше 12 часов."""

    trip_id: UUID
    occurred_at: datetime

@dataclass(frozen=True)
class OperatorContacted:
    """Оператор связался с клиентом."""

    trip_id: UUID
    occurred_at: datetime
    result: str
