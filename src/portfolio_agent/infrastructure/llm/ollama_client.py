"""LLMClient for local Ollama."""

import logging
import time
from collections.abc import Sequence
from typing import Any

import httpx
import ollama

from portfolio_agent.application.observability import log_event
from portfolio_agent.application.ports import ChatMessage, LLMError, LLMResponse, ToolCall

logger = logging.getLogger(__name__)


def to_ollama_message(message: ChatMessage) -> dict[str, Any]:

    payload: dict[str, Any] = {"role": message.role, "content": message.content}

    if message.tool_calls:
        payload["tool_calls"] = [
            {"function": {"name": c.name, "arguments": c.arguments}} for c in message.tool_calls
        ]

    if message.tool_name:
        payload["tool_name"] = message.tool_name

    return payload


class OllamaClient:
    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        *,
        think: bool = False,
        timeout_s: float = 60.0,
        client: ollama.Client | None = None,
    ) -> None:
        self._model = model
        self._think = think
        self._client = client or ollama.Client(host=base_url, timeout=timeout_s)

    def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        response_schema: dict[str, Any] | None = None,
    ) -> LLMResponse:

        started = time.perf_counter()
        try:
            response = self._client.chat(
                model=self._model,
                messages=[to_ollama_message(m) for m in messages],
                tools=list(tools) if tools else None,
                format=response_schema,
                think=self._think,
                options={"temperature": 0},
            )
        except (ollama.ResponseError, ConnectionError, httpx.HTTPError) as e:
            raise LLMError(f"Ollama request failed: {e}") from e

        calls = [
            ToolCall(name=c.function.name, arguments=dict(c.function.arguments))
            for c in response.message.tool_calls or []
        ]

        log_event(
            logger,
            "llm_call",
            model=self._model,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
            prompt_tokens=response.prompt_eval_count,
            output_tokens=response.eval_count,
            tool_calls=[c.name for c in calls],
            structured=response_schema is not None,
        )

        return LLMResponse(content=response.message.content or "", tool_calls=calls)
