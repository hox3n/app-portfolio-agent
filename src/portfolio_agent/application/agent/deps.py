"""Dependencies and limits injected into every graph node."""

from collections.abc import Callable
from dataclasses import dataclass

from portfolio_agent.application.ports import LLMClient
from portfolio_agent.application.tools.registry import ToolRegistry
from portfolio_agent.domain.models import DatasetInfo


@dataclass(frozen=True)
class AgentDeps:
    llm: LLMClient
    tools: ToolRegistry
    dataset: Callable[[], DatasetInfo]
    max_input_chars: int = 2000
    max_tool_steps: int = 6
    max_retries: int = 2
    anomaly_days: int = 7
    llm_summaries: bool = True
    max_tool_calls_per_step: int = 3
    max_tool_result_chars: int = 6000
    max_summary_chars: int = 1500
    summary_top_n: int = 5
    summary_max_anomalies: int = 10
    history_turns: int = 3
