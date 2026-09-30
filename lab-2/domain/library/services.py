from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from domain.exceptions import DomainInvariantViolation, EntityNotFound
from domain.library.loan import Loan
from domain.library.repositories import BookRepository, LoanRepository
from domain.library.value_objects import Fine, LoanPeriod, ReaderId
from domain.shared.money import Money

FINE_PER_DAY = Money(Decimal("50"), "RUB")


class CheckoutService:
    """Выдача книги: затрагивает Book и Loan."""

    def __init__(self, books: BookRepository, loans: LoanRepository) -> None:
        self._books = books
        self._loans = loans

    def checkout(
        self,
        book_id: UUID,
        reader_id: ReaderId,
        period: LoanPeriod,
    ) -> Loan:
        book = self._books.get(book_id)
        if book is None:
            raise EntityNotFound("Книга не найдена")

        book.checkout()

        loan = Loan(
            id=uuid4(),
            book_id=book_id,
            reader_id=reader_id,
            period=period,
        )
        self._books.save(book)
        self._loans.save(loan)
        return loan


class ReturnService:
    """Возврат книги: затрагивает Book и Loan."""

    def __init__(self, books: BookRepository, loans: LoanRepository) -> None:
        self._books = books
        self._loans = loans

    def return_book(
        self,
        book_id: UUID,
        reader_id: ReaderId,
        returned_at: datetime,
    ) -> Loan:
        loan = self._loans.find_open_loan(book_id, reader_id.value)
        if loan is None:
            raise DomainInvariantViolation(
                "Нет открытой выдачи этой книги этому читателю"
            )

        fine: Fine | None = None
        if loan.period.is_overdue(returned_at):
            overdue_days = (returned_at - loan.period.due_date).days or 1
            fine = Fine(FINE_PER_DAY * Decimal(overdue_days))

        loan.close(returned_at, fine)

        book = self._books.get(book_id)
        if book is None:
            raise EntityNotFound("Книга не найдена")
        book.return_copy()

        self._books.save(book)
        self._loans.save(loan)
        return loan