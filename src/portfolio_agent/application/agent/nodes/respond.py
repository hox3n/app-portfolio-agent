"""respond node: fills defaults so every run ends with a status and a summary."""

from portfolio_agent.application.agent.state import AgentState, NodeUpdate


def respond(state: AgentState) -> NodeUpdate:
    update: NodeUpdate = {}
    if not state.get("status"):
        update["status"] = "ok"
    if not state.get("summary"):
        update["summary"] = "No answer was produced."
    return update
