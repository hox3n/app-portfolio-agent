"""Tests for the read-only DuckDB repository."""

from datetime import date
from pathlib import Path

import pytest

from portfolio_agent.application.ports import RepositoryError
from portfolio_agent.domain.models import Period
from portfolio_agent.infrastructure.db.duckdb_repository import DuckDBMetricsRepository
from portfolio_agent.infrastructure.db.seed import APPS, COUNTRIES, PLATFORMS

JANUARY = Period(start=date(2025, 1, 1), end=date(2025, 1, 31))
TOTAL_ROWS = 50 * 397


def test_missing_database_raises(tmp_path: Path) -> None:
    with pytest.raises(RepositoryError, match="make seed"):
        DuckDBMetricsRepository(tmp_path / "nope.duckdb")


def test_describe(repository: DuckDBMetricsRepository) -> None:
    info = repository.describe()
    assert info.table == "app_metrics"
    assert info.apps == sorted(APPS)
    assert info.platforms == sorted(PLATFORMS)
    assert info.countries == sorted(COUNTRIES)
    assert (info.date_min, info.date_max) == (date(2024, 1, 1), date(2025, 1, 31))
    assert info.row_count == TOTAL_ROWS
    assert {"installs", "ua_cost", "date"} <= info.columns.keys()


def test_fetch_metrics_returns_one_row_per_pair(repository: DuckDBMetricsRepository) -> None:
    rows = repository.fetch_metrics(JANUARY)
    assert len(rows) == 50
    assert len({(r.app_name, r.platform, r.country) for r in rows}) == 50


def test_fetch_metrics_filters(repository: DuckDBMetricsRepository) -> None:
    rows = repository.fetch_metrics(JANUARY, apps=["News"], platforms=["iOS"], countries=["UK"])
    assert [(r.app_name, r.platform, r.country) for r in rows] == [("News", "iOS", "UK")]


def test_fetch_metrics_matches_raw_sums(repository: DuckDBMetricsRepository) -> None:
    [row] = repository.fetch_metrics(JANUARY, apps=["Paint"], platforms=["iOS"], countries=["USA"])
    raw = repository.run_select(
        "SELECT SUM(installs) AS i, SUM(ua_cost) AS c FROM app_metrics "
        "WHERE app_name='Paint' AND platform='iOS' AND country='USA' "
        "AND date BETWEEN '2025-01-01' AND '2025-01-31'",
        max_rows=1,
    ).rows[0]
    assert row.installs == raw["i"]
    assert row.ua_cost == pytest.approx(raw["c"], abs=0.01)


def test_filter_values_are_parameters_not_sql(repository: DuckDBMetricsRepository) -> None:
    assert repository.fetch_metrics(JANUARY, apps=["x'; DROP TABLE app_metrics;--"]) == []
    assert repository.describe().row_count == TOTAL_ROWS


def test_run_select_truncates(repository: DuckDBMetricsRepository) -> None:
    result = repository.run_select("SELECT * FROM app_metrics", max_rows=5)
    assert len(result.rows) == 5
    assert result.truncated is True
    assert result.columns[0] == "app_name"
    assert isinstance(result.rows[0]["date"], str)


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM app_metrics",
        "DROP TABLE app_metrics",
        "INSERT INTO app_metrics VALUES ('X','iOS','2025-01-01','USA',1,1,1,1)",
        "CREATE TABLE t (x INT)",
        "SET enable_external_access = true",
    ],
)
def test_writes_are_rejected(repository: DuckDBMetricsRepository, sql: str) -> None:
    with pytest.raises(RepositoryError):
        repository.run_select(sql, max_rows=1)
    assert repository.describe().row_count == TOTAL_ROWS


def test_file_access_is_blocked(repository: DuckDBMetricsRepository, tmp_path: Path) -> None:
    target = tmp_path / "leak.csv"
    with pytest.raises(RepositoryError):
        repository.run_select(f"COPY app_metrics TO '{target}'", max_rows=1)
    assert not target.exists()
    with pytest.raises(RepositoryError):
        repository.run_select("SELECT * FROM read_csv('/etc/hosts')", max_rows=1)
