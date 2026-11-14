"""Tests for period-over-period anomaly detection."""

from portfolio_agent.domain.anomalies import AnomalyConfig, detect_anomalies
from portfolio_agent.domain.kpis import compute_kpis
from portfolio_agent.domain.models import KpiRow, MetricRow

CONFIG = AnomalyConfig()


def kpi(
    installs: int = 1000, cost: float = 2000.0, revenue: float = 2400.0, app: str = "News"
) -> KpiRow:
    return compute_kpis(
        MetricRow(
            app_name=app,
            platform="iOS",
            country="UK",
            installs=installs,
            in_app_revenue=revenue,
            ads_revenue=0.0,
            ua_cost=cost,
        )
    )


def test_cpi_spike_detected() -> None:
    found = {a.metric: a for a in detect_anomalies([kpi()], [kpi(cost=4400.0)], CONFIG)}
    assert found["cpi"].change_pct == 120.0
    assert found["cpi"].direction == "up"
    assert found["roas"].direction == "down"
    assert "installs" not in found


def test_small_changes_ignored() -> None:
    assert detect_anomalies([kpi()], [kpi(cost=2400.0)], CONFIG) == []


def test_low_spend_pairs_ignored() -> None:
    assert detect_anomalies([kpi(cost=100.0)], [kpi(cost=300.0)], CONFIG) == []


def test_pair_missing_in_previous_period_ignored() -> None:
    assert detect_anomalies([kpi(app="Paint")], [kpi(app="News", cost=9000.0)], CONFIG) == []


def test_sorted_biggest_change_first() -> None:
    previous = [kpi(app="A"), kpi(app="B")]
    current = [kpi(app="A", installs=1500), kpi(app="B", installs=3000)]
    found = detect_anomalies(previous, current, AnomalyConfig(metrics=("installs",)))
    assert [(a.app_name, a.change_pct) for a in found] == [("B", 200.0), ("A", 50.0)]
