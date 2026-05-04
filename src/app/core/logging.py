"""
Structured JSON logging.

Drop-in replacement for the previous ``logging.basicConfig`` setup. Logs
emit one JSON object per line so downstream collectors (Datadog,
CloudWatch, Vector, ...) can parse without grok regexes.

Per-request correlation: the request-logging middleware in ``main.py``
already generates a ``request_id`` and stores it in a ContextVar
(:data:`request_id_var`). Every log record this formatter emits picks
up the current value and includes it as ``request_id`` in the output.

Disable JSON output by setting ``LOG_FORMAT=text`` (useful for
local debugging when you want human-readable lines).
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------- Context vars
#
# `request_id_var` is the per-request correlation id. The HTTP middleware
# in `main.py` calls `request_id_var.set(...)` at the start of every
# request and resets it at the end. Logs emitted within that scope pick
# up the value automatically.

request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


# ---------------------------------------------------------- Formatters


class JSONLogFormatter(logging.Formatter):
    """Render every log record as a single-line JSON object."""

    # Keys we always include if present.
    _STANDARD = (
        "name",
        "levelname",
        "module",
        "funcName",
        "lineno",
        "process",
        "thread",
    )

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        payload: dict[str, Any] = {
            "ts": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = record.stack_info

        # Pull the per-request correlation id off the ContextVar.
        rid = request_id_var.get()
        if rid:
            payload["request_id"] = rid

        # Anything passed via `logger.info(..., extra={...})` goes into
        # `record.__dict__`; promote keys that aren't standard logging
        # attributes so callers can attach domain-specific fields.
        skip = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__)
        skip.update({"args", "msg", "message", "exc_info", "exc_text", "stack_info"})
        for key, value in record.__dict__.items():
            if key in skip:
                continue
            if key.startswith("_"):
                continue
            try:
                json.dumps(value, default=str)
                payload[key] = value
            except (TypeError, ValueError):
                payload[key] = repr(value)

        return json.dumps(payload, default=str, ensure_ascii=False)


class TextLogFormatter(logging.Formatter):
    """Human-readable formatter for local dev (LOG_FORMAT=text)."""

    DEFAULT_FMT = (
        "%(asctime)s %(levelname)-7s [%(name)s] "
        "[req=%(_req_short)s] %(message)s"
    )

    def __init__(self) -> None:
        super().__init__(self.DEFAULT_FMT)

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        rid = request_id_var.get()
        record.__dict__["_req_short"] = (rid[:8] + "…") if rid else "-"
        return super().format(record)


# ---------------------------------------------------------- Setup


def configure_logging(
    *,
    level: str = "INFO",
    fmt: str = "json",
    log_dir: Optional[str] = "logs",
    log_file: str = "app.log",
) -> None:
    """Wire up a single root handler emitting JSON (or text) lines.

    Idempotent: replaces existing handlers on the root logger so it's
    safe to call again from tests.
    """
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)

    formatter: logging.Formatter
    if fmt.lower() == "text":
        formatter = TextLogFormatter()
    else:
        formatter = JSONLogFormatter()

    stream_handler = logging.StreamHandler(stream=sys.stdout)
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    if log_dir:
        try:
            Path(log_dir).mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                Path(log_dir) / log_file,
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
        except Exception:
            # Non-fatal: still have stdout. Don't take the app down because
            # the logs directory wasn't writable.
            logging.getLogger(__name__).exception(
                "Unable to attach RotatingFileHandler at %s/%s", log_dir, log_file
            )

    root.setLevel(level.upper())


def set_request_id(request_id: Optional[str]) -> None:
    """Convenience setter for the per-request correlation id."""
    request_id_var.set(request_id)
