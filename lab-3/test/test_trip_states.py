import unittest
from types import SimpleNamespace

from domain.exceptions import TransitionNotAllowed
from domain.scooter import trip_states as s
from domain.shared.money import Money
from decimal import Decimal

EVENTS = ["expire_reservation", "reject_debt", "authorize", "reject_payment", "start_ride",
          "pause", "resume", "finish", "charge_success", "charge_fail", "on_ride_too_long"]

# Таблица переходов (строки — состояния, столбцы — события); None означает «недопустимо»
TABLE = {
    s.Booked: dict(expire_reservation=s.ReservationReleased, reject_debt=s.RejectedByDebt,
                   authorize=s.Checked, reject_payment=s.RejectedByPayment),
    s.Checked: dict(start_ride=s.Riding),
    s.Riding: dict(pause=s.Paused, finish=s.Finished, on_ride_too_long=s.Riding),
    s.Paused: dict(resume=s.Riding, on_ride_too_long=s.Paused),
    s.Finished: dict(charge_success=s.Paid, charge_fail=s.Unpaid),
    s.ReservationReleased: {}, s.RejectedByDebt: {}, s.RejectedByPayment: {},
    s.Paid: {}, s.Unpaid: {},
}


def ready_trip():
    """Поездка, у которой выполнены все условия сторожевых проверок."""
    return SimpleNamespace(preauth_amount=Money(Decimal("300")), lock_unlocked=True,
                           billing_started=True, zone_confirmed=True, finish_photo="p.jpg",
                           cost=Money(Decimal("100")))


class TransitionTableTest(unittest.TestCase):
    def test_every_state_event_pair(self):
        for state_cls, row in TABLE.items():
            for event in EVENTS:
                with self.subTest(state=state_cls.name, event=event):
                    state = state_cls()
                    if event in row:
                        self.assertIsInstance(getattr(state, event)(ready_trip()), row[event])
                    else:
                        with self.assertRaises(TransitionNotAllowed) as ctx:
                            getattr(state, event)(ready_trip())
                        self.assertEqual(ctx.exception.state, state.name)
                        self.assertEqual(ctx.exception.event, event)

    def test_allowed_lists_match_table(self):
        for state_cls, row in TABLE.items():
            self.assertEqual(state_cls.allowed, frozenset(row))

    def test_final_states(self):
        finals = {c for c in TABLE if c.final}
        self.assertEqual(len(finals), 5)
        for cls in finals:
            self.assertEqual(cls.allowed, frozenset())


if __name__ == "__main__":
    unittest.main()
