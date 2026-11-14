"""Request/response contracts: Plan, AgentResult, ToolError and session state."""

import json
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Workflow = Literal["qa", "budget_review", "anomaly_check", "export"]
Route = Literal["qa", "budget_review", "anomaly_check", "export", "refuse", "clarify"]
Status = Literal["ok", "refused", "needs_clarification", "error"]
PeriodHint = Literal[
    "none", "last_7_days", "last_14_days", "last_30_days", "last_month", "last_quarter", "custom"
]

MAX_SESSION_TURNS = 10


class ToolError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class Plan(BaseModel):
    workflow: Route
    period: PeriodHint = "none"
    start: date | None = None
    end: date | None = None
    apps: list[str] | None = None
    platforms: list[str] | None = None
    countries: list[str] | None = None
    reason: str = ""

    @field_validator("start", "end", mode="before")
    @classmethod
    def _empty_date_is_none(cls, value: Any) -> Any:
        return None if value in ("", "null", "none") else value

    @field_validator("apps", "platforms", "countries", mode="before")
    @classmethod
    def _wrap_single_value(cls, value: Any) -> Any:
        if value in ("", []):
            return None
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("["):
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    pass
            return [text]
        return value


class ToolCallRecord(BaseModel):
    tool: str
    ok: bool
    duration_ms: float
    error_code: str | None = None


class Table(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    source: str


class AgentResult(BaseModel):
    trace_id: str
    session_id: str
    workflow: Workflow | None = None
    status: Status
    summary: str
    data: dict[str, Any] = Field(default_factory=dict)
    table: Table | None = None
    plan: Plan | None = None
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    duration_ms: float = 0.0


class Turn(BaseModel):
    request: str
    workflow: Workflow | None
    status: Status
    summary: str


class Session(BaseModel):
    turns: list[Turn] = Field(default_factory=list)
    last_table: Table | None = None

    def with_turn(
        self, turn: Turn, table: Table | None, max_turns: int = MAX_SESSION_TURNS
    ) -> "Session":
        return Session(
            turns=[*self.turns, turn][-max_turns:],
            last_table=table or self.last_table,
        )
