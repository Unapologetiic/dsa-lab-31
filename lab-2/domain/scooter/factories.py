from datetime import datetime
from uuid import UUID

from domain.scooter.scooter import Scooter
from domain.scooter.trip import Trip
from domain.scooter.value_objects import BatteryLevel, ScooterStatus, Tariff
from domain.shared.money import Money


class ScooterFactory:
    """Фабрика восстановления агрегата Scooter."""

    @staticmethod
    def restore(
        id: UUID,
        battery_percent: int,
        status: ScooterStatus = ScooterStatus.FREE,
    ) -> Scooter:
        # BatteryLevel сам валидирует диапазон [0; 100]
        return Scooter(
            id=id,
            battery=BatteryLevel(battery_percent),
            status=status,
        )


class TripFactory:
    """Фабрика восстановления агрегата Trip."""

    @staticmethod
    def restore(
        id: UUID,
        scooter_id: UUID,
        user_id: UUID,
        tariff: Tariff,
        started_at: datetime,
        finished_at: datetime | None = None,
        cost: Money | None = None,
    ) -> Trip:
        trip = Trip(
            id=id,
            scooter_id=scooter_id,
            user_id=user_id,
            tariff=tariff,
            started_at=started_at,
        )
        
        if finished_at is not None:
            trip.finish(finished_at)
        return trip