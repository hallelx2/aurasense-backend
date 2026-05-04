"""Unit tests for the structured JSON logger."""

from __future__ import annotations

import io
import json
import logging

import pytest

from src.app.core.logging import (
    JSONLogFormatter,
    TextLogFormatter,
    configure_logging,
    request_id_var,
)


def _captured_record(record: logging.LogRecord, formatter: logging.Formatter) -> str:
    return formatter.format(record)


class TestJSONLogFormatter:
    def test_emits_single_line_json(self) -> None:
        f = JSONLogFormatter()
        rec = logging.LogRecord(
            "myapp",
            logging.INFO,
            "/path/to/x.py",
            10,
            "hello %s",
            ("world",),
            None,
        )
        out = f.format(rec)
        # Must be a single line of JSON.
        assert "\n" not in out
        parsed = json.loads(out)
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "myapp"
        assert parsed["msg"] == "hello world"
        assert "ts" in parsed

    def test_includes_request_id_when_set(self) -> None:
        f = JSONLogFormatter()
        token = request_id_var.set("req-abc-123")
        try:
            rec = logging.LogRecord(
                "x", logging.INFO, "x.py", 1, "msg", None, None
            )
            parsed = json.loads(f.format(rec))
            assert parsed["request_id"] == "req-abc-123"
        finally:
            request_id_var.reset(token)

    def test_promotes_extra_fields(self) -> None:
        f = JSONLogFormatter()
        logger = logging.getLogger("extra-test")
        buf = io.StringIO()
        h = logging.StreamHandler(buf)
        h.setFormatter(f)
        logger.addHandler(h)
        logger.setLevel(logging.INFO)
        try:
            logger.info("event", extra={"user_id": "u-1", "duration_s": 0.5})
            parsed = json.loads(buf.getvalue().strip())
            assert parsed["user_id"] == "u-1"
            assert parsed["duration_s"] == 0.5
        finally:
            logger.removeHandler(h)

    def test_includes_exception_traceback(self) -> None:
        f = JSONLogFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            import sys

            exc_info = sys.exc_info()
            rec = logging.LogRecord(
                "x", logging.ERROR, "x.py", 1, "boom-msg", None, exc_info
            )
        parsed = json.loads(f.format(rec))
        assert "exc_info" in parsed
        assert "ValueError" in parsed["exc_info"]


class TestTextLogFormatter:
    def test_text_format_includes_request_id_short(self) -> None:
        f = TextLogFormatter()
        token = request_id_var.set("req-abcdef-12345678")
        try:
            rec = logging.LogRecord(
                "x", logging.INFO, "x.py", 1, "msg", None, None
            )
            out = f.format(rec)
            # Truncated form of the request id makes it into the line.
            assert "req-abcd" in out
        finally:
            request_id_var.reset(token)


class TestConfigureLogging:
    def test_replaces_existing_handlers(self) -> None:
        root = logging.getLogger()
        # Pre-populate with a dummy handler we expect to be replaced.
        existing = logging.NullHandler()
        root.addHandler(existing)
        before = len(root.handlers)

        configure_logging(level="INFO", fmt="json", log_dir=None)
        assert existing not in root.handlers
        # After call: at least the stdout handler is present.
        assert len(root.handlers) >= 1

    def test_text_mode(self) -> None:
        configure_logging(level="DEBUG", fmt="text", log_dir=None)
        # Just ensure no exception and root level is set.
        assert logging.getLogger().level == logging.DEBUG
