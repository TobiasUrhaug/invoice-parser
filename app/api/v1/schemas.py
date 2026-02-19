from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class MonetaryAmount(BaseModel):
    amount: Decimal
    currency: str | None


class InvoiceResult(BaseModel):
    invoiceDate: date | None
    invoiceReference: str | None
    netAmount: MonetaryAmount | None
    vatAmount: MonetaryAmount | None
    totalAmount: MonetaryAmount | None
