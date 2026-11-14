"""get_schema tool: table structure, allowed values and KPI formulas."""

from collections.abc import Callable

from portfolio_agent.application.tools.contracts import GetSchemaInput, SchemaOutput
from portfolio_agent.application.tools.registry import Tool
from portfolio_agent.domain.models import DatasetInfo

KPI_DEFINITIONS = {
    "revenue": "in_app_revenue + ads_revenue",
    "profit": "revenue - ua_cost",
    "roas": "revenue / ua_cost",
    "cpi": "ua_cost / installs",
    "arpi": "revenue / installs",
}


def make_get_schema_tool(
    dataset: Callable[[], DatasetInfo],
) -> Tool[GetSchemaInput, SchemaOutput]:

    def run(_: GetSchemaInput) -> SchemaOutput:
        return SchemaOutput(dataset=dataset(), kpi_definitions=KPI_DEFINITIONS)

    return Tool(
        name="get_schema",
        description=(
            "Describe the app_metrics table: columns, allowed app/platform/country values, "
            "available date range and KPI formulas. Call this before writing SQL."
        ),
        input_model=GetSchemaInput,
        output_model=SchemaOutput,
        func=run,
        llm_exposed=True,
    )
