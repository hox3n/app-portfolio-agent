"""apply_budget_rules tool: scale / maintain / cut decisions from KPIs."""

from portfolio_agent.application.tools.contracts import BudgetRulesInput, DecisionsOutput
from portfolio_agent.application.tools.registry import Tool
from portfolio_agent.domain.budget_rules import ACTION_ORDER, BudgetRuleConfig, apply_budget_rules
from portfolio_agent.domain.models import Action


def make_apply_budget_rules_tool(
    config: BudgetRuleConfig,
) -> Tool[BudgetRulesInput, DecisionsOutput]:

    def run(inp: BudgetRulesInput) -> DecisionsOutput:

        decisions = apply_budget_rules(inp.kpis, config)
        counts: dict[Action, int] = dict.fromkeys(ACTION_ORDER, 0)

        for decision in decisions:
            counts[decision.action] += 1
        return DecisionsOutput(decisions=decisions, counts=counts)

    return Tool(
        name="apply_budget_rules",
        description="Mark each app/platform/country as scale, maintain or cut from its KPIs.",
        input_model=BudgetRulesInput,
        output_model=DecisionsOutput,
        func=run,
    )
