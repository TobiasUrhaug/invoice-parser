import logging
from datetime import date
from decimal import Decimal

import pytest

from app.api.v1.schemas import InvoiceResult, MonetaryAmount
from app.services.validator import InvoiceValidator


def test_valid_dict_produces_correct_invoice_result() -> None:
    raw = {
        "invoiceDate": "2024-01-15",
        "invoiceReference": "INV-2024-001",
        "netAmount": {"amount": 10000, "currency": "NOK"},
        "vatAmount": {"amount": 2500, "currency": "NOK"},
        "totalAmount": {"amount": 12500, "currency": "NOK"},
    }
    result = InvoiceValidator().validate(raw)
    assert isinstance(result, InvoiceResult)
    assert result.invoiceDate == date(2024, 1, 15)
    assert result.invoiceReference == "INV-2024-001"
    assert result.netAmount == MonetaryAmount(amount=Decimal("10000"), currency="NOK")
    assert result.vatAmount == MonetaryAmount(amount=Decimal("2500"), currency="NOK")
    assert result.totalAmount == MonetaryAmount(amount=Decimal("12500"), currency="NOK")


def test_invoice_date_german_format_is_normalised_to_date() -> None:
    raw = {
        "invoiceDate": "15. Januar 2024",
        "invoiceReference": None,
        "netAmount": None,
        "vatAmount": None,
        "totalAmount": None,
    }
    result = InvoiceValidator().validate(raw)
    assert result.invoiceDate == date(2024, 1, 15)


def test_totals_inconsistency_logs_warning_but_returns_all_values(
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw = {
        "invoiceDate": None,
        "invoiceReference": None,
        "netAmount": {"amount": 100, "currency": "NOK"},
        "vatAmount": {"amount": 25, "currency": "NOK"},
        "totalAmount": {"amount": 200, "currency": "NOK"},  # net + vat = 125, not 200
    }
    with caplog.at_level(logging.WARNING):
        result = InvoiceValidator().validate(raw)

    assert result.netAmount is not None
    assert result.vatAmount is not None
    assert result.totalAmount is not None
    assert result.netAmount.amount == Decimal("100")
    assert result.vatAmount.amount == Decimal("25")
    assert result.totalAmount.amount == Decimal("200")
    assert any("inconsisten" in r.message.lower() for r in caplog.records)


def test_field_with_wrong_type_is_returned_as_null() -> None:
    raw = {
        "invoiceDate": 12345,  # int is not a valid date
        "invoiceReference": None,
        "netAmount": None,
        "vatAmount": None,
        "totalAmount": None,
    }
    result = InvoiceValidator().validate(raw)
    assert result.invoiceDate is None


def test_invoice_date_norwegian_format_is_normalised_to_date() -> None:
    raw = {
        "invoiceDate": "15. mars 2024",
        "invoiceReference": None,
        "netAmount": None,
        "vatAmount": None,
        "totalAmount": None,
    }
    result = InvoiceValidator().validate(raw)
    assert result.invoiceDate == date(2024, 3, 15)


def test_invoice_date_french_format_is_normalised_to_date() -> None:
    raw = {
        "invoiceDate": "15 février 2024",
        "invoiceReference": None,
        "netAmount": None,
        "vatAmount": None,
        "totalAmount": None,
    }
    result = InvoiceValidator().validate(raw)
    assert result.invoiceDate == date(2024, 2, 15)


def test_invoice_date_italian_format_is_normalised_to_date() -> None:
    raw = {
        "invoiceDate": "15 gennaio 2024",
        "invoiceReference": None,
        "netAmount": None,
        "vatAmount": None,
        "totalAmount": None,
    }
    result = InvoiceValidator().validate(raw)
    assert result.invoiceDate == date(2024, 1, 15)


def test_invoice_date_spanish_format_is_normalised_to_date() -> None:
    raw = {
        "invoiceDate": "15 enero 2024",
        "invoiceReference": None,
        "netAmount": None,
        "vatAmount": None,
        "totalAmount": None,
    }
    result = InvoiceValidator().validate(raw)
    assert result.invoiceDate == date(2024, 1, 15)


def test_negative_amount_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    raw = {
        "invoiceDate": None,
        "invoiceReference": None,
        "netAmount": {"amount": -100, "currency": "NOK"},
        "vatAmount": None,
        "totalAmount": None,
    }
    with caplog.at_level(logging.WARNING):
        result = InvoiceValidator().validate(raw)

    assert result.netAmount is not None
    assert result.netAmount.amount == Decimal("-100")
    assert any("negative" in r.message.lower() for r in caplog.records)


def test_negative_vat_amount_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    raw = {
        "invoiceDate": None,
        "invoiceReference": None,
        "netAmount": None,
        "vatAmount": {"amount": -25, "currency": "NOK"},
        "totalAmount": None,
    }
    with caplog.at_level(logging.WARNING):
        result = InvoiceValidator().validate(raw)

    assert result.vatAmount is not None
    assert result.vatAmount.amount == Decimal("-25")
    assert any("negative" in r.message.lower() for r in caplog.records)


def test_negative_total_amount_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    raw = {
        "invoiceDate": None,
        "invoiceReference": None,
        "netAmount": None,
        "vatAmount": None,
        "totalAmount": {"amount": -12500, "currency": "NOK"},
    }
    with caplog.at_level(logging.WARNING):
        result = InvoiceValidator().validate(raw)

    assert result.totalAmount is not None
    assert result.totalAmount.amount == Decimal("-12500")
    assert any("negative" in r.message.lower() for r in caplog.records)


def test_monetary_amount_field_with_wrong_type_is_returned_as_null() -> None:
    raw = {
        "invoiceDate": None,
        "invoiceReference": None,
        "netAmount": "not-an-object",
        "vatAmount": None,
        "totalAmount": None,
    }
    result = InvoiceValidator().validate(raw)
    assert result.netAmount is None


def test_zero_amounts_do_not_log_totals_inconsistency_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw = {
        "invoiceDate": None,
        "invoiceReference": None,
        "netAmount": {"amount": 0, "currency": "NOK"},
        "vatAmount": {"amount": 0, "currency": "NOK"},
        "totalAmount": {"amount": 0, "currency": "NOK"},
    }
    with caplog.at_level(logging.WARNING):
        InvoiceValidator().validate(raw)

    assert not any("inconsisten" in r.message.lower() for r in caplog.records)


def test_non_date_string_is_returned_as_null_invoice_date() -> None:
    raw = {
        "invoiceDate": "order #2024-001",
        "invoiceReference": None,
        "netAmount": None,
        "vatAmount": None,
        "totalAmount": None,
    }
    result = InvoiceValidator().validate(raw)
    assert result.invoiceDate is None


def test_mismatched_currencies_logs_currency_warning_and_skips_totals_check(
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw = {
        "invoiceDate": None,
        "invoiceReference": None,
        "netAmount": {"amount": 100, "currency": "NOK"},
        "vatAmount": {"amount": 25, "currency": "NOK"},
        "totalAmount": {"amount": 200, "currency": "EUR"},
    }
    with caplog.at_level(logging.WARNING):
        result = InvoiceValidator().validate(raw)

    assert result.totalAmount is not None
    assert any("currency" in r.message.lower() for r in caplog.records)
    assert not any("inconsisten" in r.message.lower() for r in caplog.records)
