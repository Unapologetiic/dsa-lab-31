from datetime import datetime, time
from uuid import uuid4

import pytest

from domain.exceptions import DomainInvariantViolation, InvalidValueObject
from domain.meeting_room.booking import Booking
from domain.meeting_room.room import Room
from domain.meeting_room.services import CreateBookingService
from domain.meeting_room.value_objects import Capacity, WorkingHours
from domain.shared.time_period import TimePeriod
from infrastructure.in_memory import (
    InMemoryBookingRepository,
    InMemoryRoomRepository,
)


def make_room(
    capacity: int = 10,
    open_at: time = time(9, 0),
    close_at: time = time(18, 0),
) -> Room:
    return Room(
        id=uuid4(),
        name="Переговорная",
        capacity=Capacity(capacity),
        working_hours=WorkingHours(open_at, close_at),
    )


def period(h_start: int, h_end: int, day: int = 1) -> TimePeriod:
    return TimePeriod(
        start=datetime(2026, 9, day, h_start, 0),
        end=datetime(2026, 9, day, h_end, 0),
    )


def make_service():
    rooms = InMemoryRoomRepository()
    bookings = InMemoryBookingRepository()
    return rooms, bookings, CreateBookingService(rooms, bookings)


# ---------- Value objects ----------

def test_capacity_must_be_positive():
    with pytest.raises(InvalidValueObject):
        Capacity(0)


def test_working_hours_invalid():
    with pytest.raises(InvalidValueObject):
        WorkingHours(time(18, 0), time(9, 0))


def test_capacity_can_fit():
    assert Capacity(5).can_fit(5)
    assert Capacity(5).can_fit(3)
    assert not Capacity(5).can_fit(6)


def test_time_period_invalid():
    with pytest.raises(InvalidValueObject):
        TimePeriod(
            datetime(2026, 9, 1, 12, 0),
            datetime(2026, 9, 1, 11, 0),
        )


# ---------- Агрегат Booking ----------

def test_booking_within_capacity_ok():
    room = make_room(capacity=5)
    booking = Booking(
        id=uuid4(),
        room_id=room.id,
        employee_id=uuid4(),
        period=period(10, 11),
        participants=5,
    )
    booking.validate_against_room(room.capacity, room.working_hours)


def test_booking_exceeds_capacity():
    room = make_room(capacity=5)
    booking = Booking(
        id=uuid4(),
        room_id=room.id,
        employee_id=uuid4(),
        period=period(10, 11),
        participants=6,
    )
    with pytest.raises(DomainInvariantViolation):
        booking.validate_against_room(room.capacity, room.working_hours)


def test_booking_outside_hours_before():
    room = make_room(open_at=time(9, 0), close_at=time(18, 0))
    booking = Booking(
        id=uuid4(),
        room_id=room.id,
        employee_id=uuid4(),
        period=period(8, 10),
        participants=3,
    )
    with pytest.raises(DomainInvariantViolation):
        booking.validate_against_room(room.capacity, room.working_hours)


def test_booking_outside_hours_after():
    room = make_room(open_at=time(9, 0), close_at=time(18, 0))
    booking = Booking(
        id=uuid4(),
        room_id=room.id,
        employee_id=uuid4(),
        period=period(17, 19),
        participants=3,
    )
    with pytest.raises(DomainInvariantViolation):
        booking.validate_against_room(room.capacity, room.working_hours)


def test_cancel_twice_fails():
    room = make_room()
    booking = Booking(
        id=uuid4(),
        room_id=room.id,
        employee_id=uuid4(),
        period=period(10, 11),
        participants=3,
    )
    booking.cancel()
    with pytest.raises(DomainInvariantViolation):
        booking.cancel()


# ---------- Доменный сервис ----------

def test_create_booking_happy():
    rooms, bookings, svc = make_service()
    room = make_room(capacity=10)
    rooms.save(room)

    booking = svc.create(room.id, uuid4(), period(10, 11), 4)
    assert bookings.get(booking.id) is booking


def test_create_booking_room_not_found():
    rooms, bookings, svc = make_service()
    with pytest.raises(Exception):
        svc.create(uuid4(), uuid4(), period(10, 11), 4)


def test_overlapping_bookings_rejected():
    rooms, bookings, svc = make_service()
    room = make_room()
    rooms.save(room)

    svc.create(room.id, uuid4(), period(10, 12), 4)
    with pytest.raises(DomainInvariantViolation):
        svc.create(room.id, uuid4(), period(11, 13), 4)


def test_adjacent_bookings_allowed():
    rooms, bookings, svc = make_service()
    room = make_room()
    rooms.save(room)

    svc.create(room.id, uuid4(), period(10, 11), 4)
    svc.create(room.id, uuid4(), period(11, 12), 4)
    assert len(bookings.find_by_room(room.id)) == 2


def test_cancelled_booking_does_not_block_new_one():
    rooms, bookings, svc = make_service()
    room = make_room()
    rooms.save(room)

    b1 = svc.create(room.id, uuid4(), period(10, 12), 4)
    b1.cancel()
    bookings.save(b1)

    b2 = svc.create(room.id, uuid4(), period(10, 12), 4)
    assert b2.id != b1.id