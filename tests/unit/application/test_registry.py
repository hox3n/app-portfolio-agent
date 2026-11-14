"""Tests for the tool registry contract wrapper."""

import json
import logging
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict, Field

from portfolio_agent.application.schemas import ToolError
from portfolio_agent.application.tools.registry import (
    Tool,
    ToolExecutionError,
    ToolRegistry,
    _trace_tool_outputs,
)


class EchoIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    n: int = Field(ge=0)


class EchoOut(BaseModel):
    doubled: int = Field(ge=0)


def double(inp: EchoIn) -> EchoOut:
    return EchoOut(doubled=inp.n * 2)


def fail(inp: EchoIn) -> EchoOut:
    raise ToolExecutionError("too_big", "n is too big", {"max": 10})


def crash(inp: EchoIn) -> EchoOut:
    raise RuntimeError("secret internal detail")


def broken(inp: EchoIn) -> EchoOut:
    return EchoOut.model_construct(doubled=-1)


REGISTRY = ToolRegistry(
    [
        Tool("double", "Double a number", EchoIn, EchoOut, double, llm_exposed=True),
        Tool("fail", "Always fails", EchoIn, EchoOut, fail),
        Tool("crash", "Always crashes", EchoIn, EchoOut, crash),
        Tool("broken", "Returns invalid output", EchoIn, EchoOut, broken),
    ]
)


def test_success() -> None:
    result = REGISTRY.call("double", {"n": 4})
    assert result.ok
    assert result.output == EchoOut(doubled=8)
    assert result.duration_ms >= 0


def test_accepts_model_as_input() -> None:
    assert REGISTRY.call("double", EchoIn(n=2)).output == EchoOut(doubled=4)


def test_unknown_tool_lists_allowed() -> None:
    result = REGISTRY.call("nope", {})
    assert result.error is not None
    assert result.error.code == "unknown_tool"
    assert "double" in result.error.details["allowed"]


@pytest.mark.parametrize("args", [{"n": -1}, {"n": "x"}, {}, {"n": 1, "extra": True}])
def test_invalid_input(args: dict[str, Any]) -> None:
    result = REGISTRY.call("double", args)
    assert result.error is not None
    assert result.error.code == "invalid_input"
    assert result.error.details["errors"]


def test_expected_failure_passed_through() -> None:
    result = REGISTRY.call("fail", {"n": 1})
    assert result.error is not None
    assert (result.error.code, result.error.details) == ("too_big", {"max": 10})


def test_crash_becomes_internal_error_without_leaking_details() -> None:
    result = REGISTRY.call("crash", {"n": 1})
    assert result.error is not None
    assert result.error.code == "internal_error"
    assert "secret" not in result.to_llm_content()


def test_invalid_output_caught() -> None:
    result = REGISTRY.call("broken", {"n": 1})
    assert result.error is not None
    assert result.error.code == "invalid_output"


def test_llm_specs_only_include_exposed_tools() -> None:
    specs = REGISTRY.llm_tool_specs()
    assert [s["function"]["name"] for s in specs] == ["double"]
    assert "n" in specs[0]["function"]["parameters"]["properties"]


def test_llm_content_is_json() -> None:
    assert json.loads(REGISTRY.call("double", {"n": 1}).to_llm_content()) == {"doubled": 2}
    assert json.loads(REGISTRY.call("fail", {"n": 1}).to_llm_content())["error"]["code"] == (
        "too_big"
    )


def test_every_call_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="portfolio_agent")
    REGISTRY.call("double", {"n": 1})
    REGISTRY.call("fail", {"n": 1})
    records = [r for r in caplog.records if r.getMessage() == "tool_call"]
    fields = [getattr(r, "fields", {}) for r in records]
    assert [(f["tool"], f["ok"], f["error_code"]) for f in fields] == [
        ("double", True, None),
        ("fail", False, "too_big"),
    ]
    assert [r.levelname for r in records] == ["INFO", "WARNING"]


def test_llm_only_hides_graph_tools() -> None:
    result = REGISTRY.call("fail", {"n": 1}, llm_only=True)
    assert result.error is not None
    assert result.error.code == "unknown_tool"
    assert result.error.details["allowed"] == ["double"]


def test_tool_trace_payload() -> None:
    error = ToolError(code="too_big", message="n is too big")
    assert _trace_tool_outputs((EchoOut(doubled=2), None)) == {
        "output": {"doubled": 2},
        "error": None,
    }
    assert _trace_tool_outputs((None, error))["error"]["code"] == "too_big"
