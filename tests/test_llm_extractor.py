import json
from unittest.mock import MagicMock

from app.services.llm_extractor import _FIVE_KEYS, LLMExtractor


def _make_mock_model(content: str) -> MagicMock:
    mock = MagicMock()
    mock.create_chat_completion.return_value = {
        "choices": [{"message": {"content": content}}]
    }
    return mock


def test_extract_fields_returns_all_five_keys_for_valid_invoice_text() -> None:
    payload = {
        "invoiceDate": "2024-01-15",
        "invoiceReference": "INV-001",
        "netAmount": {"amount": 100.0, "currency": "EUR"},
        "vatAmount": {"amount": 20.0, "currency": "EUR"},
        "totalAmount": {"amount": 120.0, "currency": "EUR"},
    }
    extractor = LLMExtractor(_make_mock_model(json.dumps(payload)))

    result = extractor.extract_fields("Invoice text here.")

    assert set(result.keys()) == _FIVE_KEYS
    assert result["invoiceDate"] == "2024-01-15"
    assert result["invoiceReference"] == "INV-001"


def test_extract_fields_returns_null_values_on_completely_malformed_output() -> None:
    extractor = LLMExtractor(_make_mock_model("I cannot parse this invoice."))

    result = extractor.extract_fields("Some text")

    assert set(result.keys()) == _FIVE_KEYS
    assert all(v is None for v in result.values())


def test_extract_fields_extracts_prose_wrapped_json_when_all_amounts_are_null() -> None:
    payload = {
        "invoiceDate": "2024-03-10",
        "invoiceReference": "REF-456",
        "netAmount": None,
        "vatAmount": None,
        "totalAmount": None,
    }
    wrapped = f"Here is the extracted data:\n{json.dumps(payload)}\nEnd."
    extractor = LLMExtractor(_make_mock_model(wrapped))

    result = extractor.extract_fields("text")

    assert set(result.keys()) == _FIVE_KEYS
    assert result["invoiceDate"] == "2024-03-10"
    assert result["invoiceReference"] == "REF-456"


def test_extract_fields_extracts_json_from_prose_with_nested_amount_objects() -> None:
    payload = {
        "invoiceDate": "2024-01-15",
        "invoiceReference": "INV-001",
        "netAmount": {"amount": 100.0, "currency": "EUR"},
        "vatAmount": {"amount": 20.0, "currency": "EUR"},
        "totalAmount": {"amount": 120.0, "currency": "EUR"},
    }
    wrapped = f"Here is the result: {json.dumps(payload)} End."
    extractor = LLMExtractor(_make_mock_model(wrapped))

    result = extractor.extract_fields("text")

    assert result["invoiceDate"] == "2024-01-15"
    assert result["netAmount"] == {"amount": 100.0, "currency": "EUR"}


def test_extract_fields_always_returns_all_five_keys_when_partial_json_returned() -> (
    None
):
    partial = {"invoiceDate": "2024-06-01", "invoiceReference": "X-99"}
    extractor = LLMExtractor(_make_mock_model(json.dumps(partial)))

    result = extractor.extract_fields("partial text")

    assert set(result.keys()) == _FIVE_KEYS
    assert result["invoiceDate"] == "2024-06-01"
    assert result["netAmount"] is None
    assert result["vatAmount"] is None
    assert result["totalAmount"] is None


def test_extract_fields_returns_nulls_on_invalid_json_after_regex_fallback() -> None:
    extractor = LLMExtractor(_make_mock_model("Result: {broken json here}"))

    result = extractor.extract_fields("text")

    assert set(result.keys()) == _FIVE_KEYS
    assert all(v is None for v in result.values())


def test_extract_fields_returns_all_null_when_llm_returns_json_array() -> None:
    extractor = LLMExtractor(_make_mock_model("[]"))

    result = extractor.extract_fields("text")

    assert set(result.keys()) == _FIVE_KEYS
    assert all(v is None for v in result.values())


def test_extract_fields_returns_all_null_when_llm_returns_json_number() -> None:
    extractor = LLMExtractor(_make_mock_model("42"))

    result = extractor.extract_fields("text")

    assert set(result.keys()) == _FIVE_KEYS
    assert all(v is None for v in result.values())


def test_extract_fields_extracts_first_json_object_when_prose_contains_multiple() -> (
    None
):
    first = {"invoiceDate": "2024-07-01", "invoiceReference": "FIRST"}
    second = {"invoiceDate": "2024-08-01", "invoiceReference": "SECOND"}
    raw = f"First: {json.dumps(first)} and also: {json.dumps(second)}"
    extractor = LLMExtractor(_make_mock_model(raw))

    result = extractor.extract_fields("text")

    assert result["invoiceDate"] == "2024-07-01"
    assert result["invoiceReference"] == "FIRST"


def test_extract_fields_returns_all_null_when_choices_list_is_empty() -> None:
    mock = MagicMock()
    mock.create_chat_completion.return_value = {"choices": []}
    extractor = LLMExtractor(mock)

    result = extractor.extract_fields("text")

    assert set(result.keys()) == _FIVE_KEYS
    assert all(v is None for v in result.values())


def test_extract_fields_returns_all_null_when_content_is_none() -> None:
    mock = MagicMock()
    mock.create_chat_completion.return_value = {
        "choices": [{"message": {"content": None}}]
    }
    extractor = LLMExtractor(mock)

    result = extractor.extract_fields("text")

    assert set(result.keys()) == _FIVE_KEYS
    assert all(v is None for v in result.values())


def test_extract_fields_returns_all_null_when_opening_brace_is_never_closed() -> None:
    # LLM output has an open brace that is never closed — graceful fallback to all-null
    extractor = LLMExtractor(_make_mock_model("Here is the result: {unclosed"))

    result = extractor.extract_fields("text")

    assert set(result.keys()) == _FIVE_KEYS
    assert all(v is None for v in result.values())


def test_extract_fields_handles_escaped_quotes_in_prose_wrapped_json() -> None:
    # The model output contains a JSON object wrapped in prose, with an escaped
    # quote inside a string value.  _extract_json_object must not treat the
    # escaped quote as the end of the string.
    inner = json.dumps(
        {
            "invoiceDate": None,
            "invoiceReference": 'INV "special"',
            "netAmount": None,
            "vatAmount": None,
            "totalAmount": None,
        }
    )
    wrapped = f"Extracted data: {inner}"
    extractor = LLMExtractor(_make_mock_model(wrapped))

    result = extractor.extract_fields("text")

    assert set(result.keys()) == _FIVE_KEYS
    assert result["invoiceReference"] == 'INV "special"'
