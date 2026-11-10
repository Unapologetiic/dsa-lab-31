from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StrictInt, StringConstraints, model_validator

NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]


class OperationIn(BaseModel):
    """Проверка ТОЛЬКО формата (раздел I). Бизнес-правила проверяет worker."""
    operation_id: NonEmpty
    type: Literal["purchase", "return", "redeem"]
    customer_id: NonEmpty
    store_id: NonEmpty
    check_number: NonEmpty
    occurred_at: datetime
    amount: Decimal | None = Field(default=None, gt=0, max_digits=16, decimal_places=2)
    points: StrictInt | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def check_fields_for_type(self):
        if self.type in ("purchase", "redeem") and self.amount is None:
            raise ValueError("amount обязателен для покупки и оплаты баллами")
        if self.type == "return" and self.amount is not None:
            raise ValueError("в возврате поле amount отсутствует")
        if self.type == "redeem" and self.points is None:
            raise ValueError("points обязателен для оплаты баллами")
        if self.type != "redeem" and self.points is not None:
            raise ValueError("поле points допустимо только для оплаты баллами")
        return self
