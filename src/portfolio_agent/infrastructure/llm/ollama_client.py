"""LLMClient for local Ollama."""

import logging
import time
from collections.abc import Sequence
from typing import Any

import httpx
import ollama
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree

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


def _trace_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    return {
        "messages": [to_ollama_message(m) for m in inputs.get("messages") or []],
        "tools": [t.get("function", {}).get("name") for t in inputs.get("tools") or []],
        "structured_output": inputs.get("response_schema") is not None,
    }


def _trace_outputs(response: Any) -> dict[str, Any]:
    if not isinstance(response, LLMResponse):
        return {"output": response}
    usage = None
    if response.input_tokens is not None and response.output_tokens is not None:
        usage = {
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "total_tokens": response.input_tokens + response.output_tokens,
        }
    return {
        "content": response.content,
        "tool_calls": [c.model_dump() for c in response.tool_calls],
        "usage_metadata": usage,
    }


class OllamaClient:
    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        *,
        think: bool = False,
        temperature: float = 0.0,
        timeout_s: float = 60.0,
        client: ollama.Client | None = None,
    ) -> None:
        self._model = model
        self._think = think
        self._temperature = temperature
        self._client = client or ollama.Client(host=base_url, timeout=timeout_s)

    @traceable(
        run_type="llm", name="ollama", process_inputs=_trace_inputs, process_outputs=_trace_outputs
    )
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
                options={"temperature": self._temperature},
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

        run = get_current_run_tree()
        if run is not None:
            run.metadata.update(
                {
                    "ls_provider": "ollama",
                    "ls_model_name": self._model,
                    "ls_temperature": self._temperature,
                }
            )
        return LLMResponse(
            content=response.message.content or "",
            tool_calls=calls,
            input_tokens=response.prompt_eval_count,
            output_tokens=response.eval_count,
        )
