"""W2: fixed sequence compute_kpis → apply_budget_rules, then a deterministic summary."""

from collections.abc import Callable

from portfolio_agent.application.agent.deps import AgentDeps
from portfolio_agent.application.agent.state import AgentState, NodeUpdate
from portfolio_agent.application.agent.templates import budget_facts, budget_summary
from portfolio_agent.application.agent.tooling import call_tool, query_args
from portfolio_agent.application.schemas import Table, ToolCallRecord, ToolError
from portfolio_agent.application.tools.contracts import DecisionsOutput, KpisOutput
from portfolio_agent.domain.models import Decision


def make_budget_review_node(deps: AgentDeps) -> Callable[[AgentState], NodeUpdate]:
    def budget_review(state: AgentState) -> NodeUpdate:
        plan = state["plan"]
        assert plan is not None
        kpis = call_tool(deps.tools, "compute_kpis", query_args(plan), KpisOutput)
        if kpis.output is None:
            return _failed("compute KPIs", kpis.error, [kpis.record])
        if not kpis.output.kpis:
            return {
                "status": "ok",
                "summary": f"No data for {plan.start} to {plan.end} with these filters.",
                "tool_calls": [kpis.record],
            }

        rules = call_tool(
            deps.tools, "apply_budget_rules", {"kpis": kpis.output.kpis}, DecisionsOutput
        )
        if rules.output is None:
            return _failed("apply the budget rules", rules.error, [kpis.record, rules.record])

        decisions = rules.output.decisions
        facts = budget_facts(
            kpis.output.period,
            decisions,
            kpis.output.kpis,
            rules.output.counts,
            deps.summary_top_n,
        )
        return {
            "facts": facts,
            "data": facts,
            "summary": budget_summary(facts),
            "table": Table(
                columns=list(Decision.model_fields),
                rows=[d.model_dump() for d in decisions],
                source="budget_review",
            ),
            "tool_calls": [kpis.record, rules.record],
        }

    return budget_review


def _failed(what: str, error: ToolError | None, records: list[ToolCallRecord]) -> NodeUpdate:
    message = error.message if error else "unknown error"
    return {"status": "error", "summary": f"Could not {what}: {message}", "tool_calls": records}
