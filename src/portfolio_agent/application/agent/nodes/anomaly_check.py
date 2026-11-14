"""W3: fixed sequence compute_kpis (current + previous period) → detect_anomalies."""

from collections.abc import Callable

from portfolio_agent.application.agent.deps import AgentDeps
from portfolio_agent.application.agent.state import AgentState, NodeUpdate
from portfolio_agent.application.agent.templates import anomaly_facts, anomaly_summary
from portfolio_agent.application.agent.tooling import call_tool, query_args
from portfolio_agent.application.schemas import Table
from portfolio_agent.application.tools.contracts import AnomaliesOutput, KpisOutput
from portfolio_agent.domain.models import Anomaly, Period


def make_anomaly_check_node(deps: AgentDeps) -> Callable[[AgentState], NodeUpdate]:
    def anomaly_check(state: AgentState) -> NodeUpdate:
        plan = state["plan"]
        assert plan is not None and plan.start is not None and plan.end is not None
        current = Period(start=plan.start, end=plan.end)
        previous = current.previous()
        args = query_args(plan)

        cur = call_tool(deps.tools, "compute_kpis", args, KpisOutput)
        prev = call_tool(
            deps.tools,
            "compute_kpis",
            {**args, "start": previous.start, "end": previous.end},
            KpisOutput,
        )
        records = [cur.record, prev.record]
        if cur.output is None or prev.output is None:
            error = cur.error or prev.error
            message = error.message if error else "unknown error"
            return {
                "status": "error",
                "summary": f"Could not compute KPIs: {message}",
                "tool_calls": records,
            }
        if not cur.output.kpis or not prev.output.kpis:
            return {
                "status": "ok",
                "summary": "No data to compare for these periods and filters.",
                "tool_calls": records,
            }

        found = call_tool(
            deps.tools,
            "detect_anomalies",
            {"previous": prev.output.kpis, "current": cur.output.kpis},
            AnomaliesOutput,
        )
        records.append(found.record)
        if found.output is None:
            message = found.error.message if found.error else "unknown error"
            return {
                "status": "error",
                "summary": f"Could not detect anomalies: {message}",
                "tool_calls": records,
            }

        anomalies = found.output.anomalies
        facts = anomaly_facts(current, previous, anomalies, deps.summary_max_anomalies)
        return {
            "facts": facts,
            "data": facts,
            "summary": anomaly_summary(facts),
            "table": Table(
                columns=list(Anomaly.model_fields),
                rows=[a.model_dump() for a in anomalies],
                source="anomaly_check",
            ),
            "tool_calls": records,
        }

    return anomaly_check
