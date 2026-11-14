"""Interfaces the application depends on: LLM, metrics repository, exporter, sessions, tracer."""

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from portfolio_agent.domain.models import DatasetInfo, MetricRow, Period


class RepositoryError(Exception):
    pass


class QueryResult(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    truncated: bool


class MetricsRepository(Protocol):
    def describe(self) -> DatasetInfo: ...

    def fetch_metrics(
        self,
        period: Period,
        *,
        apps: Sequence[str] | None = None,
        platforms: Sequence[str] | None = None,
        countries: Sequence[str] | None = None,
    ) -> list[MetricRow]: ...

    def run_select(self, sql: str, max_rows: int) -> QueryResult: ...


class Exporter(Protocol):
    def export_csv(
        self, columns: Sequence[str], rows: Sequence[Mapping[str, Any]], name: str
    ) -> Path: ...


class LLMError(Exception):
    pass


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_name: str | None = None


class LLMResponse(BaseModel):
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)


class LLMClient(Protocol):
    def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        response_schema: dict[str, Any] | None = None,
    ) -> LLMResponse: ...
