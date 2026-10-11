"""Паттерн «Состояние» для жизненного цикла поездки.

Базовый класс объявляет методы всех событий таблицы переходов и по умолчанию
запрещает их. Конкретное состояние переопределяет только допустимые переходы.
"""
from domain.exceptions import DomainInvariantViolation, TransitionNotAllowed


class TripState:
    name = ""
    final = False
    allowed: frozenset[str] = frozenset()

    def expire_reservation(self, trip) -> "TripState":
        raise TransitionNotAllowed(self.name, "expire_reservation")

    def reject_debt(self, trip) -> "TripState":
        raise TransitionNotAllowed(self.name, "reject_debt")

    def authorize(self, trip) -> "TripState":
        raise TransitionNotAllowed(self.name, "authorize")

    def reject_payment(self, trip) -> "TripState":
        raise TransitionNotAllowed(self.name, "reject_payment")

    def start_ride(self, trip) -> "TripState":
        raise TransitionNotAllowed(self.name, "start_ride")

    def pause(self, trip) -> "TripState":
        raise TransitionNotAllowed(self.name, "pause")

    def resume(self, trip) -> "TripState":
        raise TransitionNotAllowed(self.name, "resume")

    def finish(self, trip) -> "TripState":
        raise TransitionNotAllowed(self.name, "finish")

    def charge_success(self, trip) -> "TripState":
        raise TransitionNotAllowed(self.name, "charge_success")

    def charge_fail(self, trip) -> "TripState":
        raise TransitionNotAllowed(self.name, "charge_fail")

    def on_ride_too_long(self, trip) -> "TripState":
        raise TransitionNotAllowed(self.name, "on_ride_too_long")


class Booked(TripState):
    name = "Забронирована"
    allowed = frozenset({"expire_reservation", "reject_debt", "authorize", "reject_payment"})

    def expire_reservation(self, trip):
        return ReservationReleased()

    def reject_debt(self, trip):
        return RejectedByDebt()

    def authorize(self, trip):
        if trip.preauth_amount is None:
            raise DomainInvariantViolation("Предавторизация платежа не выполнена")
        return Checked()

    def reject_payment(self, trip):
        return RejectedByPayment()


class Checked(TripState):
    name = "Проверена"
    allowed = frozenset({"start_ride"})

    def start_ride(self, trip):
        if not (trip.lock_unlocked and trip.billing_started):
            raise DomainInvariantViolation(
                "Замок не разблокирован или тарификация не запущена"
            )
        return Riding()


class Riding(TripState):
    name = "В пути"
    allowed = frozenset({"pause", "finish", "on_ride_too_long"})

    def pause(self, trip):
        return Paused()

    def finish(self, trip):
        if not trip.zone_confirmed:
            raise DomainInvariantViolation("Самокат не в разрешённой зоне парковки")
        if trip.finish_photo is None:
            raise DomainInvariantViolation("Фото самоката не получено")
        return Finished()

    def on_ride_too_long(self, trip):
        return self


class Paused(TripState):
    name = "На паузе"
    allowed = frozenset({"resume", "on_ride_too_long"})

    def resume(self, trip):
        return Riding()

    def on_ride_too_long(self, trip):
        return self


class Finished(TripState):
    name = "Завершена"
    allowed = frozenset({"charge_success", "charge_fail"})

    def charge_success(self, trip):
        if trip.cost is None:
            raise DomainInvariantViolation("Стоимость поездки не рассчитана")
        return Paid()

    def charge_fail(self, trip):
        if trip.cost is None:
            raise DomainInvariantViolation("Стоимость поездки не рассчитана")
        return Unpaid()


class ReservationReleased(TripState):
    name = "Бронь снята"
    final = True


class RejectedByDebt(TripState):
    name = "Отклонена (задолженность)"
    final = True


class RejectedByPayment(TripState):
    name = "Отклонена (платёж)"
    final = True


class Paid(TripState):
    name = "Оплачена"
    final = True


class Unpaid(TripState):
    name = "Не оплачена"
    final = True


ALL_STATES = (Booked, Checked, Riding, Paused, Finished,
              ReservationReleased, RejectedByDebt, RejectedByPayment, Paid, Unpaid)
STATE_BY_NAME = {cls.name: cls for cls in ALL_STATES}
