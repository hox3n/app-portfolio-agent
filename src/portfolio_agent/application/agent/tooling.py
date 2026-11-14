"""Helpers for calling tools from graph nodes and turning results into records and tables."""

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from portfolio_agent.application.schemas import Plan, Table, ToolCallRecord, ToolError
from portfolio_agent.application.tools.contracts import KpisOutput, MetricsOutput, RunSqlOutput
from portfolio_agent.application.tools.registry import ToolArgs, ToolRegistry, ToolResult
from portfolio_agent.domain.models import KpiRow, MetricRow

GROUP_COLUMNS = ["installs", "ua_cost", "revenue", "profit", "roas", "cpi", "arpi"]

OutputT = TypeVar("OutputT", bound=BaseModel)


@dataclass(frozen=True)
class Step(Generic[OutputT]):
    output: OutputT | None
    record: ToolCallRecord
    error: ToolError | None


def record(result: ToolResult) -> ToolCallRecord:
    return ToolCallRecord(
        tool=result.tool,
        ok=result.ok,
        duration_ms=result.duration_ms,
        error_code=result.error.code if result.error else None,
    )


def call_tool(
    tools: ToolRegistry, name: str, args: ToolArgs, output_type: type[OutputT]
) -> Step[OutputT]:
    result = tools.call(name, args)
    output = result.output if isinstance(result.output, output_type) else None
    return Step(output=output, record=record(result), error=result.error)


def query_args(plan: Plan) -> dict[str, Any]:
    args: dict[str, Any] = {"start": plan.start, "end": plan.end}
    for field in ("apps", "platforms", "countries"):
        if getattr(plan, field):
            args[field] = getattr(plan, field)
    return args


def table_from(output: BaseModel | None, source: str) -> Table | None:
    if isinstance(output, RunSqlOutput):
        return Table(columns=output.columns, rows=output.rows, source=source)
    if isinstance(output, KpisOutput) and output.groups is not None:
        dims = list(output.groups[0].group) if output.groups else []
        rows = [{**g.group, **g.model_dump(include=set(GROUP_COLUMNS))} for g in output.groups]
        return Table(columns=dims + GROUP_COLUMNS, rows=rows, source=source)
    if isinstance(output, KpisOutput):
        rows = [k.model_dump() for k in output.kpis]
        return Table(columns=list(KpiRow.model_fields), rows=rows, source=source)
    if isinstance(output, MetricsOutput):
        rows = [r.model_dump() for r in output.rows]
        return Table(columns=list(MetricRow.model_fields), rows=rows, source=source)
    return None
