"""export_csv tool: writes a result table to a CSV file."""

from datetime import UTC, datetime

from portfolio_agent.application.observability import current_trace_id
from portfolio_agent.application.ports import Exporter
from portfolio_agent.application.tools.contracts import ExportInput, ExportResult
from portfolio_agent.application.tools.registry import Tool, ToolExecutionError


def make_export_csv_tool(exporter: Exporter) -> Tool[ExportInput, ExportResult]:

    def run(inp: ExportInput) -> ExportResult:
        name = inp.filename or (
            f"export_{current_trace_id() or datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}"
        )
        try:
            path = exporter.export_csv(inp.columns, inp.rows, name)
        except (OSError, ValueError) as e:
            raise ToolExecutionError("export_failed", str(e)) from e
        return ExportResult(path=str(path), row_count=len(inp.rows))

    return Tool(
        name="export_csv",
        description="Save a result table as a CSV file in the export folder.",
        input_model=ExportInput,
        output_model=ExportResult,
        func=run,
    )
