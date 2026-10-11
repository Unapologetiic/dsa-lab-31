import dataclasses
import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from application.rental_process import GatewayUnresolved, RentalProcess
from domain.exceptions import DomainInvariantViolation, EntityNotFound, TransitionNotAllowed
from domain.scooter.factories import ScooterFactory
from domain.scooter.trip import Trip
from domain.scooter.user_account import UserAccount
from domain.scooter.value_objects import Location, ScooterStatus, Tariff
from domain.shared.money import Money
from infrastructure.in_memory import (InMemoryParkingZones, ManualClock, InMemoryPaymentGateway,
                                      InMemoryScooterLock, InMemoryScooterRepository,
                                      InMemoryTripRepository, InMemoryUserAccountRepository)

START = datetime(2026, 10, 1, 10, 0)
IN_ZONE = Location(55.03, 82.92)
OUT_ZONE = Location(55.50, 83.50)


def rub(x):
    return Money(Decimal(str(x)))


class ProcessTestCase(unittest.TestCase):
    def setUp(self):
        self.scooters = InMemoryScooterRepository()
        self.trips = InMemoryTripRepository()
        self.accounts = InMemoryUserAccountRepository()
        self.payments = InMemoryPaymentGateway()
        self.lock = InMemoryScooterLock()
        self.zones = InMemoryParkingZones([(55.0, 55.1, 82.8, 83.0)])
        self.clock = ManualClock(START)
        self.tariff = Tariff(rub(5), rub(10), rub(2))
        self.process = RentalProcess(self.scooters, self.trips, self.accounts, self.payments,
                                     self.lock, self.zones, self.clock, self.tariff)
        self.user = uuid4()
        self.scooter_id = uuid4()
        self.accounts.save(UserAccount(self.user))
        self.scooters.save(ScooterFactory.restore(self.scooter_id, 80))

    def scooter(self):
        return self.scooters.get(self.scooter_id)

    def started_trip(self):
        trip = self.process.book_scooter(self.user, self.scooter_id)
        self.clock.advance(timedelta(minutes=2))
        return self.process.request_ride_start(trip.id)

    def finish(self, trip_id, location=IN_ZONE):
        self.process.receive_client_request(trip_id, "finish", location)
        return self.process.receive_finish_photo(trip_id, "photo.jpg")


class MainPathTest(ProcessTestCase):
    def test_p1_main_path(self):
        trip = self.started_trip()
        self.assertEqual(trip.status, "В пути")
        self.assertEqual(self.scooter().status, ScooterStatus.RENTED)
        self.assertEqual(self.lock.unlocked, [self.scooter_id])
        self.clock.advance(timedelta(minutes=30))
        trip = self.finish(trip.id)
        self.assertEqual(trip.status, "Оплачена")
        self.assertEqual(self.scooter().status, ScooterStatus.FREE)
        self.assertEqual(trip.cost, rub(5 * 30))
        self.assertEqual(self.payments.charges, [(self.user, rub(150))])
        names = [type(e).__name__ for e in trip.events]
        self.assertEqual(names[0], "ReservationConfirmed")
        self.assertEqual(names[-1], "TripCharged")
        self.assertIn("RideStarted", names)

    def test_p2_reservation_timer(self):
        trip = self.process.book_scooter(self.user, self.scooter_id)
        self.clock.advance(timedelta(minutes=9, seconds=59))
        self.process.on_tick()
        self.assertEqual(self.trips.get(trip.id).status, "Забронирована")
        self.clock.advance(timedelta(seconds=1))
        self.process.on_tick()
        self.assertEqual(self.trips.get(trip.id).status, "Бронь снята")
        self.assertEqual(self.scooter().status, ScooterStatus.FREE)

    def test_p2_start_after_timeout_releases_booking(self):
        trip = self.process.book_scooter(self.user, self.scooter_id)
        self.clock.advance(timedelta(minutes=11))
        self.assertEqual(self.process.request_ride_start(trip.id).status, "Бронь снята")

    def test_p3_debt_rejects_ride(self):
        self.accounts.save(UserAccount(self.user, debt=rub(50)))
        trip = self.process.book_scooter(self.user, self.scooter_id)
        trip = self.process.request_ride_start(trip.id)
        self.assertEqual(trip.status, "Отклонена (задолженность)")
        self.assertEqual(self.scooter().status, ScooterStatus.FREE)
        self.assertEqual(self.payments.preauthorizations, [])

    def test_p4_preauthorization_declined(self):
        self.payments.decline_preauth.add(self.user)
        trip = self.process.book_scooter(self.user, self.scooter_id)
        trip = self.process.request_ride_start(trip.id)
        self.assertEqual(trip.status, "Отклонена (платёж)")
        self.assertEqual(self.scooter().status, ScooterStatus.FREE)
        self.assertEqual(self.lock.unlocked, [])


class AlternativePathTest(ProcessTestCase):
    def test_p5_pause_uses_reduced_rate(self):
        trip = self.started_trip()
        self.clock.advance(timedelta(minutes=10))
        trip = self.process.receive_client_request(trip.id, "pause")
        self.assertEqual(self.trips.get(trip.id).status, "На паузе")
        self.assertEqual(self.trips.get(trip.id).billing_rate, "pause")
        self.clock.advance(timedelta(minutes=10))
        self.process.request_resume(trip.id)
        self.assertEqual(self.trips.get(trip.id).billing_rate, "regular")
        self.clock.advance(timedelta(minutes=10))
        trip = self.finish(trip.id)
        self.assertEqual(trip.cost, rub(20 * 5 + 10 * 2))

    def test_p6_forbidden_zone_then_allowed(self):
        trip = self.started_trip()
        self.process.receive_client_request(trip.id, "finish", OUT_ZONE)
        self.assertEqual(self.trips.get(trip.id).status, "В пути")
        self.assertIn("ParkingZoneViolation", [type(e).__name__ for e in self.trips.get(trip.id).events])
        with self.assertRaises(DomainInvariantViolation):
            self.process.receive_finish_photo(trip.id, "photo.jpg")
        self.clock.advance(timedelta(minutes=5))
        trip = self.finish(trip.id)
        self.assertEqual(trip.status, "Оплачена")

    def test_p7_charge_failure_creates_debt_and_blocks(self):
        trip = self.started_trip()
        self.payments.decline_charge.add(self.user)
        self.clock.advance(timedelta(minutes=20))
        trip = self.finish(trip.id)
        self.assertEqual(trip.status, "Не оплачена")
        account = self.accounts.get(self.user)
        self.assertEqual(account.debt, rub(100))
        self.assertTrue(account.blocked)
        self.assertIn("AccountBlockedNotified", [type(e).__name__ for e in trip.events])
        other = uuid4()
        self.scooters.save(ScooterFactory.restore(other, 90))
        with self.assertRaises(DomainInvariantViolation):
            self.process.book_scooter(self.user, other)

    def test_p8_long_ride_notifies_operator_once(self):
        trip = self.started_trip()
        self.clock.advance(timedelta(hours=11, minutes=59))
        self.process.on_tick()
        self.assertFalse(self.trips.get(trip.id).operator_notified)
        self.clock.advance(timedelta(minutes=1))
        self.process.on_tick()
        self.process.on_tick()
        stored = self.trips.get(trip.id)
        self.assertEqual(stored.status, "В пути")
        self.assertEqual([type(e).__name__ for e in stored.events].count("OperatorNotified"), 1)
        self.process.contact_client(trip.id, "клиент ответил")
        trip = self.finish(trip.id)
        self.assertEqual(trip.status, "Оплачена")
        self.assertEqual(type(trip.events[-1]).__name__, "TripCharged")
        self.assertIn("OperatorContacted", [type(e).__name__ for e in trip.events])

    def test_contact_without_notification_is_rejected(self):
        trip = self.started_trip()
        with self.assertRaises(DomainInvariantViolation):
            self.process.contact_client(trip.id, "звонок")


class InvalidEventTest(ProcessTestCase):
    def snapshot(self, trip_id):
        t = self.trips.get(trip_id)
        return t.status, len(t.events)

    def test_start_twice_is_rejected_and_state_kept(self):
        trip = self.started_trip()
        before = self.snapshot(trip.id)
        with self.assertRaises(TransitionNotAllowed):
            self.process.request_ride_start(trip.id)
        self.assertEqual(self.snapshot(trip.id), before)

    def test_pause_in_booked_state(self):
        trip = self.process.book_scooter(self.user, self.scooter_id)
        before = self.snapshot(trip.id)
        with self.assertRaises(TransitionNotAllowed):
            self.process.receive_client_request(trip.id, "pause")
        self.assertEqual(self.snapshot(trip.id), before)

    def test_resume_without_pause(self):
        trip = self.started_trip()
        before = self.snapshot(trip.id)
        with self.assertRaises(TransitionNotAllowed):
            self.process.request_resume(trip.id)
        self.assertEqual(self.snapshot(trip.id), before)

    def test_finish_from_paused(self):
        trip = self.started_trip()
        self.process.receive_client_request(trip.id, "pause")
        before = self.snapshot(trip.id)
        with self.assertRaises(TransitionNotAllowed):
            self.process.receive_client_request(trip.id, "finish", IN_ZONE)
        self.assertEqual(self.snapshot(trip.id), before)

    def test_photo_without_zone_check(self):
        trip = self.started_trip()
        with self.assertRaises(DomainInvariantViolation):
            self.process.receive_finish_photo(trip.id, "photo.jpg")

    def test_booking_busy_scooter(self):
        self.process.book_scooter(self.user, self.scooter_id)
        other = uuid4()
        self.accounts.save(UserAccount(other))
        with self.assertRaises(DomainInvariantViolation):
            self.process.book_scooter(other, self.scooter_id)

    def test_low_battery_scooter_cannot_be_booked(self):
        low = uuid4()
        self.scooters.save(ScooterFactory.restore(low, 10))
        with self.assertRaises(DomainInvariantViolation):
            self.process.book_scooter(self.user, low)

    def test_unknown_entities(self):
        with self.assertRaises(EntityNotFound):
            self.process.request_ride_start(uuid4())
        with self.assertRaises(EntityNotFound):
            self.process.book_scooter(uuid4(), self.scooter_id)

    def test_gateway_unresolved_when_port_returns_none(self):
        self.payments.preauthorize = lambda user_id, amount: None
        trip = self.process.book_scooter(self.user, self.scooter_id)
        with self.assertRaises(GatewayUnresolved):
            self.process.request_ride_start(trip.id)


class RestoreCompatibilityTest(ProcessTestCase):
    def test_lab2_signature_restores_started_trip(self):
        from domain.scooter.factories import TripFactory
        trip = TripFactory.restore(uuid4(), self.scooter_id, self.user, self.tariff, START)
        self.assertEqual(trip.status, "В пути")
        self.assertEqual(trip.allowed_events, frozenset({"pause", "finish", "on_ride_too_long"}))

    def test_lab2_signature_restores_finished_trip_with_cost(self):
        from domain.scooter.factories import TripFactory
        trip = TripFactory.restore(uuid4(), self.scooter_id, self.user, self.tariff,
                                   START, START + timedelta(minutes=30))
        self.assertEqual(trip.status, "Завершена")
        self.assertEqual(trip.cost, rub(150))

    def test_restore_booked_trip(self):
        from domain.scooter.factories import TripFactory
        trip = TripFactory.restore(uuid4(), self.scooter_id, self.user, self.tariff,
                                   reserved_at=START)
        self.assertEqual(trip.status, "Забронирована")


class AggregateProtectionTest(ProcessTestCase):
    def test_status_has_no_setter(self):
        trip = self.process.book_scooter(self.user, self.scooter_id)
        with self.assertRaises(AttributeError):
            trip.status = "Оплачена"

    def test_domain_events_are_immutable(self):
        trip = self.process.book_scooter(self.user, self.scooter_id)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            trip.events[0].scooter_id = uuid4()

    def test_wrong_preauthorization_amount(self):
        trip = Trip.book(uuid4(), self.scooter_id, self.user, self.tariff, START)
        with self.assertRaises(DomainInvariantViolation):
            trip.record_preauthorization(rub(100), START)

    def test_pause_rate_not_above_regular(self):
        from domain.exceptions import InvalidValueObject
        with self.assertRaises(InvalidValueObject):
            Tariff(rub(5), rub(10), rub(6))


if __name__ == "__main__":
    unittest.main()
