"""Logging setup: one JSON (or text) line per event on stderr, tagged with the trace_id."""

import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any, Literal, TextIO

from portfolio_agent.application.observability import current_trace_id

ROOT_LOGGER = "portfolio_agent"
REDACT_KEY = re.compile(r"(^|_)(token|secret|password|api_key)$")
MAX_VALUE_CHARS = 500


def _clean(key: str, value: Any, max_chars: int) -> Any:

    if REDACT_KEY.search(key.lower()):
        return "***"

    if isinstance(value, str) and len(value) > max_chars:
        return value[:max_chars] + "…"

    return value


def _fields(record: logging.LogRecord, max_chars: int) -> dict[str, Any]:
    fields: dict[str, Any] = getattr(record, "fields", {})
    return {key: _clean(key, value, max_chars) for key, value in fields.items()}


class _Formatter(logging.Formatter):
    def __init__(self, max_value_chars: int = MAX_VALUE_CHARS) -> None:
        super().__init__()
        self.max_value_chars = max_value_chars


class JsonFormatter(_Formatter):
    def format(self, record: logging.LogRecord) -> str:

        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
            "trace_id": current_trace_id(),
            **_fields(record, self.max_value_chars),
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str, ensure_ascii=False)


class TextFormatter(_Formatter):
    def format(self, record: logging.LogRecord) -> str:

        time = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        trace = (current_trace_id() or "-")[:8]
        fields = " ".join(
            f"{key}={value}" for key, value in _fields(record, self.max_value_chars).items()
        )
        line = f"{time} {record.levelname:<7} [{trace}] {record.getMessage()} {fields}".rstrip()

        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


def configure_logging(
    level: str = "INFO",
    fmt: Literal["json", "text"] = "json",
    stream: TextIO | None = None,
    max_value_chars: int = MAX_VALUE_CHARS,
) -> None:

    handler = logging.StreamHandler(stream or sys.stderr)
    formatter = JsonFormatter if fmt == "json" else TextFormatter
    handler.setFormatter(formatter(max_value_chars))
    logger = logging.getLogger(ROOT_LOGGER)
    logger.handlers = [handler]
    logger.setLevel(level)
    logger.propagate = False
