"""Прикладной сервис процесса «Аренда электросамоката».

Каждой задаче схемы BPMN соответствует метод с названием по задаче.
Состояние поездки меняется только методами событий агрегата Trip.
"""
from functools import partial
from uuid import UUID, uuid4

from application.ports import Clock, ParkingZones, PaymentGateway, ScooterLock
from domain.exceptions import DomainInvariantViolation, EntityNotFound, TransitionNotAllowed
from domain.scooter.repositories import ScooterRepository, TripRepository, UserAccountRepository
from domain.scooter.scooter import Scooter
from domain.scooter.trip import PREAUTH_AMOUNT, Trip
from domain.scooter.user_account import UserAccount
from domain.scooter.value_objects import Location, ScooterStatus, Tariff


class GatewayUnresolved(Exception):
    """Ни одно условие исключающего шлюза не выполнено, а потока по умолчанию нет."""


# ---- условия исключающих шлюзов схемы BPMN: по одной функции-предикату на условие
# Шлюз «Задолженность есть?»
def debt_exists(account: UserAccount) -> bool:
    return account.has_debt()


def no_debt(account: UserAccount) -> bool:
    return not account.has_debt()


# Шлюз «Предавторизация успешна?»
def preauthorization_succeeded(result: bool) -> bool:
    return result is True


def preauthorization_declined(result: bool) -> bool:
    return result is False


# Шлюз «Действие клиента?»
def pause_requested(action: str) -> bool:
    return action == "pause"


# Шлюз «Самокат в зоне парковки?»
def in_allowed_zone(zones, location: Location) -> bool:
    return zones.is_allowed(location) is True


def outside_allowed_zone(zones, location: Location) -> bool:
    return zones.is_allowed(location) is False


# Шлюз «Списание прошло?»
def charge_succeeded(result: bool) -> bool:
    return result is True


def charge_failed(result: bool) -> bool:
    return result is False


class RentalProcess:
    def __init__(self, scooters: ScooterRepository, trips: TripRepository,
                 accounts: UserAccountRepository, payments: PaymentGateway,
                 lock: ScooterLock, zones: ParkingZones, clock: Clock,
                 tariff: Tariff) -> None:
        self._scooters = scooters
        self._trips = trips
        self._accounts = accounts
        self._payments = payments
        self._lock = lock
        self._zones = zones
        self._clock = clock
        self._tariff = tariff

    # ------------------------------------------------------------ вспомогательное
    def _trip(self, trip_id: UUID) -> Trip:
        trip = self._trips.get(trip_id)
        if trip is None:
            raise EntityNotFound("Поездка не найдена")
        return trip

    def _scooter(self, scooter_id: UUID) -> Scooter:
        scooter = self._scooters.get(scooter_id)
        if scooter is None:
            raise EntityNotFound("Самокат не найден")
        return scooter

    def _account(self, user_id: UUID) -> UserAccount:
        account = self._accounts.get(user_id)
        if account is None:
            raise EntityNotFound("Клиент не найден")
        return account

    @staticmethod
    def _choose(gateway: str, *branches, default=None):
        """Исключающий шлюз: выбирает исход по первому выполненному условию."""
        for condition, outcome in branches:
            if condition():
                return outcome
        if default is not None:
            return default
        raise GatewayUnresolved(f"Шлюз «{gateway}»: ни одно условие не выполнено")

    @staticmethod
    def _run_parallel(*branches) -> None:
        """Параллельный шлюз: ветви выполняются последовательно, слияние после всех."""
        for branch in branches:
            branch()

    def _release_scooter(self, trip: Trip) -> None:
        scooter = self._scooters.get(trip.scooter_id)
        if scooter is not None and scooter.status == ScooterStatus.RESERVED:
            scooter.release_reservation()
            self._scooters.save(scooter)

    # ------------------------------------------------------------ бронирование
    def book_scooter(self, user_id: UUID, scooter_id: UUID) -> Trip:
        """Начальное событие «Бронь запрошена» и задача «Забронировать самокат»."""
        now = self._clock.now()
        account = self._account(user_id)
        account.ensure_can_book()
        scooter = self._scooter(scooter_id)
        scooter.reserve()
        trip = Trip.book(uuid4(), scooter_id, user_id, self._tariff, now)
        self._scooters.save(scooter)
        self._trips.save(trip)
        return trip

    # ------------------------------------------------------------ старт поездки
    def request_ride_start(self, trip_id: UUID) -> Trip:
        """Задача «Ожидать начала поездки» получила запрос клиента, далее проверки."""
        trip = self._trip(trip_id)
        now = self._clock.now()
        if "expire_reservation" in trip.allowed_events:
            trip.on_reservation_expired(now)
            if not trip.is_active:
                self._release_scooter(trip)
                self._trips.save(trip)
                return trip
        if "authorize" not in trip.allowed_events:
            raise TransitionNotAllowed(trip.status, "request_ride_start")

        account = self.check_user_debt(trip)
        debt = self._choose(
            "Задолженность есть?",
            (partial(debt_exists, account), "yes"),
            (partial(no_debt, account), "no"),
        )
        if debt == "yes":
            trip.reject_debt(now)
            self._release_scooter(trip)
            self._trips.save(trip)
            return trip

        result = self.perform_preauthorization(trip)
        preauth = self._choose(
            "Предавторизация успешна?",
            (partial(preauthorization_succeeded, result), "approved"),
            (partial(preauthorization_declined, result), "declined"),
        )
        if preauth == "declined":
            trip.reject_payment(now)
            self._release_scooter(trip)
            self._trips.save(trip)
            return trip

        trip.record_preauthorization(PREAUTH_AMOUNT, now)
        trip.authorize(now)
        self._trips.save(trip)

        self._run_parallel(lambda: self.unlock_scooter(trip),
                           lambda: self.start_billing(trip))
        self.start_trip(trip)
        return trip

    def check_user_debt(self, trip: Trip) -> UserAccount:
        return self._account(trip.user_id)

    def perform_preauthorization(self, trip: Trip) -> bool:
        return self._payments.preauthorize(trip.user_id, PREAUTH_AMOUNT)

    def unlock_scooter(self, trip: Trip) -> None:
        """Задача «Разблокировать замок»."""
        self._lock.unlock(trip.scooter_id)
        trip.mark_lock_unlocked(self._clock.now())
        self._trips.save(trip)

    def start_billing(self, trip: Trip) -> None:
        """Задача «Запустить тарификацию»."""
        trip.start_billing(self._clock.now())
        self._trips.save(trip)

    def start_trip(self, trip: Trip) -> None:
        """Задача «Начать поездку» (после слияния параллельных ветвей)."""
        scooter = self._scooter(trip.scooter_id)
        trip.start_ride(self._clock.now())
        scooter.start_rent()
        self._scooters.save(scooter)
        self._trips.save(trip)

    # ------------------------------------------------------------ во время поездки
    def receive_client_request(self, trip_id: UUID, action: str,
                               location: Location | None = None) -> Trip:
        """Задача «Получить запрос клиента» и шлюз «Действие клиента?»."""
        trip = self._trip(trip_id)
        branch = self._choose(
            "Действие клиента?",
            (partial(pause_requested, action), "pause"),
            default="finish",
        )
        if branch == "pause":
            self.pause_trip(trip)
            self.switch_to_pause_rate(trip)
        else:
            self.request_finish(trip, location)
        return trip

    def pause_trip(self, trip: Trip) -> None:
        trip.pause(self._clock.now())
        self._trips.save(trip)

    def switch_to_pause_rate(self, trip: Trip) -> None:
        trip.switch_to_pause_rate(self._clock.now())
        self._trips.save(trip)

    def request_resume(self, trip_id: UUID) -> Trip:
        """Задача «Возобновить поездку» получила запрос клиента."""
        trip = self._trip(trip_id)
        self.resume_trip(trip)
        self.switch_to_regular_rate(trip)
        return trip

    def resume_trip(self, trip: Trip) -> None:
        trip.resume(self._clock.now())
        self._trips.save(trip)

    def switch_to_regular_rate(self, trip: Trip) -> None:
        trip.switch_to_regular_rate(self._clock.now())
        self._trips.save(trip)

    # ------------------------------------------------------------ завершение
    def request_finish(self, trip: Trip, location: Location | None) -> None:
        """Шлюз «Самокат в зоне парковки?»."""
        if location is None:
            raise DomainInvariantViolation("Не передано местоположение самоката")
        zone = self._choose(
            "Самокат в зоне парковки?",
            (partial(in_allowed_zone, self._zones, location), "inside"),
            (partial(outside_allowed_zone, self._zones, location), "outside"),
        )
        if zone == "outside":
            self.notify_client_about_forbidden_zone(trip, location)
            return
        trip.confirm_parking_zone()
        self._trips.save(trip)

    def notify_client_about_forbidden_zone(self, trip: Trip, location: Location) -> None:
        trip.report_forbidden_zone(self._clock.now(), location)
        self._trips.save(trip)

    def receive_finish_photo(self, trip_id: UUID, photo_ref: str) -> Trip:
        """Задача «Получить фото самоката», далее завершение, расчёт и списание."""
        trip = self._trip(trip_id)
        trip.attach_finish_photo(photo_ref, self._clock.now())
        self._trips.save(trip)
        self.finish_trip(trip)
        self.calculate_trip_cost(trip)
        paid = self.charge_trip(trip)
        outcome = self._choose(
            "Списание прошло?",
            (partial(charge_succeeded, paid), "success"),
            (partial(charge_failed, paid), "failure"),
        )
        now = self._clock.now()
        if outcome == "success":
            trip.charge_success(now)
            self._trips.save(trip)
        else:
            trip.charge_fail(now)
            self._trips.save(trip)
            self.register_user_debt(trip)
            self.block_user_account(trip)
        return trip

    def finish_trip(self, trip: Trip) -> None:
        scooter = self._scooter(trip.scooter_id)
        trip.finish(self._clock.now())
        scooter.finish_rent()
        self._scooters.save(scooter)
        self._trips.save(trip)

    def calculate_trip_cost(self, trip: Trip) -> None:
        trip.calculate_cost(self._clock.now())
        self._trips.save(trip)

    def charge_trip(self, trip: Trip) -> bool:
        """Задача «Списать стоимость поездки»."""
        return self._payments.charge(trip.user_id, trip.cost)

    def register_user_debt(self, trip: Trip) -> None:
        account = self._account(trip.user_id)
        account.register_debt(trip.cost)
        self._accounts.save(account)

    def block_user_account(self, trip: Trip) -> None:
        account = self._account(trip.user_id)
        account.block()
        trip.notify_account_blocked(self._clock.now())
        self._accounts.save(account)
        self._trips.save(trip)

    # ------------------------------------------------------------ таймеры и оператор
    def notify_operator(self, trip: Trip) -> None:
        """Задача «Уведомить оператора» (непрерывающий таймер 12 часов)."""
        trip.on_ride_too_long(self._clock.now())
        self._trips.save(trip)

    def contact_client(self, trip_id: UUID, result: str) -> Trip:
        """Задача человека «Связаться с клиентом»: принимает результат."""
        trip = self._trip(trip_id)
        trip.record_operator_contact(result, self._clock.now())
        self._trips.save(trip)
        return trip

    def on_tick(self) -> None:
        """Вызывает методы on_...(now) для сущностей с истёкшим сроком."""
        now = self._clock.now()
        for trip in self._trips.all():
            if "expire_reservation" in trip.allowed_events:
                trip.on_reservation_expired(now)
                if not trip.is_active:
                    self._release_scooter(trip)
                self._trips.save(trip)
            elif "on_ride_too_long" in trip.allowed_events:
                self.notify_operator(trip)
