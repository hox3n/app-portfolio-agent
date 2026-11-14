"""Trace context and structured event logging used by the agent and its tools."""

import logging
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)


def current_trace_id() -> str | None:
    return _trace_id.get()


@contextmanager
def trace(trace_id: str | None = None) -> Iterator[str]:
    token = _trace_id.set(trace_id or uuid.uuid4().hex[:16])
    try:
        yield _trace_id.get() or ""
    finally:
        _trace_id.reset(token)


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **fields: Any) -> None:
    logger.log(level, event, extra={"fields": fields})
