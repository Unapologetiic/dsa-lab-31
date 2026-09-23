from datetime import datetime
from uuid import UUID, uuid4

from domain.exceptions import DomainInvariantViolation, EntityNotFound
from domain.scooter.repositories import ScooterRepository, TripRepository
from domain.scooter.trip import Trip
from domain.scooter.value_objects import Tariff


class StartTripService:
    """Начать поездку: затрагивает Scooter и Trip."""

    def __init__(self, scooters: ScooterRepository, trips: TripRepository) -> None:
        self._scooters = scooters
        self._trips = trips

    def start(self, scooter_id: UUID, user_id: UUID,
              tariff: Tariff, started_at: datetime) -> Trip:
        scooter = self._scooters.get(scooter_id)
        if scooter is None:
            raise EntityNotFound("Самокат не найден")

        scooter.start_rent()

        trip = Trip(
            id=uuid4(),
            scooter_id=scooter_id,
            user_id=user_id,
            tariff=tariff,
            started_at=started_at,
        )
        self._scooters.save(scooter)
        self._trips.save(trip)
        return trip


class FinishTripService:
    """Завершить поездку: затрагивает Scooter и Trip."""

    def __init__(self, scooters: ScooterRepository, trips: TripRepository) -> None:
        self._scooters = scooters
        self._trips = trips

    def finish(self, trip_id: UUID, finished_at: datetime) -> Trip:
        trip = self._trips.get(trip_id)
        if trip is None:
            raise EntityNotFound("Поездка не найдена")

        trip.finish(finished_at)

        scooter = self._scooters.get(trip.scooter_id)
        if scooter is None:
            raise EntityNotFound("Самокат не найден")
        scooter.finish_rent()

        self._scooters.save(scooter)
        self._trips.save(trip)
        return trip