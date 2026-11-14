"""W1: function-calling loop: tool_agent asks the LLM, run_tools executes, qa_finish checks."""

from collections.abc import Callable
from typing import Any

from portfolio_agent.application.agent.deps import AgentDeps
from portfolio_agent.application.agent.state import AgentState, NodeUpdate
from portfolio_agent.application.agent.templates import table_fallback_summary
from portfolio_agent.application.agent.tooling import record, table_from
from portfolio_agent.application.guardrails.output_validator import unsupported_numbers
from portfolio_agent.application.ports import ChatMessage, LLMError
from portfolio_agent.application.prompts import render, user_block
from portfolio_agent.application.schemas import Plan


def _hints(plan: Plan | None) -> str:
    if plan is None:
        return ""
    parts = []
    if plan.start and plan.end:
        parts.append(f"period {plan.start} to {plan.end}")
    for field in ("apps", "platforms", "countries"):
        if values := getattr(plan, field):
            parts.append(f"{field} {values}")
    return f"\nPlanner hints: {'; '.join(parts)}." if parts else ""


def _initial_messages(deps: AgentDeps, state: AgentState) -> list[ChatMessage]:
    info = deps.dataset()
    system = render(
        "tool_agent",
        apps=", ".join(info.apps),
        platforms=", ".join(info.platforms),
        countries=", ".join(info.countries),
        date_min=info.date_min,
        date_max=info.date_max,
    )
    question = user_block(state["request"]) + _hints(state.get("plan"))
    return [
        ChatMessage(role="system", content=system),
        ChatMessage(role="user", content=question),
    ]


def make_tool_agent_node(deps: AgentDeps) -> Callable[[AgentState], NodeUpdate]:
    def tool_agent(state: AgentState) -> NodeUpdate:
        messages = state.get("agent_messages") or _initial_messages(deps, state)
        if state.get("tool_steps", 0) >= deps.max_tool_steps:
            return {
                "status": "error",
                "summary": f"I couldn't answer within {deps.max_tool_steps} tool calls. "
                "Try a more specific question (period, app, platform or country).",
                "warnings": ["tool_step_limit_reached"],
            }
        try:
            response = deps.llm.chat(messages, tools=deps.tools.llm_tool_specs())
        except LLMError as e:
            return {
                "status": "error",
                "summary": "The language model is unavailable. Please try again.",
                "warnings": [str(e)],
            }
        reply = ChatMessage(
            role="assistant", content=response.content, tool_calls=response.tool_calls
        )
        update: NodeUpdate = {"agent_messages": [*messages, reply]}
        if not response.tool_calls:
            update["answer"] = response.content
        return update

    return tool_agent


def make_run_tools_node(deps: AgentDeps) -> Callable[[AgentState], NodeUpdate]:
    def run_tools(state: AgentState) -> NodeUpdate:
        messages = list(state["agent_messages"])
        calls = messages[-1].tool_calls[: deps.max_tool_calls_per_step]
        facts: dict[str, Any] = dict(state.get("facts") or {})
        results: list[Any] = list(facts.get("tool_results", []))
        table = state.get("table")
        records = []
        for call in calls:
            result = deps.tools.call(call.name, call.arguments, llm_only=True)
            records.append(record(result))
            messages.append(
                ChatMessage(
                    role="tool",
                    tool_name=call.name,
                    content=result.to_llm_content()[: deps.max_tool_result_chars],
                )
            )
            if result.ok and result.output is not None:
                results.append(result.output.model_dump(mode="json"))
                table = table_from(result.output, call.name) or table
        facts["tool_results"] = results
        return {
            "agent_messages": messages,
            "tool_steps": state.get("tool_steps", 0) + len(calls),
            "tool_calls": records,
            "facts": facts,
            "table": table,
        }

    return run_tools


def qa_finish(state: AgentState) -> NodeUpdate:
    answer = state.get("answer", "").strip()
    facts = state.get("facts") or {}
    table = state.get("table")
    tools_used = sorted({c.tool for c in state.get("tool_calls", []) if c.ok})
    unsupported = unsupported_numbers(answer, facts)
    if answer and not unsupported:
        return {"summary": answer, "data": {"tools_used": tools_used}}

    warning = (
        f"answer_rejected: unsupported numbers {unsupported[:5]}"
        if unsupported
        else "answer_rejected: empty answer"
    )
    if table is not None:
        return {
            "summary": table_fallback_summary(table),
            "data": {"tools_used": tools_used},
            "warnings": [warning],
        }
    return {
        "status": "error",
        "summary": "I couldn't produce an answer I could verify against the data. "
        "Try rephrasing with a period, app, platform or country.",
        "warnings": [warning],
    }


def route_after_tool_agent(state: AgentState) -> str:
    if state.get("status"):
        return "respond"
    if "answer" in state:
        return "qa_finish"
    return "run_tools"
