"""Tests for the deterministic sample data generator."""

from datetime import date

from portfolio_agent.infrastructure.db.duckdb_repository import DuckDBMetricsRepository
from portfolio_agent.infrastructure.db.seed import (
    APPS,
    COUNTRIES,
    PLATFORMS,
    checksum,
    generate_rows,
)

START, END = date(2024, 1, 1), date(2024, 1, 10)


def test_same_seed_gives_identical_rows() -> None:
    assert generate_rows(7, START, END) == generate_rows(7, START, END)


def test_different_seed_gives_different_rows() -> None:
    assert checksum(generate_rows(1, START, END)) != checksum(generate_rows(2, START, END))


def test_every_pair_has_every_day() -> None:
    rows = generate_rows(start=START, end=END)
    assert len(rows) == len(APPS) * len(PLATFORMS) * len(COUNTRIES) * 10
    assert len({r[:4] for r in rows}) == len(rows)


def test_values_are_non_negative() -> None:
    assert all(min(r[4:]) >= 0 for r in generate_rows(start=START, end=END))


def _value(repo: DuckDBMetricsRepository, sql: str) -> float:
    return float(next(iter(repo.run_select(sql, 1).rows[0].values())))


def _roas(repo: DuckDBMetricsRepository, app: str, platform: str, country: str) -> float:
    return _value(
        repo,
        "SELECT SUM(in_app_revenue + ads_revenue) / SUM(ua_cost) FROM app_metrics "
        f"WHERE app_name='{app}' AND platform='{platform}' AND country='{country}'",
    )


def test_planted_loss_and_star_pairs(repository: DuckDBMetricsRepository) -> None:
    assert _roas(repository, "Puzzle", "Android", "India") < 0.7
    assert _roas(repository, "Countdown", "Android", "USA") < 0.8
    assert _roas(repository, "Fitness", "iOS", "USA") > 1.8


def test_planted_cpi_spike(repository: DuckDBMetricsRepository) -> None:
    def cpi(start: str, end: str) -> float:
        return _value(
            repository,
            "SELECT SUM(ua_cost) / SUM(installs) FROM app_metrics "
            "WHERE app_name='News' AND platform='iOS' AND country='UK' "
            f"AND date BETWEEN '{start}' AND '{end}'",
        )

    assert cpi("2025-01-25", "2025-01-31") > 1.8 * cpi("2025-01-06", "2025-01-12")
