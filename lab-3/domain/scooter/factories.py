import math
from datetime import datetime, timedelta
from uuid import UUID

from domain.exceptions import DomainInvariantViolation
from domain.scooter.scooter import Scooter
from domain.scooter.trip import PREAUTH_AMOUNT, Trip
from domain.scooter.trip_states import STATE_BY_NAME
from domain.scooter.value_objects import BatteryLevel, ScooterStatus, Tariff, TripPeriod
from domain.shared.money import Money


class ScooterFactory:
    """Фабрика восстановления агрегата Scooter."""

    @staticmethod
    def restore(id: UUID, battery_percent: int,
                status: ScooterStatus = ScooterStatus.FREE) -> Scooter:
        # BatteryLevel сам валидирует диапазон [0; 100]
        return Scooter(id=id, battery=BatteryLevel(battery_percent), status=status)


class TripFactory:
    """Фабрика восстановления агрегата Trip.

    Первые семь параметров совпадают с ЛР №2. Если состояние не передано,
    оно выводится из данных: нет started_at — «Забронирована», есть started_at
    без finished_at — «В пути», есть finished_at — «Завершена».
    """

    @staticmethod
    def restore(id: UUID, scooter_id: UUID, user_id: UUID, tariff: Tariff,
                started_at: datetime | None = None,
                finished_at: datetime | None = None,
                cost: Money | None = None,
                *, reserved_at: datetime | None = None,
                state_name: str | None = None,
                preauth_amount: Money | None = None,
                lock_unlocked: bool | None = None,
                billing_started: bool | None = None,
                paused_total: timedelta = timedelta(0)) -> Trip:
        if state_name is None:
            if started_at is None:
                state_name = "Забронирована"
            elif finished_at is None:
                state_name = "В пути"
            else:
                state_name = "Завершена"
        if state_name not in STATE_BY_NAME:
            raise DomainInvariantViolation(f"Неизвестное состояние поездки: {state_name}")
        began = state_name not in ("Забронирована", "Бронь снята",
                                   "Отклонена (задолженность)", "Отклонена (платёж)")
        if reserved_at is None:
            reserved_at = started_at
        if reserved_at is None:
            raise DomainInvariantViolation("Не указано время бронирования или начала поездки")
        trip = Trip(id, scooter_id, user_id, tariff, reserved_at)
        trip._state = STATE_BY_NAME[state_name]()
        trip.started_at = started_at
        trip.finished_at = finished_at
        trip.preauth_amount = preauth_amount if preauth_amount is not None else (
            PREAUTH_AMOUNT if began or state_name == "Проверена" else None)
        past_check = began or state_name == "Проверена"
        trip.lock_unlocked = past_check if lock_unlocked is None else lock_unlocked
        trip.billing_started = past_check if billing_started is None else billing_started
        trip.paused_total = paused_total
        if finished_at is not None:
            if started_at is None:
                raise DomainInvariantViolation("Поездка не может быть завершена без начала")
            period = TripPeriod(started_at, finished_at)
            paused = min(math.ceil(paused_total.total_seconds() / 60), period.minutes)
            trip.cost = cost if cost is not None else tariff.calculate(period.minutes, paused)
        else:
            trip.cost = cost
        return trip
