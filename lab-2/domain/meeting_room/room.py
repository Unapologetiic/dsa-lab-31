from dataclasses import dataclass
from uuid import UUID

from domain.meeting_room.value_objects import Capacity, WorkingHours


@dataclass
class Room:
    """Агрегат «Переговорная комната»."""

    id: UUID
    name: str
    capacity: Capacity
    working_hours: WorkingHours