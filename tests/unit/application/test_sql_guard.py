"""Tests for the SQL guard."""

import pytest

from portfolio_agent.application.guardrails.sql_guard import SqlGuardError, validate_select
from portfolio_agent.infrastructure.db.duckdb_repository import DuckDBMetricsRepository


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM app_metrics",
        "select app_name, SUM(installs) AS i FROM app_metrics GROUP BY app_name ORDER BY i DESC",
        "WITH jan AS (SELECT * FROM app_metrics WHERE date >= '2025-01-01') "
        "SELECT COUNT(*) FROM jan",
        "SELECT app_name FROM app_metrics WHERE platform = 'iOS' "
        "UNION SELECT app_name FROM app_metrics WHERE platform = 'Android'",
        "SELECT * FROM (SELECT app_name, ua_cost FROM app_metrics) AS t WHERE ua_cost > 100",
        "SELECT DATE_TRUNC('month', date) AS m, ROUND(SUM(ua_cost), 2) FROM app_metrics GROUP BY m",
        "SELECT * FROM app_metrics;",
        "SELECT app_name, SUM(in_app_revenue + ads_revenue) / SUM(installs) AS arpi "
        "FROM app_metrics GROUP BY app_name",
    ],
)
def test_valid_queries_pass(sql: str) -> None:
    assert validate_select(sql, max_rows=100)


@pytest.mark.parametrize(
    ("sql", "code"),
    [
        ("", "empty_sql"),
        ("   ", "empty_sql"),
        ("SELECT * FROM app_metrics WHERE " + "x = 1 AND " * 300 + "1=1", "sql_too_long"),
        ("SELECT * FROM (", "parse_error"),
        ("SELEC * FORM app_metrics", "not_select"),
        ("SELECT 1; DROP TABLE app_metrics", "multiple_statements"),
        ("DELETE FROM app_metrics", "not_select"),
        ("DROP TABLE app_metrics", "not_select"),
        ("INSERT INTO app_metrics VALUES (1)", "not_select"),
        ("UPDATE app_metrics SET installs = 0", "not_select"),
        ("CREATE TABLE t AS SELECT * FROM app_metrics", "not_select"),
        ("COPY app_metrics TO 'leak.csv'", "not_select"),
        ("ATTACH 'other.db'", "not_select"),
        ("SET enable_external_access = true", "not_select"),
        ("PRAGMA database_list", "not_select"),
        ("INSTALL httpfs", "not_select"),
        ("SELECT * FROM users", "table_not_allowed"),
        ("SELECT * FROM main.app_metrics", "table_not_allowed"),
        ("SELECT * FROM information_schema.tables", "table_not_allowed"),
        ("SELECT * FROM app_metrics JOIN secrets ON true", "table_not_allowed"),
        ("SELECT * FROM read_csv('/etc/hosts')", "function_not_allowed"),
        ("SELECT * FROM query('SELECT 1')", "function_not_allowed"),
        ("SELECT getenv('HOME')", "function_not_allowed"),
        ("SELECT app_name, read_text('/etc/hosts') FROM app_metrics", "function_not_allowed"),
        (
            "SELECT app_name, SUM((in_app_revenue + ads_revenue) / installs) FROM app_metrics "
            "GROUP BY app_name",
            "ratio_aggregation",
        ),
        ("SELECT AVG(ua_cost / installs) FROM app_metrics", "ratio_aggregation"),
    ],
)
def test_unsafe_queries_rejected(sql: str, code: str) -> None:
    with pytest.raises(SqlGuardError) as err:
        validate_select(sql, max_rows=100)
    assert err.value.code == code


def test_limit_added_when_missing() -> None:
    assert validate_select("SELECT * FROM app_metrics", max_rows=50).endswith("LIMIT 50")


def test_large_limit_lowered() -> None:
    assert validate_select("SELECT * FROM app_metrics LIMIT 99999", max_rows=50).endswith(
        "LIMIT 50"
    )


def test_small_limit_kept() -> None:
    assert validate_select("SELECT * FROM app_metrics LIMIT 5", max_rows=50).endswith("LIMIT 5")


def test_limit_applies_to_union() -> None:
    sql = validate_select("SELECT 1 FROM app_metrics UNION SELECT 2 FROM app_metrics", 10)
    assert sql.endswith("LIMIT 10")


def test_error_message_lists_allowed_tables() -> None:
    with pytest.raises(SqlGuardError, match="allowed: app_metrics"):
        validate_select("SELECT * FROM revenue", max_rows=10)


def test_guarded_sql_runs_on_real_database(repository: DuckDBMetricsRepository) -> None:
    sql = validate_select(
        "SELECT country, SUM(installs) AS installs FROM app_metrics GROUP BY country", 3
    )
    result = repository.run_select(sql, max_rows=100)
    assert len(result.rows) == 3
    assert result.columns == ["country", "installs"]
