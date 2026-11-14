"""LLM summary from structured facts; kept only if every number in it matches the data."""

import json
from collections.abc import Callable

from portfolio_agent.application.agent.deps import AgentDeps
from portfolio_agent.application.agent.state import AgentState, NodeUpdate
from portfolio_agent.application.guardrails.output_validator import unsupported_numbers
from portfolio_agent.application.ports import ChatMessage, LLMError
from portfolio_agent.application.prompts import render


def make_summarize_node(deps: AgentDeps) -> Callable[[AgentState], NodeUpdate]:
    def summarize(state: AgentState) -> NodeUpdate:
        facts = state.get("facts")
        if not deps.llm_summaries or not facts:
            return {}
        messages = [
            ChatMessage(role="system", content=render("summarize")),
            ChatMessage(
                role="user",
                content=f"Workflow: {state.get('workflow')}\nFacts (JSON):\n"
                + json.dumps(facts, default=str),
            ),
        ]
        try:
            text = deps.llm.chat(messages).content.strip()
        except LLMError as e:
            return {"warnings": [f"summary_fallback: {e}"]}
        if not text:
            return {"warnings": ["summary_fallback: empty LLM summary"]}
        unsupported = unsupported_numbers(text, facts)
        if unsupported:
            return {"warnings": [f"summary_fallback: unsupported numbers {unsupported[:5]}"]}
        return {"summary": text[: deps.max_summary_chars]}

    return summarize
