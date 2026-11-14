"""input_guard node: deterministic checks before any LLM call."""

from collections.abc import Callable

from portfolio_agent.application.agent.deps import AgentDeps
from portfolio_agent.application.agent.state import AgentState, NodeUpdate
from portfolio_agent.application.guardrails.input_guard import check_input


def make_guard_node(deps: AgentDeps) -> Callable[[AgentState], NodeUpdate]:
    def guard(state: AgentState) -> NodeUpdate:
        result = check_input(state["request"], deps.max_input_chars)
        if not result.ok:
            return {
                "status": "refused",
                "summary": result.message,
                "warnings": [f"input_guard: {result.code}"],
            }
        return {"request": result.text}

    return guard
