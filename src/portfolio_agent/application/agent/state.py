"""Typed agent state shared by all graph nodes."""

import operator
from typing import Annotated, Any, TypedDict

from portfolio_agent.application.ports import ChatMessage
from portfolio_agent.application.schemas import (
    Plan,
    Session,
    Status,
    Table,
    ToolCallRecord,
    Workflow,
)


class AgentState(TypedDict, total=False):
    request: str
    session: Session
    plan: Plan | None
    plan_attempts: int
    plan_feedback: str | None
    workflow: Workflow | None
    status: Status
    summary: str
    facts: dict[str, Any]
    data: dict[str, Any]
    table: Table | None
    agent_messages: list[ChatMessage]
    tool_steps: int
    answer: str
    tool_calls: Annotated[list[ToolCallRecord], operator.add]
    warnings: Annotated[list[str], operator.add]


NodeUpdate = dict[str, Any]
