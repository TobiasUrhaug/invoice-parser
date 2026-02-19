from datetime import date
from decimal import Decimal

from app.api.v1.schemas import InvoiceResult, MonetaryAmount


def test_monetary_amount_serializes_correctly() -> None:
    amount = MonetaryAmount(amount=Decimal("100.00"), currency="NOK")
    data = amount.model_dump()
    assert data == {"amount": Decimal("100.00"), "currency": "NOK"}


def test_monetary_amount_with_null_currency_serializes_correctly() -> None:
    amount = MonetaryAmount(amount=Decimal("100.00"), currency=None)
    data = amount.model_dump()
    assert data["currency"] is None


def test_invoice_result_all_fields_serialize_correctly() -> None:
    result = InvoiceResult(
        invoiceDate=date(2024, 1, 15),
        invoiceReference="INV-001",
        netAmount=MonetaryAmount(amount=Decimal("10000.00"), currency="NOK"),
        vatAmount=MonetaryAmount(amount=Decimal("2500.00"), currency="NOK"),
        totalAmount=MonetaryAmount(amount=Decimal("12500.00"), currency="NOK"),
    )
    data = result.model_dump()
    assert data["invoiceDate"] == date(2024, 1, 15)
    assert data["invoiceReference"] == "INV-001"
    assert data["netAmount"] == {"amount": Decimal("10000.00"), "currency": "NOK"}
    assert data["vatAmount"] == {"amount": Decimal("2500.00"), "currency": "NOK"}
    assert data["totalAmount"] == {"amount": Decimal("12500.00"), "currency": "NOK"}


def test_invoice_result_null_fields_are_present_in_output() -> None:
    result = InvoiceResult(
        invoiceDate=None,
        invoiceReference=None,
        netAmount=None,
        vatAmount=None,
        totalAmount=None,
    )
    data = result.model_dump()
    assert set(data.keys()) == {
        "invoiceDate",
        "invoiceReference",
        "netAmount",
        "vatAmount",
        "totalAmount",
    }
    assert data["invoiceDate"] is None
    assert data["invoiceReference"] is None
    assert data["netAmount"] is None
    assert data["vatAmount"] is None
    assert data["totalAmount"] is None


def test_invoice_result_json_serialization_includes_null_fields() -> None:
    result = InvoiceResult(
        invoiceDate=date(2024, 1, 15),
        invoiceReference=None,
        netAmount=None,
        vatAmount=None,
        totalAmount=MonetaryAmount(amount=Decimal("12500.00"), currency="NOK"),
    )
    json_str = result.model_dump_json()
    assert '"invoiceReference":null' in json_str
    assert '"netAmount":null' in json_str
    assert '"vatAmount":null' in json_str
