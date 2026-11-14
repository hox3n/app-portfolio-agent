"""W4: export the previous result table of this session as CSV."""

from collections.abc import Callable

from portfolio_agent.application.agent.deps import AgentDeps
from portfolio_agent.application.agent.state import AgentState, NodeUpdate
from portfolio_agent.application.agent.tooling import call_tool
from portfolio_agent.application.tools.contracts import ExportResult


def make_export_node(deps: AgentDeps) -> Callable[[AgentState], NodeUpdate]:
    def export(state: AgentState) -> NodeUpdate:
        table = state["session"].last_table
        if table is None:
            return {
                "status": "needs_clarification",
                "summary": "There is no previous result to export yet. "
                "Ask a question first, then say 'export that'.",
            }
        step = call_tool(
            deps.tools,
            "export_csv",
            {"columns": table.columns, "rows": table.rows},
            ExportResult,
        )
        if step.output is None:
            message = step.error.message if step.error else "unknown error"
            return {
                "status": "error",
                "summary": f"The export failed: {message}",
                "tool_calls": [step.record],
            }
        return {
            "summary": f"Exported {step.output.row_count} "
            f"row{'' if step.output.row_count == 1 else 's'} from the previous "
            f"{table.source} result to {step.output.path}.",
            "data": step.output.model_dump(),
            "tool_calls": [step.record],
        }

    return export
