"""Tests for the scale / maintain / cut rules."""

import pytest
from pydantic import ValidationError

from portfolio_agent.domain.budget_rules import BudgetRuleConfig, apply_budget_rules, decide
from portfolio_agent.domain.models import KpiRow

CONFIG = BudgetRuleConfig()


def kpi(roas: float | None, cost: float = 5000.0, app: str = "Puzzle") -> KpiRow:
    revenue = 0.0 if roas is None else round(cost * roas, 2)
    return KpiRow(
        app_name=app,
        platform="Android",
        country="India",
        installs=1000,
        ua_cost=cost,
        revenue=revenue,
        profit=round(revenue - cost, 2),
        roas=roas,
        cpi=None,
        arpi=None,
    )


@pytest.mark.parametrize(
    ("roas", "cost", "action", "rule"),
    [
        (0.55, 5000.0, "cut", "roas_below_cut_threshold"),
        (0.8, 5000.0, "maintain", "roas_within_target_range"),
        (1.2, 5000.0, "maintain", "roas_within_target_range"),
        (1.5, 5000.0, "scale", "roas_above_scale_threshold"),
        (2.1, 500.0, "maintain", "spend_too_low_to_scale"),
        (None, 0.0, "maintain", "no_spend"),
    ],
)
def test_rules(roas: float | None, cost: float, action: str, rule: str) -> None:
    decision = decide(kpi(roas, cost), CONFIG)
    assert (decision.action, decision.rule) == (action, rule)


def test_sorted_cut_first_biggest_impact_first() -> None:
    kpis = [kpi(1.2, app="A"), kpi(2.0, app="B"), kpi(0.7, app="C"), kpi(0.3, app="D")]
    assert [d.app_name for d in apply_budget_rules(kpis, CONFIG)] == ["D", "C", "B", "A"]


def test_thresholds_are_configurable() -> None:
    strict = BudgetRuleConfig(cut_roas_below=1.0)
    assert decide(kpi(0.9), strict).action == "cut"


def test_cut_threshold_must_be_below_scale_threshold() -> None:
    with pytest.raises(ValidationError):
        BudgetRuleConfig(cut_roas_below=1.5, scale_roas_at_least=1.5)
