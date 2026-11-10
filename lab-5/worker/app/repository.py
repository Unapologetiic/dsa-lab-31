"""Работа с БД: одна операция = одна транзакция."""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from . import domain
from .domain import Context, Operation, PurchaseInfo
from .models import Account, OperationRow


def event_from_row(row: OperationRow) -> dict:
    return {
        "operation_id": row.operation_id,
        "type": row.type,
        "customer_id": row.customer_id,
        "store_id": row.store_id,
        "status": row.status,
        "points_delta": int(row.points_delta),
        "balance_after": int(row.balance_after),
        "reject_reason": row.reject_reason,
        "processed_at": row.processed_at.isoformat(),
    }


async def _build_context(session: AsyncSession, op: Operation, balance: Decimal) -> Context:
    if op.type == domain.PURCHASE:
        exists = await session.scalar(
            select(OperationRow.operation_id).where(
                OperationRow.type == domain.PURCHASE,
                OperationRow.check_number == op.check_number,
                OperationRow.status == domain.APPLIED,
            ).limit(1)
        )
        return Context(balance=balance, accepted_purchase_exists=exists is not None)

    if op.type == domain.RETURN:
        purchase_row = await session.scalar(
            select(OperationRow).where(
                OperationRow.type == domain.PURCHASE,
                OperationRow.check_number == op.check_number,
                OperationRow.status == domain.APPLIED,
            )
        )
        returned = await session.scalar(
            select(OperationRow.operation_id).where(
                OperationRow.type == domain.RETURN,
                OperationRow.check_number == op.check_number,
                OperationRow.status == domain.APPLIED,
            ).limit(1)
        )
        purchase = None
        if purchase_row is not None:
            purchase = PurchaseInfo(purchase_row.customer_id, int(purchase_row.points_delta))
        return Context(balance=balance, purchase=purchase, already_returned=returned is not None)

    return Context(balance=balance)


async def process_operation(sessionmaker: async_sessionmaker[AsyncSession], op: Operation) -> dict:
    """Рассчитать баллы, сохранить операцию и изменить баланс в одной транзакции.

    Возвращает событие «операция обработана». Повторная доставка уже
    обработанной операции (operation_id есть в БД) ничего не меняет и
    возвращает сохранённый результат, поэтому сообщение безопасно обрабатывать дважды.
    """
    async with sessionmaker() as session:
        async with session.begin():
            existing = await session.get(OperationRow, op.operation_id)
            if existing is not None:
                return event_from_row(existing)

            account = await session.scalar(
                select(Account).where(Account.customer_id == op.customer_id).with_for_update()
            )
            if account is None:   # счёт создаётся при первой операции покупателя
                account = Account(customer_id=op.customer_id, balance=Decimal(0))
                session.add(account)
                await session.flush()

            decision = domain.decide(op, await _build_context(session, op, account.balance))
            new_balance = account.balance + decision.points_delta
            account.balance = new_balance

            row = OperationRow(
                operation_id=op.operation_id, type=op.type, customer_id=op.customer_id,
                store_id=op.store_id, check_number=op.check_number, amount=op.amount,
                points=Decimal(op.points) if op.points is not None else None,
                points_delta=Decimal(decision.points_delta), balance_after=new_balance,
                status=decision.status, reject_reason=decision.reject_reason,
                occurred_at=op.occurred_at if op.occurred_at.tzinfo else op.occurred_at.replace(tzinfo=timezone.utc),
                processed_at=datetime.now(timezone.utc),
            )
            session.add(row)
            await session.flush()
            return event_from_row(row)   # коммит произойдёт при выходе из session.begin()
