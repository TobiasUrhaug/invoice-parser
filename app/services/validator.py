import logging
import re
from datetime import date
from decimal import Decimal
from typing import Any

from dateutil import parser as dateutil_parser
from pydantic import ValidationError

from app.api.v1.schemas import InvoiceResult, MonetaryAmount

logger = logging.getLogger(__name__)

# Mapping from European month names to English for dateutil compatibility.
# Only months that differ from English are included.
_EUROPEAN_MONTHS: dict[str, str] = {
    # German / Austrian
    "januar": "January",
    "februar": "February",
    "märz": "March",
    "mär": "March",
    "mai": "May",
    "juni": "June",
    "juli": "July",
    "oktober": "October",
    "dezember": "December",
    # Norwegian / Danish / Swedish
    "mars": "March",
    "desember": "December",
    # Dutch
    "januari": "January",
    "februari": "February",
    "maart": "March",
    "mei": "May",
    "december": "December",
    # French
    "janvier": "January",
    "février": "February",
    "avril": "April",
    "juin": "June",
    "juillet": "July",
    "août": "August",
    "octobre": "October",
    "novembre": "November",
    "décembre": "December",
    # Italian
    "gennaio": "January",
    "febbraio": "February",
    "marzo": "March",
    "aprile": "April",
    "maggio": "May",
    "giugno": "June",
    "luglio": "July",
    "settembre": "September",
    "ottobre": "October",
    "dicembre": "December",
    # Spanish
    "enero": "January",
    "febrero": "February",
    "junio": "June",
    "julio": "July",
    "agosto": "August",
    "septiembre": "September",
    "octubre": "October",
    "noviembre": "November",
    "diciembre": "December",
}


_MONTH_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b" + re.escape(local) + r"\b", re.IGNORECASE), english)
    for local, english in _EUROPEAN_MONTHS.items()
]


def _normalize_european_months(s: str) -> str:
    for pattern, english in _MONTH_PATTERNS:
        s = pattern.sub(english, s)
    return s


class InvoiceValidator:
    def validate(self, raw: dict[str, Any]) -> InvoiceResult:
        processed = self._normalize_date(dict(raw))
        result = self._coerce(processed)
        self._check_totals(result)
        self._check_negative_amounts(result)
        return result

    def _normalize_date(self, data: dict[str, Any]) -> dict[str, Any]:
        invoice_date = data.get("invoiceDate")
        if invoice_date is None or isinstance(invoice_date, date):
            return data
        if not isinstance(invoice_date, str):
            data["invoiceDate"] = None
            return data
        try:
            date.fromisoformat(invoice_date)
            return data  # Already ISO 8601 — Pydantic handles the rest
        except ValueError:
            pass
        normalized = _normalize_european_months(invoice_date)
        try:
            parsed = dateutil_parser.parse(normalized, dayfirst=True)
            data["invoiceDate"] = parsed.date()
        except (ValueError, OverflowError):
            data["invoiceDate"] = None
        return data

    def _coerce(self, data: dict[str, Any]) -> InvoiceResult:
        try:
            return InvoiceResult.model_validate(data)
        except ValidationError as exc:
            cleaned = dict(data)
            for error in exc.errors():
                if error["loc"]:
                    cleaned[str(error["loc"][0])] = None
            try:
                return InvoiceResult.model_validate(cleaned)
            except ValidationError:
                return InvoiceResult(
                    invoiceDate=None,
                    invoiceReference=None,
                    netAmount=None,
                    vatAmount=None,
                    totalAmount=None,
                )

    def _check_totals(self, result: InvoiceResult) -> None:
        if result.netAmount and result.vatAmount and result.totalAmount:
            currencies = {
                result.netAmount.currency,
                result.vatAmount.currency,
                result.totalAmount.currency,
            }
            if len(currencies) > 1:
                logger.warning(
                    "Currency mismatch in totals: net=%s vat=%s total=%s",
                    result.netAmount.currency,
                    result.vatAmount.currency,
                    result.totalAmount.currency,
                )
                return
            net = result.netAmount.amount
            vat = result.vatAmount.amount
            total = result.totalAmount.amount
            if total != 0 and abs(net + vat - total) / abs(total) > Decimal("0.01"):
                logger.warning(
                    "Totals inconsistency: net=%s vat=%s total=%s", net, vat, total
                )

    def _check_negative_amounts(self, result: InvoiceResult) -> None:
        for key in ("netAmount", "vatAmount", "totalAmount"):
            field: MonetaryAmount | None = getattr(result, key)
            if field is not None and field.amount < 0:
                logger.warning("Negative amount in %s: %s", key, field.amount)
