"""Scripted LLMClient for deterministic tests."""

from collections import deque
from collections.abc import Iterable, Sequence
from typing import Any

from pydantic import BaseModel

from portfolio_agent.application.ports import ChatMessage, LLMError, LLMResponse


class FakeLLMClient:
    def __init__(self, responses: Iterable[LLMResponse | BaseModel | str]) -> None:
        self._responses = deque(responses)
        self.calls: list[list[ChatMessage]] = []

    def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        response_schema: dict[str, Any] | None = None,
    ) -> LLMResponse:
        self.calls.append(list(messages))
        if not self._responses:
            raise LLMError("fake LLM has no scripted responses left")
        item = self._responses.popleft()
        if isinstance(item, LLMResponse):
            return item
        if isinstance(item, BaseModel):
            return LLMResponse(content=item.model_dump_json())
        return LLMResponse(content=item)
