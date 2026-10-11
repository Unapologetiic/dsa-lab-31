import math
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from domain.exceptions import DomainInvariantViolation, TransitionNotAllowed
from domain.scooter import events as ev
from domain.scooter.trip_states import Booked, Paused, Riding, TripState, Unpaid
from domain.scooter.value_objects import Location, Tariff, TripPeriod
from domain.shared.money import Money

RESERVATION_TIMEOUT = timedelta(minutes=10)
LONG_RIDE_LIMIT = timedelta(hours=12)
PREAUTH_AMOUNT = Money(Decimal("300"))


class Trip:
    """Агрегат «Поездка». Жизненный цикл задаётся паттерном «Состояние».

    Текущее состояние хранится в закрытом атрибуте, публичного сеттера нет:
    изменить его можно только методами событий.
    """

    def __init__(self, id: UUID, scooter_id: UUID, user_id: UUID,
                 tariff: Tariff, reserved_at: datetime) -> None:
        self.id = id
        self.scooter_id = scooter_id
        self.user_id = user_id
        self.tariff = tariff
        self.reserved_at = reserved_at
        self.started_at: datetime | None = None
        self.finished_at: datetime | None = None
        self.cost: Money | None = None
        self.preauth_amount: Money | None = None
        self.lock_unlocked = False       # ветвь «Разблокировать замок» завершена
        self.billing_started = False     # ветвь «Запустить тарификацию» завершена
        self.zone_confirmed = False
        self.finish_photo: str | None = None
        self.pause_started_at: datetime | None = None
        self.paused_total = timedelta(0)
        self.billing_rate = "regular"
        self.operator_notified = False
        self._state: TripState = Booked()
        self._events: list = []

    @classmethod
    def book(cls, id: UUID, scooter_id: UUID, user_id: UUID,
             tariff: Tariff, reserved_at: datetime) -> "Trip":
        trip = cls(id, scooter_id, user_id, tariff, reserved_at)
        trip._events.append(ev.ReservationConfirmed(id, reserved_at, scooter_id))
        return trip

    # ---- чтение состояния
    @property
    def status(self) -> str:
        return self._state.name

    @property
    def allowed_events(self) -> frozenset[str]:
        return self._state.allowed

    @property
    def is_active(self) -> bool:
        return not self._state.final

    @property
    def events(self) -> tuple:
        return tuple(self._events)

    def _require(self, event: str) -> None:
        if event not in self._state.allowed:
            raise TransitionNotAllowed(self._state.name, event)

    # ---- события таймера
    def on_reservation_expired(self, now: datetime) -> None:
        if now - self.reserved_at < RESERVATION_TIMEOUT:
            return
        self._state = self._state.expire_reservation(self)
        self._events.append(ev.ReservationExpired(self.id, now))

    def on_ride_too_long(self, now: datetime) -> None:
        if self.started_at is None or self.operator_notified:
            return
        if now - self.started_at < LONG_RIDE_LIMIT:
            return
        self._state = self._state.on_ride_too_long(self)
        self.operator_notified = True
        self._events.append(ev.OperatorNotified(self.id, now))

    # ---- проверки перед стартом
    def reject_debt(self, now: datetime) -> None:
        self._state = self._state.reject_debt(self)
        self._events.append(ev.RideRejectedByDebt(self.id, now))

    def record_preauthorization(self, amount: Money, now: datetime) -> None:
        self._require("authorize")
        if amount != PREAUTH_AMOUNT:
            raise DomainInvariantViolation("Сумма предавторизации должна быть 300 руб.")
        self.preauth_amount = amount
        self._events.append(ev.PreauthorizationApproved(self.id, now, amount))

    def authorize(self, now: datetime) -> None:
        self._state = self._state.authorize(self)

    def reject_payment(self, now: datetime) -> None:
        self._state = self._state.reject_payment(self)
        self._events.append(ev.RideRejectedByPayment(self.id, now))

    # ---- параллельные ветви перед стартом
    def mark_lock_unlocked(self, now: datetime) -> None:
        self._require("start_ride")
        self.lock_unlocked = True
        self._events.append(ev.LockUnlocked(self.id, now))

    def start_billing(self, now: datetime) -> None:
        self._require("start_ride")
        self.billing_started = True
        self._events.append(ev.BillingStarted(self.id, now))

    def start_ride(self, now: datetime) -> None:
        new_state = self._state.start_ride(self)
        self._state = new_state
        self.started_at = now
        self._events.append(ev.RideStarted(self.id, now))

    # ---- пауза
    def pause(self, now: datetime) -> None:
        new_state = self._state.pause(self)
        self._state = new_state
        self.pause_started_at = now
        self.zone_confirmed = False
        self.finish_photo = None
        self._events.append(ev.RidePaused(self.id, now))

    def switch_to_pause_rate(self, now: datetime) -> None:
        if not isinstance(self._state, Paused):
            raise TransitionNotAllowed(self._state.name, "switch_to_pause_rate")
        self.billing_rate = "pause"
        self._events.append(ev.BillingRateChanged(self.id, now, "pause"))

    def resume(self, now: datetime) -> None:
        new_state = self._state.resume(self)
        self._state = new_state
        self.paused_total += now - self.pause_started_at
        self.pause_started_at = None
        self._events.append(ev.RideResumed(self.id, now))

    def switch_to_regular_rate(self, now: datetime) -> None:
        if not isinstance(self._state, Riding):
            raise TransitionNotAllowed(self._state.name, "switch_to_regular_rate")
        self.billing_rate = "regular"
        self._events.append(ev.BillingRateChanged(self.id, now, "regular"))

    # ---- завершение
    def confirm_parking_zone(self) -> None:
        self._require("finish")
        self.zone_confirmed = True

    def report_forbidden_zone(self, now: datetime, location: Location) -> None:
        self._require("finish")
        self.zone_confirmed = False
        self._events.append(ev.ParkingZoneViolation(self.id, now, location))

    def attach_finish_photo(self, photo_ref: str, now: datetime) -> None:
        self._require("finish")
        if not self.zone_confirmed:
            raise DomainInvariantViolation("Сначала нужно подтвердить зону парковки")
        if not photo_ref or not photo_ref.strip():
            raise DomainInvariantViolation("Фото самоката не может быть пустым")
        self.finish_photo = photo_ref
        self._events.append(ev.FinishPhotoReceived(self.id, now, photo_ref))

    def finish(self, now: datetime) -> None:
        if self.started_at is not None and now < self.started_at:
            raise DomainInvariantViolation("Завершение раньше начала")
        new_state = self._state.finish(self)
        TripPeriod(self.started_at, now)
        self._state = new_state
        self.finished_at = now
        self._events.append(ev.RideFinished(self.id, now))

    def calculate_cost(self, now: datetime) -> Money:
        if self.finished_at is None:
            raise DomainInvariantViolation("Поездка не завершена")
        if self.cost is not None:
            raise DomainInvariantViolation("Стоимость поездки уже рассчитана")
        period = TripPeriod(self.started_at, self.finished_at)
        paused_minutes = min(math.ceil(self.paused_total.total_seconds() / 60), period.minutes)
        self.cost = self.tariff.calculate(period.minutes, paused_minutes)
        self._events.append(ev.CostCalculated(self.id, now, self.cost))
        return self.cost

    # ---- списание
    def charge_success(self, now: datetime) -> None:
        self._state = self._state.charge_success(self)
        self._events.append(ev.TripCharged(self.id, now, self.cost))

    def charge_fail(self, now: datetime) -> None:
        self._state = self._state.charge_fail(self)
        self._events.append(ev.ChargeFailed(self.id, now, self.cost))

    def notify_account_blocked(self, now: datetime) -> None:
        if not isinstance(self._state, Unpaid):
            raise TransitionNotAllowed(self._state.name, "notify_account_blocked")
        self._events.append(ev.AccountBlockedNotified(self.id, now))

    # ---- оператор
    def record_operator_contact(self, result: str, now: datetime) -> None:
        if not self.operator_notified:
            raise DomainInvariantViolation("Оператор не получал уведомление по этой поездке")
        self._events.append(ev.OperatorContacted(self.id, now, result))
