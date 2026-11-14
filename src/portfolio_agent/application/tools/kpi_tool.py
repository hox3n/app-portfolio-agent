"""compute_kpis tool: revenue, profit, ROAS, CPI and ARPI for a period."""

from collections.abc import Callable

from portfolio_agent.application.ports import MetricsRepository
from portfolio_agent.application.tools.contracts import KpisOutput, MetricsQuery
from portfolio_agent.application.tools.metrics_tool import check_query, fetch_rows
from portfolio_agent.application.tools.registry import Tool
from portfolio_agent.domain.kpis import compute_all
from portfolio_agent.domain.models import DatasetInfo


def make_compute_kpis_tool(
    repository: MetricsRepository, dataset: Callable[[], DatasetInfo]
) -> Tool[MetricsQuery, KpisOutput]:

    def run(query: MetricsQuery) -> KpisOutput:
        check_query(query, dataset())
        return KpisOutput(period=query.period, kpis=compute_all(fetch_rows(repository, query)))

    return Tool(
        name="compute_kpis",
        description=(
            "Revenue, profit, ROAS, CPI and ARPI per app/platform/country for a period, "
            "with optional filters. Prefer this over SQL for any KPI question."
        ),
        input_model=MetricsQuery,
        output_model=KpisOutput,
        func=run,
        llm_exposed=True,
    )
