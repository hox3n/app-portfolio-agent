"""AgentService.run(): the single entry point used by every interface."""

import logging
import time
import uuid
from typing import Any

from portfolio_agent.application.agent.state import AgentState
from portfolio_agent.application.observability import log_event, trace
from portfolio_agent.application.ports import SessionStore
from portfolio_agent.application.schemas import AgentResult, Turn

logger = logging.getLogger(__name__)

DEFAULT_RECURSION_LIMIT = 60
CRASH_SUMMARY = "Something went wrong while handling your request. Please try again."


class AgentService:
    def __init__(
        self,
        graph: Any,
        sessions: SessionStore,
        *,
        max_turns: int = 10,
        recursion_limit: int = DEFAULT_RECURSION_LIMIT,
    ) -> None:
        self._graph = graph
        self._sessions = sessions
        self._max_turns = max_turns
        self._recursion_limit = recursion_limit

    def run(self, request: str, session_id: str | None = None) -> AgentResult:
        session_id = session_id or uuid.uuid4().hex[:12]
        started = time.perf_counter()
        with trace() as trace_id:
            session = self._sessions.get(session_id)
            log_event(logger, "request_received", session_id=session_id, chars=len(request))
            try:
                initial: AgentState = {
                    "request": request,
                    "session": session,
                    "tool_calls": [],
                    "warnings": [],
                }
                state = self._graph.invoke(
                    initial,
                    config={
                        "recursion_limit": self._recursion_limit,
                        "run_name": "portfolio-agent",
                        "tags": ["portfolio-agent"],
                        "metadata": {"trace_id": trace_id, "session_id": session_id},
                    },
                )
                result = self._to_result(state, trace_id, session_id)
            except Exception:
                logger.exception("agent_crashed", extra={"fields": {"session_id": session_id}})
                result = AgentResult(
                    trace_id=trace_id, session_id=session_id, status="error", summary=CRASH_SUMMARY
                )

            result.duration_ms = round((time.perf_counter() - started) * 1000, 1)
            turn = Turn(
                request=request[:500],
                workflow=result.workflow,
                status=result.status,
                summary=result.summary[:500],
            )
            table = result.table if result.workflow != "export" else None
            self._sessions.save(session_id, session.with_turn(turn, table, self._max_turns))
            log_event(
                logger,
                "decision_record",
                session_id=session_id,
                workflow=result.workflow,
                status=result.status,
                plan=result.plan.model_dump(mode="json") if result.plan else None,
                tools=[f"{c.tool}:{'ok' if c.ok else c.error_code}" for c in result.tool_calls],
                warnings=result.warnings,
                duration_ms=result.duration_ms,
            )
            return result

    @staticmethod
    def _to_result(state: dict[str, Any], trace_id: str, session_id: str) -> AgentResult:
        workflow = state.get("workflow")
        return AgentResult(
            trace_id=trace_id,
            session_id=session_id,
            workflow=workflow,
            status=state.get("status", "ok"),
            summary=state.get("summary", ""),
            data=state.get("data", {}),
            table=state.get("table") if workflow != "export" else None,
            plan=state.get("plan"),
            tool_calls=state.get("tool_calls", []),
            warnings=state.get("warnings", []),
        )
