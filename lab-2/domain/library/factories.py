from datetime import datetime
from uuid import UUID

from domain.library.book import Book
from domain.library.loan import Loan
from domain.library.value_objects import Fine, LoanPeriod, ReaderId


class BookFactory:
    """Фабрика восстановления агрегата Book."""

    @staticmethod
    def restore(
        id: UUID,
        title: str,
        total_copies: int,
        available_copies: int,
    ) -> Book:
        # Book.__post_init__ повторно проверяет инварианты:
        # 0 <= available_copies <= total_copies и total_copies > 0
        return Book(
            id=id,
            title=title,
            total_copies=total_copies,
            available_copies=available_copies,
        )


class LoanFactory:
    """Фабрика восстановления агрегата Loan."""

    @staticmethod
    def restore(
        id: UUID,
        book_id: UUID,
        reader_id: ReaderId,
        period: LoanPeriod,
        returned_at: datetime | None = None,
        fine: Fine | None = None,
    ) -> Loan:
        loan = Loan(
            id=id,
            book_id=book_id,
            reader_id=reader_id,
            period=period,
        )
        
        if returned_at is not None:
            loan.close(returned_at, fine)
        return loan