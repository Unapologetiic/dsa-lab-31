from datetime import datetime
from uuid import UUID, uuid4

from domain.exceptions import DomainInvariantViolation, EntityNotFound
from domain.parking.parking_session import ParkingSession
from domain.parking.repositories import (
    ParkingSessionRepository,
    ParkingSpotRepository,
)
from domain.parking.value_objects import Tariff


class StartParkingService:
    """Въезд: затрагивает ParkingSpot и ParkingSession."""

    def __init__(self, spots: ParkingSpotRepository,
                 sessions: ParkingSessionRepository) -> None:
        self._spots = spots
        self._sessions = sessions

    def start(self, spot_id: UUID, vehicle_plate: str,
              tariff: Tariff, entered_at: datetime) -> ParkingSession:
        spot = self._spots.get(spot_id)
        if spot is None:
            raise EntityNotFound("Место не найдено")

        spot.occupy()

        session = ParkingSession(
            id=uuid4(),
            spot_id=spot_id,
            vehicle_plate=vehicle_plate,
            tariff=tariff,
            entered_at=entered_at,
        )
        self._spots.save(spot)
        self._sessions.save(session)
        return session


class CloseParkingService:
    """Выезд: затрагивает ParkingSpot и ParkingSession."""

    def __init__(self, spots: ParkingSpotRepository,
                 sessions: ParkingSessionRepository) -> None:
        self._spots = spots
        self._sessions = sessions

    def close(self, session_id: UUID, exited_at: datetime) -> ParkingSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise EntityNotFound("Сессия не найдена")

        session.close(exited_at)

        spot = self._spots.get(session.spot_id)
        if spot is None:
            raise EntityNotFound("Место не найдено")
        spot.release()

        self._spots.save(spot)
        self._sessions.save(session)
        return session