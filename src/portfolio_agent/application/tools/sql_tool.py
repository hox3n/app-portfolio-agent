"""run_sql tool: guarded, read-only SQL over app_metrics."""

from portfolio_agent.application.guardrails.sql_guard import SqlGuardError, validate_select
from portfolio_agent.application.ports import MetricsRepository, RepositoryError
from portfolio_agent.application.tools.contracts import RunSqlInput, RunSqlOutput
from portfolio_agent.application.tools.registry import Tool, ToolExecutionError


def make_run_sql_tool(
    repository: MetricsRepository, max_rows: int
) -> Tool[RunSqlInput, RunSqlOutput]:

    def run(inp: RunSqlInput) -> RunSqlOutput:
        try:
            # One extra row lets us tell the caller the result was truncated.
            safe_sql = validate_select(inp.sql, max_rows + 1)
        except SqlGuardError as e:
            raise ToolExecutionError(e.code, str(e)) from e
        try:
            result = repository.run_select(safe_sql, max_rows)
        except RepositoryError as e:
            raise ToolExecutionError("query_failed", str(e)) from e
        return RunSqlOutput(
            sql=safe_sql,
            columns=result.columns,
            rows=result.rows,
            row_count=len(result.rows),
            truncated=result.truncated,
        )

    return Tool(
        name="run_sql",
        description=(
            "Run one read-only SELECT on the app_metrics table (DuckDB SQL). "
            f"At most {max_rows} rows are returned. Use for questions compute_kpis can't answer."
        ),
        input_model=RunSqlInput,
        output_model=RunSqlOutput,
        func=run,
        llm_exposed=True,
    )
