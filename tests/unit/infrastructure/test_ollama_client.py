"""Tests for the Ollama adapter using a stub instead of a real server."""

from typing import Any, cast

import ollama
import pytest

from portfolio_agent.application.ports import ChatMessage, LLMError, ToolCall
from portfolio_agent.infrastructure.llm.ollama_client import OllamaClient, to_ollama_message

HELLO = [ChatMessage(role="user", content="hi")]


class StubClient:
    def __init__(self, response: ollama.ChatResponse | Exception) -> None:
        self.response = response
        self.kwargs: dict[str, Any] = {}

    def chat(self, **kwargs: Any) -> ollama.ChatResponse:
        self.kwargs = kwargs
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def reply(content: str = "", tools: list[str] | None = None) -> ollama.ChatResponse:
    calls = [
        ollama.Message.ToolCall(function=ollama.Message.ToolCall.Function(name=n, arguments={}))
        for n in tools or []
    ]
    return ollama.ChatResponse(
        message=ollama.Message(role="assistant", content=content, tool_calls=calls or None)
    )


def make(stub: StubClient) -> OllamaClient:
    return OllamaClient("qwen3.5:4b", client=cast(ollama.Client, stub))


def test_sends_think_false_and_temperature_zero() -> None:
    stub = StubClient(reply("hello"))
    assert make(stub).chat(HELLO).content == "hello"
    assert stub.kwargs["think"] is False
    assert stub.kwargs["options"] == {"temperature": 0}
    assert stub.kwargs["model"] == "qwen3.5:4b"


def test_parses_tool_calls() -> None:
    result = make(StubClient(reply(tools=["get_schema"]))).chat(HELLO, tools=[{"x": 1}])
    assert result.tool_calls == [ToolCall(name="get_schema")]


def test_passes_schema_as_format() -> None:
    stub = StubClient(reply("{}"))
    make(stub).chat(HELLO, response_schema={"type": "object"})
    assert stub.kwargs["format"] == {"type": "object"}


def test_connection_error_becomes_llm_error() -> None:
    with pytest.raises(LLMError, match="server down"):
        make(StubClient(ConnectionError("server down"))).chat(HELLO)


def test_message_conversion() -> None:
    tool_msg = ChatMessage(role="tool", content="{}", tool_name="get_schema")
    assert to_ollama_message(tool_msg) == {
        "role": "tool",
        "content": "{}",
        "tool_name": "get_schema",
    }
    call_msg = ChatMessage(
        role="assistant", tool_calls=[ToolCall(name="run_sql", arguments={"sql": "x"})]
    )
    assert to_ollama_message(call_msg)["tool_calls"] == [
        {"function": {"name": "run_sql", "arguments": {"sql": "x"}}}
    ]
