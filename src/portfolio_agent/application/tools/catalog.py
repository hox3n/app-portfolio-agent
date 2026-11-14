"""Builds the tool registry from the application's ports and rule settings."""

from functools import lru_cache

from portfolio_agent.application.ports import Exporter, MetricsRepository
from portfolio_agent.application.tools.anomaly_tool import make_detect_anomalies_tool
from portfolio_agent.application.tools.export_tool import make_export_csv_tool
from portfolio_agent.application.tools.kpi_tool import make_compute_kpis_tool
from portfolio_agent.application.tools.metrics_tool import make_fetch_metrics_tool
from portfolio_agent.application.tools.registry import ToolRegistry
from portfolio_agent.application.tools.rules_tool import make_apply_budget_rules_tool
from portfolio_agent.application.tools.schema_tool import make_get_schema_tool
from portfolio_agent.application.tools.sql_tool import make_run_sql_tool
from portfolio_agent.domain.anomalies import AnomalyConfig
from portfolio_agent.domain.budget_rules import BudgetRuleConfig


def build_tool_registry(
    repository: MetricsRepository,
    exporter: Exporter,
    *,
    budget_config: BudgetRuleConfig,
    anomaly_config: AnomalyConfig,
    sql_row_limit: int,
    max_sql_chars: int = 2000,
) -> ToolRegistry:

    dataset = lru_cache(maxsize=1)(repository.describe)
    return ToolRegistry(
        [
            make_get_schema_tool(dataset),
            make_run_sql_tool(repository, sql_row_limit, max_sql_chars),
            make_fetch_metrics_tool(repository, dataset),
            make_compute_kpis_tool(repository, dataset),
            make_apply_budget_rules_tool(budget_config),
            make_detect_anomalies_tool(anomaly_config),
            make_export_csv_tool(exporter),
        ]
    )
