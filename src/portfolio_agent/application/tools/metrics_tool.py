"""fetch_metrics tool, plus query checks shared with compute_kpis."""

from collections.abc import Callable

from portfolio_agent.application.ports import MetricsRepository, RepositoryError
from portfolio_agent.application.tools.contracts import MetricsOutput, MetricsQuery
from portfolio_agent.application.tools.registry import Tool, ToolExecutionError
from portfolio_agent.domain.kpis import totals_of
from portfolio_agent.domain.models import DatasetInfo, MetricRow


def check_query(query: MetricsQuery, info: DatasetInfo) -> None:

    if query.start < info.date_min or query.end > info.date_max:
        raise ToolExecutionError(
            "period_out_of_range",
            f"data is available from {info.date_min} to {info.date_max}",
            {"available": {"start": info.date_min.isoformat(), "end": info.date_max.isoformat()}},
        )

    for field, allowed in (("apps", info.apps), ("countries", info.countries)):
        unknown = sorted(set(getattr(query, field) or []) - set(allowed))

        if unknown:
            raise ToolExecutionError(
                "unknown_value",
                f"unknown {field}: {', '.join(unknown)}",
                {"field": field, "allowed": allowed},
            )


def fetch_rows(repository: MetricsRepository, query: MetricsQuery) -> list[MetricRow]:

    try:
        return repository.fetch_metrics(
            query.period, apps=query.apps, platforms=query.platforms, countries=query.countries
        )
    except RepositoryError as e:
        raise ToolExecutionError("query_failed", str(e)) from e


def make_fetch_metrics_tool(
    repository: MetricsRepository, dataset: Callable[[], DatasetInfo]
) -> Tool[MetricsQuery, MetricsOutput]:

    def run(query: MetricsQuery) -> MetricsOutput:
        check_query(query, dataset())

        rows = fetch_rows(repository, query)
        return MetricsOutput(period=query.period, rows=rows, totals=totals_of(rows))

    return Tool(
        name="fetch_metrics",
        description=(
            "Total installs, in-app revenue, ads revenue and UA cost per app/platform/country "
            "for a period, with optional filters, plus totals over all returned rows."
        ),
        input_model=MetricsQuery,
        output_model=MetricsOutput,
        func=run,
        llm_exposed=True,
    )
