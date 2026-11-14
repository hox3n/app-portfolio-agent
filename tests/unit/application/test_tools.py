"""Tests for the seven agent tools on the seeded test database."""

from datetime import date
from pathlib import Path
from typing import Any, TypeVar

import pytest

from portfolio_agent.application.tools.catalog import build_tool_registry
from portfolio_agent.application.tools.contracts import (
    AnomaliesOutput,
    DecisionsOutput,
    ExportResult,
    KpisOutput,
    MetricsOutput,
    RunSqlOutput,
    SchemaOutput,
)
from portfolio_agent.application.tools.registry import ToolRegistry
from portfolio_agent.domain.anomalies import AnomalyConfig
from portfolio_agent.domain.budget_rules import BudgetRuleConfig
from portfolio_agent.infrastructure.db.duckdb_repository import DuckDBMetricsRepository
from portfolio_agent.infrastructure.storage.csv_exporter import CsvExporter

OutputT = TypeVar("OutputT")

JANUARY = {"start": "2025-01-01", "end": "2025-01-31"}


def call_typed(registry: ToolRegistry, name: str, args: Any, output_type: type[OutputT]) -> OutputT:
    result = registry.call(name, args)
    assert result.error is None, result.error
    assert isinstance(result.output, output_type)
    return result.output


@pytest.fixture
def registry(repository: DuckDBMetricsRepository, tmp_path: Path) -> ToolRegistry:
    return build_tool_registry(
        repository,
        CsvExporter(tmp_path),
        budget_config=BudgetRuleConfig(),
        anomaly_config=AnomalyConfig(),
        sql_row_limit=20,
    )


def error_code(registry: ToolRegistry, tool: str, args: dict[str, object]) -> str:
    result = registry.call(tool, args)
    assert result.error is not None
    return result.error.code


def test_llm_sees_only_query_tools(registry: ToolRegistry) -> None:
    names = {spec["function"]["name"] for spec in registry.llm_tool_specs()}
    assert names == {"get_schema", "run_sql", "fetch_metrics", "compute_kpis"}


def test_get_schema(registry: ToolRegistry) -> None:
    out = call_typed(registry, "get_schema", {}, SchemaOutput)
    assert out.dataset.date_max == date(2025, 1, 31)
    assert out.kpi_definitions["roas"].startswith("revenue / ua_cost")
    assert "revenue per install" in out.kpi_definitions["arpi"]


def test_run_sql_applies_limit_and_reports_truncation(registry: ToolRegistry) -> None:
    out = call_typed(registry, "run_sql", {"sql": "SELECT * FROM app_metrics"}, RunSqlOutput)
    assert out.row_count == 20
    assert out.truncated is True


def test_run_sql_rejects_unsafe_sql(registry: ToolRegistry) -> None:
    assert error_code(registry, "run_sql", {"sql": "DROP TABLE app_metrics"}) == "not_select"


def test_run_sql_reports_database_errors(registry: ToolRegistry) -> None:
    result = registry.call("run_sql", {"sql": "SELECT nope FROM app_metrics"})
    assert result.error is not None
    assert result.error.code == "query_failed"
    assert "nope" in result.error.message


def test_fetch_metrics_with_filter(registry: ToolRegistry) -> None:
    out = call_typed(registry, "fetch_metrics", {**JANUARY, "apps": ["News"]}, MetricsOutput)
    assert len(out.rows) == 10
    assert {r.app_name for r in out.rows} == {"News"}


def test_single_filter_value_accepted_as_list(registry: ToolRegistry) -> None:
    args = {**JANUARY, "apps": "Puzzle", "platforms": "Android", "countries": "India"}
    out = call_typed(registry, "compute_kpis", args, KpisOutput)
    assert [k.pair for k in out.kpis] == [("Puzzle", "Android", "India")]


def test_unknown_app_lists_allowed_values(registry: ToolRegistry) -> None:
    result = registry.call("compute_kpis", {**JANUARY, "apps": ["Chess"]})
    assert result.error is not None
    assert result.error.code == "unknown_value"
    assert "Puzzle" in result.error.details["allowed"]


def test_period_outside_data_rejected(registry: ToolRegistry) -> None:
    args = {"start": "2023-01-01", "end": "2023-01-31"}
    assert error_code(registry, "compute_kpis", args) == "period_out_of_range"


def test_wrong_platform_case_rejected_with_hint(registry: ToolRegistry) -> None:
    result = registry.call("compute_kpis", {**JANUARY, "platforms": ["ios"]})
    assert result.error is not None
    assert result.error.code == "invalid_input"
    assert "iOS" in str(result.error.details)


def test_end_before_start_rejected(registry: ToolRegistry) -> None:
    args = {"start": "2025-01-31", "end": "2025-01-01"}
    assert error_code(registry, "compute_kpis", args) == "invalid_input"


def test_compute_kpis(registry: ToolRegistry) -> None:
    out = call_typed(registry, "compute_kpis", JANUARY, KpisOutput)
    assert len(out.kpis) == 50
    by_pair = {k.pair: k for k in out.kpis}
    assert (by_pair[("Puzzle", "Android", "India")].roas or 0) < 0.8


def test_budget_rules_flag_planted_pairs(registry: ToolRegistry) -> None:
    kpis = call_typed(registry, "compute_kpis", JANUARY, KpisOutput).kpis
    out = call_typed(registry, "apply_budget_rules", {"kpis": kpis}, DecisionsOutput)
    actions = {(d.app_name, d.platform, d.country): d.action for d in out.decisions}
    assert actions[("Puzzle", "Android", "India")] == "cut"
    assert actions[("Countdown", "Android", "USA")] == "cut"
    assert actions[("Fitness", "iOS", "USA")] == "scale"
    assert sum(out.counts.values()) == 50


def test_anomalies_find_planted_events(registry: ToolRegistry) -> None:
    previous = call_typed(
        registry, "compute_kpis", {"start": "2025-01-06", "end": "2025-01-12"}, KpisOutput
    ).kpis
    current = call_typed(
        registry, "compute_kpis", {"start": "2025-01-25", "end": "2025-01-31"}, KpisOutput
    ).kpis
    out = call_typed(
        registry, "detect_anomalies", {"previous": previous, "current": current}, AnomaliesOutput
    )
    found = {(a.app_name, a.platform, a.country, a.metric) for a in out.anomalies}
    assert ("News", "iOS", "UK", "cpi") in found
    assert ("Paint", "Android", "Germany", "revenue") in found
    assert ("Countdown", "iOS", "France", "installs") in found


def test_anomalies_need_both_periods(registry: ToolRegistry) -> None:
    kpis = call_typed(registry, "compute_kpis", JANUARY, KpisOutput).kpis
    assert error_code(registry, "detect_anomalies", {"previous": [], "current": kpis}) == (
        "invalid_input"
    )


def test_export_csv_escapes_formulas(registry: ToolRegistry, tmp_path: Path) -> None:
    args = {"columns": ["a", "b"], "rows": [{"a": 1, "b": "=HYPERLINK()"}], "filename": "t1"}
    out = call_typed(registry, "export_csv", args, ExportResult)
    path = Path(out.path)
    assert path.parent == tmp_path.resolve()
    assert path.read_text().splitlines() == ["a,b", "1,'=HYPERLINK()"]


def test_export_rejects_path_traversal(registry: ToolRegistry) -> None:
    args = {"columns": ["a"], "rows": [], "filename": "../../etc/passwd"}
    assert error_code(registry, "export_csv", args) == "invalid_input"


def test_compute_kpis_grouped_by_country(registry: ToolRegistry) -> None:
    args = {"start": "2024-01-01", "end": "2024-12-31", "countries": ["France", "Germany"]}
    grouped = call_typed(registry, "compute_kpis", {**args, "group_by": "country"}, KpisOutput)
    per_pair = call_typed(registry, "compute_kpis", args, KpisOutput)

    assert grouped.kpis == []
    assert grouped.groups is not None
    assert [g.group for g in grouped.groups] == [{"country": "France"}, {"country": "Germany"}]
    france = [k for k in per_pair.kpis if k.country == "France"]
    assert grouped.groups[0].rows == len(france) == 10
    assert grouped.groups[0].ua_cost == pytest.approx(sum(k.ua_cost for k in france), abs=0.05)
    assert grouped.totals == per_pair.totals


def test_group_by_rejects_unknown_dimension(registry: ToolRegistry) -> None:
    assert error_code(registry, "compute_kpis", {**JANUARY, "group_by": ["month"]}) == (
        "invalid_input"
    )


def test_group_by_spec_is_visible_to_the_llm(registry: ToolRegistry) -> None:
    [spec] = [s for s in registry.llm_tool_specs() if s["function"]["name"] == "compute_kpis"]
    assert "group_by" in spec["function"]["parameters"]["properties"]
