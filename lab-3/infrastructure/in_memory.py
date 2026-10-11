"""Репозитории в памяти и заглушки внешних участников."""
import copy
from datetime import datetime, timedelta
from uuid import UUID

from domain.scooter.scooter import Scooter
from domain.scooter.trip import Trip
from domain.scooter.user_account import UserAccount
from domain.scooter.value_objects import Location
from domain.shared.money import Money


class _Store:
    """Хранит копии агрегатов: незавершённые операции не меняют сохранённые данные."""

    def __init__(self) -> None:
        self._items: dict[UUID, object] = {}

    def get(self, item_id: UUID):
        item = self._items.get(item_id)
        return copy.deepcopy(item) if item is not None else None

    def _put(self, item) -> None:
        self._items[item.id] = copy.deepcopy(item)


class InMemoryScooterRepository(_Store):
    def save(self, scooter: Scooter) -> None:
        self._put(scooter)


class InMemoryTripRepository(_Store):
    def save(self, trip: Trip) -> None:
        self._put(trip)

    def find_active_by_scooter(self, scooter_id: UUID) -> Trip | None:
        for trip in self._items.values():
            if trip.scooter_id == scooter_id and trip.is_active:
                return copy.deepcopy(trip)
        return None

    def all(self) -> list[Trip]:
        return [copy.deepcopy(t) for t in self._items.values()]


class InMemoryUserAccountRepository(_Store):
    def save(self, account: UserAccount) -> None:
        self._put(account)


class InMemoryPaymentGateway:
    """Заглушка платёжной системы: список отказов задаётся, вызовы журналируются."""

    def __init__(self) -> None:
        self.decline_preauth: set[UUID] = set()
        self.decline_charge: set[UUID] = set()
        self.preauthorizations: list[tuple[UUID, Money]] = []
        self.charges: list[tuple[UUID, Money]] = []

    def preauthorize(self, user_id: UUID, amount: Money) -> bool:
        ok = user_id not in self.decline_preauth
        if ok:
            self.preauthorizations.append((user_id, amount))
        return ok

    def charge(self, user_id: UUID, amount: Money) -> bool:
        ok = user_id not in self.decline_charge
        if ok:
            self.charges.append((user_id, amount))
        return ok


class InMemoryScooterLock:
    def __init__(self) -> None:
        self.unlocked: list[UUID] = []

    def unlock(self, scooter_id: UUID) -> None:
        self.unlocked.append(scooter_id)


class InMemoryParkingZones:
    """Разрешённые зоны: прямоугольники (широта_мин, широта_макс, долгота_мин, долгота_макс)."""

    def __init__(self, areas: list[tuple[float, float, float, float]]) -> None:
        self._areas = areas

    def is_allowed(self, location: Location) -> bool:
        return any(a[0] <= location.latitude <= a[1] and a[2] <= location.longitude <= a[3]
                   for a in self._areas)


class ManualClock:
    """Управляемые часы для тестов и демо: реализуют протокол Clock."""

    def __init__(self, start: datetime) -> None:
        self._now = start

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        self._now += delta
