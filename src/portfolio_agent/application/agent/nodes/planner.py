"""planner node (LLM → Plan) and plan_check node (validation, retry or clarification)."""

from collections.abc import Callable

from portfolio_agent.application.agent.deps import AgentDeps
from portfolio_agent.application.agent.state import AgentState, NodeUpdate
from portfolio_agent.application.llm import ask_structured
from portfolio_agent.application.planning import PlanError, normalize_plan
from portfolio_agent.application.ports import ChatMessage, LLMError
from portfolio_agent.application.prompts import neutralize, render, user_block
from portfolio_agent.application.schemas import Plan, Session

REFUSAL = (
    "I can only help with questions about the app portfolio metrics (installs, revenue, "
    "UA cost and KPIs such as ROAS and CPI), and I have read-only access to the data."
)
DEFAULT_CLARIFICATION = "Could you say which period, app, platform or country you mean?"
LLM_UNAVAILABLE = "The language model is unavailable or gave an unusable answer. Please try again."


def history_block(session: Session, turns: int = 3) -> str:
    if not session.turns or turns <= 0:
        return ""
    lines = [
        f"- user: {neutralize(t.request[:200])} | workflow: {t.workflow or t.status} "
        f"| answer: {neutralize(t.summary[:200])}"
        for t in session.turns[-turns:]
    ]
    return "<previous_turns>\n" + "\n".join(lines) + "\n</previous_turns>\n"


def make_planner_node(deps: AgentDeps) -> Callable[[AgentState], NodeUpdate]:
    def planner(state: AgentState) -> NodeUpdate:
        info = deps.dataset()
        system = render(
            "planner",
            apps=", ".join(info.apps),
            platforms=", ".join(info.platforms),
            countries=", ".join(info.countries),
            date_min=info.date_min,
            date_max=info.date_max,
        )
        messages = [
            ChatMessage(role="system", content=system),
            ChatMessage(
                role="user",
                content=history_block(state["session"], deps.history_turns)
                + user_block(state["request"]),
            ),
        ]
        if feedback := state.get("plan_feedback"):
            messages.append(
                ChatMessage(
                    role="user",
                    content=f"Your previous plan was rejected: {feedback}. "
                    "Return a corrected plan.",
                )
            )
        try:
            plan = ask_structured(deps.llm, messages, Plan, max_retries=deps.max_retries)
        except LLMError as e:
            return {"status": "error", "summary": LLM_UNAVAILABLE, "warnings": [str(e)]}
        return {"plan": plan, "plan_attempts": state.get("plan_attempts", 0) + 1}

    return planner


def make_plan_check_node(deps: AgentDeps) -> Callable[[AgentState], NodeUpdate]:
    def plan_check(state: AgentState) -> NodeUpdate:
        plan = state.get("plan")
        if state.get("status") or plan is None:
            return {}
        if plan.workflow == "refuse":
            return {"status": "refused", "summary": REFUSAL}
        if plan.workflow == "clarify":
            question = neutralize(plan.reason.strip()[:300]) or DEFAULT_CLARIFICATION
            return {"status": "needs_clarification", "summary": question}
        try:
            normalized = normalize_plan(plan, deps.dataset(), deps.anomaly_days)
        except PlanError as e:
            if e.retryable and state.get("plan_attempts", 1) <= deps.max_retries:
                return {"plan_feedback": str(e), "warnings": [f"plan_rejected: {e}"]}
            return {
                "status": "needs_clarification",
                "summary": f"I couldn't run that: {e}.",
                "warnings": [f"plan_rejected: {e}"],
            }
        return {"plan": normalized, "workflow": normalized.workflow, "plan_feedback": None}

    return plan_check


def route_after_plan_check(state: AgentState) -> str:
    if state.get("status"):
        return "respond"
    if state.get("plan_feedback"):
        return "planner"
    workflow = state.get("workflow")
    return {
        "qa": "tool_agent",
        "budget_review": "budget_review",
        "anomaly_check": "anomaly_check",
        "export": "export",
    }.get(workflow or "", "respond")
