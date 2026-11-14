"""detect_anomalies tool: significant KPI changes between two periods."""

from portfolio_agent.application.tools.contracts import AnomaliesOutput, AnomalyInput
from portfolio_agent.application.tools.registry import Tool
from portfolio_agent.domain.anomalies import AnomalyConfig, detect_anomalies


def make_detect_anomalies_tool(config: AnomalyConfig) -> Tool[AnomalyInput, AnomaliesOutput]:

    def run(inp: AnomalyInput) -> AnomaliesOutput:
        return AnomaliesOutput(anomalies=detect_anomalies(inp.previous, inp.current, config))

    return Tool(
        name="detect_anomalies",
        description="Flag KPI changes between two equal length periods that exceed the threshold.",
        input_model=AnomalyInput,
        output_model=AnomaliesOutput,
        func=run,
    )
