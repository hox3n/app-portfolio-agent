"""Graph wiring: guard → planner → plan_check → workflow branch → summarize → respond."""

from typing import Any

from langgraph.graph import END, START, StateGraph

from portfolio_agent.application.agent.deps import AgentDeps
from portfolio_agent.application.agent.nodes.anomaly_check import make_anomaly_check_node
from portfolio_agent.application.agent.nodes.budget_review import make_budget_review_node
from portfolio_agent.application.agent.nodes.export import make_export_node
from portfolio_agent.application.agent.nodes.guard import make_guard_node
from portfolio_agent.application.agent.nodes.planner import (
    make_plan_check_node,
    make_planner_node,
    route_after_plan_check,
)
from portfolio_agent.application.agent.nodes.respond import respond
from portfolio_agent.application.agent.nodes.summarize import make_summarize_node
from portfolio_agent.application.agent.nodes.tool_agent import (
    make_run_tools_node,
    make_tool_agent_node,
    qa_finish,
    route_after_tool_agent,
)
from portfolio_agent.application.agent.state import AgentState


def _node(fn: Any) -> Any:
    return fn


def _stop_or(next_node: str) -> Any:
    def route(state: AgentState) -> str:
        return "respond" if state.get("status") else next_node

    return route


def build_graph(deps: AgentDeps) -> Any:
    graph = StateGraph(AgentState)
    graph.add_node("guard", _node(make_guard_node(deps)))
    graph.add_node("planner", _node(make_planner_node(deps)))
    graph.add_node("plan_check", _node(make_plan_check_node(deps)))
    graph.add_node("tool_agent", _node(make_tool_agent_node(deps)))
    graph.add_node("run_tools", _node(make_run_tools_node(deps)))
    graph.add_node("qa_finish", _node(qa_finish))
    graph.add_node("budget_review", _node(make_budget_review_node(deps)))
    graph.add_node("anomaly_check", _node(make_anomaly_check_node(deps)))
    graph.add_node("summarize", _node(make_summarize_node(deps)))
    graph.add_node("export", _node(make_export_node(deps)))
    graph.add_node("respond", _node(respond))

    graph.add_edge(START, "guard")
    graph.add_conditional_edges("guard", _stop_or("planner"), ["planner", "respond"])
    graph.add_edge("planner", "plan_check")
    graph.add_conditional_edges(
        "plan_check",
        route_after_plan_check,
        ["planner", "tool_agent", "budget_review", "anomaly_check", "export", "respond"],
    )
    graph.add_conditional_edges(
        "tool_agent", route_after_tool_agent, ["run_tools", "qa_finish", "respond"]
    )
    graph.add_edge("run_tools", "tool_agent")
    graph.add_edge("qa_finish", "respond")
    for workflow in ("budget_review", "anomaly_check"):
        graph.add_conditional_edges(workflow, _stop_or("summarize"), ["summarize", "respond"])
    graph.add_edge("summarize", "respond")
    graph.add_edge("export", "respond")
    graph.add_edge("respond", END)
    return graph.compile()
