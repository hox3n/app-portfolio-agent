"""Pydantic input/output models for every tool."""

import math
from datetime import date
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from portfolio_agent.domain.models import (
    Action,
    Anomaly,
    DatasetInfo,
    Decision,
    KpiRow,
    MetricRow,
    Period,
    Platform,
)


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GetSchemaInput(ToolInput):
    pass


class SchemaOutput(BaseModel):
    dataset: DatasetInfo
    kpi_definitions: dict[str, str]


class RunSqlInput(ToolInput):
    sql: str = Field(
        min_length=1,
        max_length=2000,
        description="One read-only SELECT over the app_metrics table, DuckDB dialect.",
    )


class RunSqlOutput(BaseModel):
    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int = Field(ge=0)
    truncated: bool

    @model_validator(mode="after")
    def _check_count(self) -> Self:
        if self.row_count != len(self.rows):
            raise ValueError("row_count does not match rows")
        return self


class MetricsQuery(ToolInput):
    start: date = Field(description="First day of the period, inclusive (YYYY-MM-DD).")
    end: date = Field(description="Last day of the period, inclusive (YYYY-MM-DD).")
    apps: list[str] | None = Field(default=None, description="App names to include; omit for all.")
    platforms: list[Platform] | None = Field(
        default=None, description="Platforms to include; omit for all."
    )
    countries: list[str] | None = Field(
        default=None, description="Countries to include; omit for all."
    )

    @model_validator(mode="after")
    def _check_order(self) -> Self:
        if self.start > self.end:
            raise ValueError("start must be on or before end")
        return self

    @property
    def period(self) -> Period:
        return Period(start=self.start, end=self.end)


class MetricsOutput(BaseModel):
    period: Period
    rows: list[MetricRow]


class KpisOutput(BaseModel):
    period: Period
    kpis: list[KpiRow]

    @model_validator(mode="after")
    def _check_finite(self) -> Self:
        for kpi in self.kpis:
            values = (kpi.ua_cost, kpi.revenue, kpi.profit, kpi.roas, kpi.cpi, kpi.arpi)
            if any(v is not None and not math.isfinite(v) for v in values):
                raise ValueError(f"non-finite KPI value for {kpi.pair}")
        return self


class BudgetRulesInput(ToolInput):
    kpis: list[KpiRow] = Field(min_length=1)


class DecisionsOutput(BaseModel):
    decisions: list[Decision]
    counts: dict[Action, int]

    @model_validator(mode="after")
    def _check_counts(self) -> Self:
        if sum(self.counts.values()) != len(self.decisions):
            raise ValueError("counts do not match decisions")
        return self


class AnomalyInput(ToolInput):
    previous: list[KpiRow] = Field(min_length=1)
    current: list[KpiRow] = Field(min_length=1)


class AnomaliesOutput(BaseModel):
    anomalies: list[Anomaly]


class ExportInput(ToolInput):
    columns: list[str] = Field(min_length=1)
    rows: list[dict[str, Any]]
    filename: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$")


class ExportResult(BaseModel):
    path: str
    row_count: int = Field(ge=0)
