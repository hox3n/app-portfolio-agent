"""Tests for KPI formulas."""

import pytest
from pydantic import ValidationError

from portfolio_agent.domain.kpis import compute_all, compute_kpis
from portfolio_agent.domain.models import MetricRow


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
