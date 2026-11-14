"""Scale / maintain / cut rules for the UA budget review."""

from collections.abc import Iterable
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from portfolio_agent.domain.models import Action, Decision, KpiRow, Rule

ACTION_ORDER: dict[Action, int] = {"cut": 0, "scale": 1, "maintain": 2}


class BudgetRuleConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    cut_roas_below: float = Field(default=0.8, gt=0)
    scale_roas_at_least: float = Field(default=1.5, gt=0)
    scale_min_spend: float = Field(default=1000.0, ge=0)

    @model_validator(mode="after")
    def _check_order(self) -> Self:
        if self.cut_roas_below >= self.scale_roas_at_least:
            raise ValueError("cut_roas_below must be less than scale_roas_at_least")
        return self


def _classify(kpi: KpiRow, config: BudgetRuleConfig) -> tuple[Action, Rule]:

    if kpi.roas is None:
        return "maintain", "no_spend"
    if kpi.roas < config.cut_roas_below:
        return "cut", "roas_below_cut_threshold"
    if kpi.roas < config.scale_roas_at_least:
        return "maintain", "roas_within_target_range"
    if kpi.ua_cost < config.scale_min_spend:
        return "maintain", "spend_too_low_to_scale"
    return "scale", "roas_above_scale_threshold"


def decide(kpi: KpiRow, config: BudgetRuleConfig) -> Decision:

    action, rule = _classify(kpi, config)
    return Decision(
        app_name=kpi.app_name,
        platform=kpi.platform,
        country=kpi.country,
        action=action,
        rule=rule,
        roas=kpi.roas,
        ua_cost=kpi.ua_cost,
        profit=kpi.profit,
    )


def apply_budget_rules(kpis: Iterable[KpiRow], config: BudgetRuleConfig) -> list[Decision]:

    decisions = [decide(kpi, config) for kpi in kpis]
    return sorted(decisions, key=lambda d: (ACTION_ORDER[d.action], -abs(d.profit)))
