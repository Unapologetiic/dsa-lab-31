"""Веб-адаптер на Flask и часы приложения. Домен и прикладной слой Flask не импортируют."""
import dataclasses
import logging
import os
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from application.rental_process import GatewayUnresolved, RentalProcess
from domain.exceptions import (DomainInvariantViolation, EntityNotFound, InvalidValueObject,
                               TransitionNotAllowed)
from domain.scooter.factories import ScooterFactory
from domain.scooter.user_account import UserAccount
from domain.scooter.value_objects import Location, Tariff
from domain.shared.money import Money
from infrastructure.in_memory import (InMemoryParkingZones, InMemoryPaymentGateway,
                                      InMemoryScooterLock, InMemoryScooterRepository,
                                      InMemoryTripRepository, InMemoryUserAccountRepository)

# Тестовые данные, создаваемые при запуске (хранилище в памяти)
USERS = {
    "10000000-0000-0000-0000-000000000001": "обычный клиент",
    "10000000-0000-0000-0000-000000000002": "клиент с задолженностью 50 руб.",
    "10000000-0000-0000-0000-000000000003": "платёжная система отклоняет предавторизацию",
    "10000000-0000-0000-0000-000000000004": "платёжная система отклоняет списание",
}
SCOOTERS = [f"20000000-0000-0000-0000-00000000000{n}" for n in range(1, 6)]


class ClockMovedBack(Exception):
    """Попытка перевести часы приложения назад."""


class ShiftedClock:
    """Часы приложения: системное время со сдвигом, который можно менять только вперёд."""

    def __init__(self) -> None:
        self._offset = timedelta(0)

    def now(self) -> datetime:
        return datetime.now() + self._offset

    def move_to(self, moment: datetime) -> None:
        if moment < self.now():
            raise ClockMovedBack("Перевод часов назад запрещён")
        self._offset = moment - datetime.now()


def _jsonable(value):
    if dataclasses.is_dataclass(value):
        return {f.name: _jsonable(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, Money):
        return {"amount": str(value.amount), "currency": value.currency}
    if isinstance(value, (UUID, Decimal)):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _body() -> dict:
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else {}


def _uuid(raw, name: str) -> UUID:
    if raw is None:
        raise InvalidValueObject(f"Поле {name} обязательно")
    try:
        return UUID(str(raw))
    except ValueError:
        raise InvalidValueObject(f"Поле {name} должно быть UUID")


def _text(body: dict, name: str) -> str:
    value = body.get(name)
    if not isinstance(value, str) or not value.strip():
        raise InvalidValueObject(f"Поле {name} обязательно")
    return value


def _location(body: dict) -> Location:
    values = []
    for name in ("latitude", "longitude"):
        value = body.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise InvalidValueObject(f"Поле {name} должно быть числом")
        values.append(float(value))
    return Location(*values)


def _moment(raw) -> datetime:
    try:
        moment = datetime.fromisoformat(str(raw))
    except ValueError:
        raise InvalidValueObject("Время должно быть в формате ISO 8601")
    if moment.tzinfo is not None:
        raise InvalidValueObject("Время указывается без часового пояса")
    return moment


ERRORS = [
    (TransitionNotAllowed, 409, "transition_not_allowed"),
    (EntityNotFound, 404, "not_found"),
    (ClockMovedBack, 422, "clock_moved_back"),
    (DomainInvariantViolation, 422, "invariant_violation"),
    (InvalidValueObject, 422, "invalid_value"),
    (GatewayUnresolved, 500, "gateway_unresolved"),
]


def create_app() -> Flask:
    logging.basicConfig(level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO))
    app = Flask(__name__)

    # часы, репозитории и сервис процесса создаются один раз при запуске
    clock = ShiftedClock()
    scooters, trips, accounts = (InMemoryScooterRepository(), InMemoryTripRepository(),
                                 InMemoryUserAccountRepository())
    payments = InMemoryPaymentGateway()
    for number, user_id in enumerate(USERS, start=1):
        debt = Money(Decimal("50")) if number == 2 else Money(Decimal("0"))
        accounts.save(UserAccount(UUID(user_id), debt=debt))
    payments.decline_preauth.add(UUID("10000000-0000-0000-0000-000000000003"))
    payments.decline_charge.add(UUID("10000000-0000-0000-0000-000000000004"))
    for scooter_id, battery in zip(SCOOTERS, (80, 80, 80, 80, 10)):
        scooters.save(ScooterFactory.restore(UUID(scooter_id), battery))
    process = RentalProcess(
        scooters, trips, accounts, payments, InMemoryScooterLock(),
        InMemoryParkingZones([(55.0, 55.1, 82.8, 83.0)]), clock,
        Tariff(Money(Decimal("5")), Money(Decimal("10")), Money(Decimal("2"))))

    def respond(trip_id: UUID, status: int = 200):
        trip = trips.get(trip_id)
        if trip is None:
            raise EntityNotFound("Поездка не найдена")
        return jsonify({
            "id": str(trip.id),
            "status": trip.status,
            "allowed_events": sorted(trip.allowed_events),
            "cost": _jsonable(trip.cost),
            "events": [{"type": type(e).__name__, **_jsonable(e)} for e in trip.events],
        }), status

    @app.post("/trips")
    def book():
        body = _body()
        trip = process.book_scooter(_uuid(body.get("user_id"), "user_id"),
                                    _uuid(body.get("scooter_id"), "scooter_id"))
        return respond(trip.id, 201)

    @app.post("/trips/<trip_id>/start")
    def start(trip_id):
        trip_id = _uuid(trip_id, "id")
        process.request_ride_start(trip_id)
        return respond(trip_id)

    @app.post("/trips/<trip_id>/pause")
    def pause(trip_id):
        trip_id = _uuid(trip_id, "id")
        process.receive_client_request(trip_id, "pause")
        return respond(trip_id)

    @app.post("/trips/<trip_id>/resume")
    def resume(trip_id):
        trip_id = _uuid(trip_id, "id")
        process.request_resume(trip_id)
        return respond(trip_id)

    @app.post("/trips/<trip_id>/finish")
    def finish(trip_id):
        trip_id = _uuid(trip_id, "id")
        process.receive_client_request(trip_id, "finish", _location(_body()))
        return respond(trip_id)

    @app.post("/trips/<trip_id>/photo")
    def photo(trip_id):
        trip_id = _uuid(trip_id, "id")
        process.receive_finish_photo(trip_id, _text(_body(), "photo_ref"))
        return respond(trip_id)

    @app.post("/trips/<trip_id>/contact")
    def contact(trip_id):
        trip_id = _uuid(trip_id, "id")
        process.contact_client(trip_id, _text(_body(), "result"))
        return respond(trip_id)

    @app.get("/trips/<trip_id>")
    def get_trip(trip_id):
        return respond(_uuid(trip_id, "id"))

    @app.post("/internal/tick")
    def tick():
        raw = _body().get("now")
        if raw is not None:
            clock.move_to(_moment(raw))
        process.on_tick()
        return jsonify({"now": clock.now().isoformat()})

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.errorhandler(Exception)
    def handle_error(exc):
        if isinstance(exc, HTTPException):
            return jsonify({"error": exc.name.lower().replace(" ", "_"),
                            "message": exc.description}), exc.code
        for cls, status, code in ERRORS:
            if isinstance(exc, cls):
                app.logger.warning("%s: %s", code, exc)
                return jsonify({"error": code, "message": str(exc)}), status
        app.logger.exception("Необработанная ошибка")
        return jsonify({"error": "internal_error", "message": "Внутренняя ошибка"}), 500

    return app
