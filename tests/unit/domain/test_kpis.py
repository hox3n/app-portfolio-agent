"""Tests for KPI formulas."""

from datetime import date

import pytest
from pydantic import ValidationError

from portfolio_agent.domain.kpis import compute_all, compute_kpis, group_totals, totals_of
from portfolio_agent.domain.models import MetricRow, Period


def metric(
    installs: int = 1000, in_app: float = 600.0, ads: float = 400.0, cost: float = 800.0
) -> MetricRow:
    return MetricRow(
        app_name="Puzzle",
        platform="iOS",
        country="USA",
        installs=installs,
        in_app_revenue=in_app,
        ads_revenue=ads,
        ua_cost=cost,
    )


def test_kpis_match_hand_calculation() -> None:
    kpi = compute_kpis(metric())
    assert kpi.revenue == 1000.0
    assert kpi.profit == 200.0
    assert kpi.roas == 1.25
    assert kpi.cpi == 0.8
    assert kpi.arpi == 1.0


def test_zero_cost_and_zero_installs_give_none() -> None:
    kpi = compute_kpis(metric(installs=0, cost=0.0))
    assert (kpi.roas, kpi.cpi, kpi.arpi) == (None, None, None)
    assert kpi.profit == 1000.0


def test_ratios_are_rounded() -> None:
    assert compute_kpis(metric(installs=3, in_app=1.0, ads=0.0, cost=3.0)).roas == 0.3333


def test_compute_all_keeps_order() -> None:
    kpis = compute_all([metric(cost=100.0), metric(cost=200.0)])
    assert [k.ua_cost for k in kpis] == [100.0, 200.0]


def test_negative_values_rejected() -> None:
    with pytest.raises(ValidationError):
        metric(cost=-1.0)


def test_totals_over_rows() -> None:
    totals = totals_of([metric(), metric(installs=0, cost=200.0)])
    assert (totals.rows, totals.installs, totals.revenue, totals.ua_cost) == (
        2,
        1000,
        2000.0,
        1000.0,
    )
    assert (totals.profit, totals.roas, totals.cpi) == (1000.0, 2.0, 1.0)


def test_totals_of_nothing() -> None:
    totals = totals_of([])
    assert (totals.rows, totals.roas, totals.cpi) == (0, None, None)


def test_previous_period_has_same_length() -> None:
    week = Period(start=date(2025, 1, 25), end=date(2025, 1, 31))
    assert week.previous() == Period(start=date(2025, 1, 18), end=date(2025, 1, 24))


def grouped_metric(country: str, platform: str, cost: float) -> MetricRow:
    return MetricRow(
        app_name="Puzzle",
        platform=platform,
        country=country,
        installs=100,
        in_app_revenue=cost,
        ads_revenue=0.0,
        ua_cost=cost,
    )


def test_group_totals_by_country() -> None:
    rows = [
        grouped_metric("UK", "iOS", 100.0),
        grouped_metric("France", "iOS", 50.0),
        grouped_metric("UK", "Android", 300.0),
    ]
    groups = group_totals(rows, ["country"])
    assert [g.group for g in groups] == [{"country": "France"}, {"country": "UK"}]
    assert (groups[1].rows, groups[1].installs, groups[1].ua_cost) == (2, 200, 400.0)
    assert groups[1].roas == 1.0


def test_group_totals_by_two_dimensions() -> None:
    rows = [grouped_metric("UK", "iOS", 1.0), grouped_metric("UK", "Android", 1.0)]
    groups = group_totals(rows, ["country", "platform"])
    assert [g.group for g in groups] == [
        {"country": "UK", "platform": "Android"},
        {"country": "UK", "platform": "iOS"},
    ]


def test_group_totals_of_nothing() -> None:
    assert group_totals([], ["app"]) == []
