"""Tests for trace context and structured logging."""

import io
import json
import logging
from collections.abc import Iterator

import pytest

from portfolio_agent.application.observability import current_trace_id, log_event, trace
from portfolio_agent.infrastructure.observability.logging import ROOT_LOGGER, configure_logging

logger = logging.getLogger(f"{ROOT_LOGGER}.test")


@pytest.fixture
def stream() -> Iterator[io.StringIO]:

    buffer = io.StringIO()
    yield buffer
    root = logging.getLogger(ROOT_LOGGER)
    root.handlers = []
    root.propagate = True


def lines(stream: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in stream.getvalue().splitlines()]


def test_trace_sets_and_resets_id() -> None:

    assert current_trace_id() is None
    with trace() as outer:
        assert current_trace_id() == outer
        with trace("inner") as inner:
            assert current_trace_id() == inner == "inner"
        assert current_trace_id() == outer
    assert current_trace_id() is None


def test_json_line_has_trace_and_fields(stream: io.StringIO) -> None:

    configure_logging(stream=stream)
    with trace("abc123"):
        log_event(logger, "tool_call", tool="run_sql", ok=True, ms=12)
    [line] = lines(stream)
    assert line["event"] == "tool_call"
    assert line["trace_id"] == "abc123"
    assert (line["tool"], line["ok"], line["ms"]) == ("run_sql", True, 12)
    assert line["level"] == "INFO"


def test_secrets_redacted_and_long_values_truncated(stream: io.StringIO) -> None:

    configure_logging(stream=stream)
    log_event(logger, "x", api_key="sk-123", slack_token="xoxb", sql="S" * 2000)
    [line] = lines(stream)
    assert line["api_key"] == line["slack_token"] == "***"
    assert isinstance(line["sql"], str)
    assert len(line["sql"]) == 501


def test_level_filtering(stream: io.StringIO) -> None:

    configure_logging(level="WARNING", stream=stream)
    log_event(logger, "hidden")
    log_event(logger, "shown", level=logging.WARNING)
    assert [line["event"] for line in lines(stream)] == ["shown"]


def test_text_format(stream: io.StringIO) -> None:

    configure_logging(fmt="text", stream=stream)
    with trace("abcdef123456"):
        log_event(logger, "tool_call", tool="get_schema")
    output = stream.getvalue()
    assert "[abcdef12] tool_call tool=get_schema" in output
