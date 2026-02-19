import json
import logging

import pytest


def test_json_formatter_emits_valid_json(caplog: logging.LogRecord) -> None:
    from app.core.logging import JsonFormatter

    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="test message",
        args=(),
        exc_info=None,
    )
    output = formatter.format(record)
    parsed = json.loads(output)
    assert parsed["message"] == "test message"
    assert parsed["level"] == "INFO"
    assert "timestamp" in parsed


def test_json_formatter_includes_extra_fields() -> None:
    from app.core.logging import JsonFormatter

    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="request complete",
        args=(),
        exc_info=None,
    )
    record.__dict__["request_id"] = "abc123"
    record.__dict__["status_code"] = 200
    output = formatter.format(record)
    parsed = json.loads(output)
    assert parsed["request_id"] == "abc123"
    assert parsed["status_code"] == 200


def test_json_formatter_renders_exception_info() -> None:
    import sys

    from app.core.logging import JsonFormatter

    formatter = JsonFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname="",
        lineno=0,
        msg="something failed",
        args=(),
        exc_info=exc_info,
    )
    output = formatter.format(record)
    parsed = json.loads(output)
    assert "exception" in parsed
    assert "ValueError" in parsed["exception"]
    assert "boom" in parsed["exception"]
    assert "Traceback" in parsed["exception"]


def test_configure_logging_sets_log_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings
    from app.core.logging import configure_logging

    monkeypatch.setenv("API_KEY", "test")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        configure_logging(settings.log_level)
        root_logger = logging.getLogger()
        assert root_logger.level == logging.WARNING
    finally:
        get_settings.cache_clear()
        configure_logging("INFO")
