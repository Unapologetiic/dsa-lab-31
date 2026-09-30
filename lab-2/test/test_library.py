from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from domain.exceptions import DomainInvariantViolation, InvalidValueObject
from domain.library.book import Book
from domain.library.loan import Loan
from domain.library.services import CheckoutService, ReturnService
from domain.library.value_objects import Fine, LoanPeriod, ReaderId
from domain.shared.money import Money
from infrastructure.in_memory import (
    InMemoryBookRepository,
    InMemoryLoanRepository,
)


def test_loan_period_ok():
    p = LoanPeriod(datetime(2026, 9, 1), datetime(2026, 9, 15))
    assert p.issue_date < p.due_date


def test_loan_period_invalid():
    with pytest.raises(InvalidValueObject):
        LoanPeriod(datetime(2026, 9, 15), datetime(2026, 9, 1))


def test_fine_negative_rejected():
    with pytest.raises(InvalidValueObject):
        Fine(Money(Decimal("-1")))


def test_reader_id_requires_uuid():
    with pytest.raises(InvalidValueObject):
        ReaderId("not-a-uuid")


def test_book_creation_ok():
    b = Book(id=uuid4(), title="DDD", total_copies=3, available_copies=3)
    assert b.available_copies == 3


def test_book_invalid_available():
    with pytest.raises(DomainInvariantViolation):
        Book(id=uuid4(), title="DDD", total_copies=1, available_copies=5)


def test_book_checkout():
    b = Book(id=uuid4(), title="DDD", total_copies=2, available_copies=2)
    b.checkout()
    assert b.available_copies == 1


def test_book_checkout_when_empty():
    b = Book(id=uuid4(), title="DDD", total_copies=1, available_copies=0)
    with pytest.raises(DomainInvariantViolation):
        b.checkout()


def test_book_return_when_full():
    b = Book(id=uuid4(), title="DDD", total_copies=1, available_copies=1)
    with pytest.raises(DomainInvariantViolation):
        b.return_copy()


def test_loan_close_twice_fails():
    loan = Loan(
        id=uuid4(),
        book_id=uuid4(),
        reader_id=ReaderId(uuid4()),
        period=LoanPeriod(datetime(2026, 9, 1), datetime(2026, 9, 15)),
    )
    loan.close(datetime(2026, 9, 10))
    with pytest.raises(DomainInvariantViolation):
        loan.close(datetime(2026, 9, 11))


def test_loan_close_before_issue_fails():
    loan = Loan(
        id=uuid4(),
        book_id=uuid4(),
        reader_id=ReaderId(uuid4()),
        period=LoanPeriod(datetime(2026, 9, 1), datetime(2026, 9, 15)),
    )
    with pytest.raises(DomainInvariantViolation):
        loan.close(datetime(2026, 8, 30))


def test_overdue_requires_fine():
    loan = Loan(
        id=uuid4(),
        book_id=uuid4(),
        reader_id=ReaderId(uuid4()),
        period=LoanPeriod(datetime(2026, 9, 1), datetime(2026, 9, 15)),
    )
    with pytest.raises(DomainInvariantViolation):
        loan.close(datetime(2026, 9, 20), fine=None)


def test_checkout_service_happy():
    books = InMemoryBookRepository()
    loans = InMemoryLoanRepository()
    book = Book(id=uuid4(), title="DDD", total_copies=1, available_copies=1)
    books.save(book)

    svc = CheckoutService(books, loans)
    reader = ReaderId(uuid4())
    period = LoanPeriod(datetime(2026, 9, 1), datetime(2026, 9, 15))
    loan = svc.checkout(book.id, reader, period)

    assert loans.get(loan.id) is loan
    assert books.get(book.id).available_copies == 0


def test_checkout_service_no_copies():
    books = InMemoryBookRepository()
    loans = InMemoryLoanRepository()
    book = Book(id=uuid4(), title="DDD", total_copies=1, available_copies=0)
    books.save(book)

    svc = CheckoutService(books, loans)
    with pytest.raises(DomainInvariantViolation):
        svc.checkout(
            book.id,
            ReaderId(uuid4()),
            LoanPeriod(datetime(2026, 9, 1), datetime(2026, 9, 15)),
        )


def test_return_service_with_fine():
    books = InMemoryBookRepository()
    loans = InMemoryLoanRepository()
    book = Book(id=uuid4(), title="DDD", total_copies=1, available_copies=1)
    books.save(book)

    checkout = CheckoutService(books, loans)
    return_svc = ReturnService(books, loans)

    reader = ReaderId(uuid4())
    issue = datetime(2026, 9, 1)
    due = issue + timedelta(days=14)
    checkout.checkout(book.id, reader, LoanPeriod(issue, due))

    loan = return_svc.return_book(book.id, reader, due + timedelta(days=3))
    assert loan.fine is not None
    assert loan.fine.amount.amount == Decimal("150")


def test_return_service_double_return_fails():
    books = InMemoryBookRepository()
    loans = InMemoryLoanRepository()
    book = Book(id=uuid4(), title="DDD", total_copies=1, available_copies=1)
    books.save(book)

    checkout = CheckoutService(books, loans)
    return_svc = ReturnService(books, loans)

    reader = ReaderId(uuid4())
    issue = datetime(2026, 9, 1)
    due = issue + timedelta(days=14)
    checkout.checkout(book.id, reader, LoanPeriod(issue, due))
    return_svc.return_book(book.id, reader, due)

    with pytest.raises(DomainInvariantViolation):
        return_svc.return_book(book.id, reader, due)