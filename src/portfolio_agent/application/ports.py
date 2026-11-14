"""Interfaces the application depends on: LLM, metrics repository, exporter, sessions, tracer."""

from collections.abc import Sequence
from typing import Any, Protocol

from pydantic import BaseModel

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
