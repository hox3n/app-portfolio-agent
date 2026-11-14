"""Logging setup: one JSON (or text) line per event on stderr, tagged with the trace_id."""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any, Literal, TextIO

from portfolio_agent.application.observability import current_trace_id

ROOT_LOGGER = "portfolio_agent"
REDACT_KEY_PARTS = ("token", "secret", "password", "api_key")
MAX_VALUE_CHARS = 500


def _clean(key: str, value: Any) -> Any:

    if any(part in key.lower() for part in REDACT_KEY_PARTS):
        return "***"

    if isinstance(value, str) and len(value) > MAX_VALUE_CHARS:
        return value[:MAX_VALUE_CHARS] + "…"

    return value


def _fields(record: logging.LogRecord) -> dict[str, Any]:
    fields: dict[str, Any] = getattr(record, "fields", {})
    return {key: _clean(key, value) for key, value in fields.items()}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:

        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
            "trace_id": current_trace_id(),
            **_fields(record),
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:

        time = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        trace = (current_trace_id() or "-")[:8]
        fields = " ".join(f"{key}={value}" for key, value in _fields(record).items())
        line = f"{time} {record.levelname:<7} [{trace}] {record.getMessage()} {fields}".rstrip()

        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


def configure_logging(
    level: str = "INFO", fmt: Literal["json", "text"] = "json", stream: TextIO | None = None
) -> None:

    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(JsonFormatter() if fmt == "json" else TextFormatter())
    logger = logging.getLogger(ROOT_LOGGER)
    logger.handlers = [handler]
    logger.setLevel(level)
    logger.propagate = False
