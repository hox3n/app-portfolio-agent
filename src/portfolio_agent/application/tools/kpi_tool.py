"""compute_kpis tool: revenue, profit, ROAS, CPI and ARPI for a period."""

from collections.abc import Callable

from portfolio_agent.application.ports import MetricsRepository
from portfolio_agent.application.tools.contracts import KpiQuery, KpisOutput
from portfolio_agent.application.tools.metrics_tool import check_query, fetch_rows
from portfolio_agent.application.tools.registry import Tool
from portfolio_agent.domain.kpis import compute_all, group_totals, totals_of
from portfolio_agent.domain.models import DatasetInfo


def make_compute_kpis_tool(
    repository: MetricsRepository, dataset: Callable[[], DatasetInfo]
) -> Tool[KpiQuery, KpisOutput]:

    def run(query: KpiQuery) -> KpisOutput:
        check_query(query, dataset())
        rows = fetch_rows(repository, query)
        if query.group_by:
            return KpisOutput(
                period=query.period,
                kpis=[],
                totals=totals_of(rows),
                groups=group_totals(rows, query.group_by),
            )
        return KpisOutput(period=query.period, kpis=compute_all(rows), totals=totals_of(rows))

    return Tool(
        name="compute_kpis",
        description=(
            "Revenue, profit, ROAS, CPI and ARPI per app/platform/country for a period, "
            "with optional filters, plus totals over all returned rows. With group_by it "
            "returns one row per app, platform or country instead. Prefer this over SQL for KPIs."
        ),
        input_model=KpiQuery,
        output_model=KpisOutput,
        func=run,
        llm_exposed=True,
    )
