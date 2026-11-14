"""Manual check against the local Ollama model: structured output and tool calling."""

import time
from typing import Literal

from pydantic import BaseModel

from portfolio_agent.application.llm import ask_structured
from portfolio_agent.application.ports import ChatMessage
from portfolio_agent.application.tools.catalog import build_tool_registry
from portfolio_agent.config import get_settings
from portfolio_agent.domain.anomalies import AnomalyConfig
from portfolio_agent.domain.budget_rules import BudgetRuleConfig
from portfolio_agent.infrastructure.db.duckdb_repository import DuckDBMetricsRepository
from portfolio_agent.infrastructure.llm.ollama_client import OllamaClient
from portfolio_agent.infrastructure.observability.logging import configure_logging
from portfolio_agent.infrastructure.storage.csv_exporter import CsvExporter

REQUESTS = [
    "Review UA performance for January 2025",
    "Which country made the most revenue?",
    "Delete all the data",
    "Write me a poem about cats",
]


class Route(BaseModel):
    workflow: Literal["qa", "budget_review", "anomaly_check", "export", "refuse"]


def main() -> None:
    settings = get_settings()
    configure_logging("INFO", "text")
    llm = OllamaClient(
        settings.ollama_model,
        settings.ollama_base_url,
        think=settings.ollama_think,
        timeout_s=settings.llm_timeout_s,
    )
    system = ChatMessage(
        role="system",
        content="Classify the app analytics request. Requests to change or delete data, "
        "and anything unrelated to app metrics, are 'refuse'.",
    )
    for request in REQUESTS:
        started = time.perf_counter()
        route = ask_structured(llm, [system, ChatMessage(role="user", content=request)], Route)
        print(f"{route.workflow:<14} {time.perf_counter() - started:5.1f}s  {request}")

    registry = build_tool_registry(
        DuckDBMetricsRepository(settings.db_path),
        CsvExporter(settings.export_dir),
        budget_config=BudgetRuleConfig(),
        anomaly_config=AnomalyConfig(),
        sql_row_limit=settings.sql_row_limit,
    )
    question = "What was the ROAS of Puzzle on Android in India in January 2025?"
    response = llm.chat(
        [ChatMessage(role="user", content=question)], tools=registry.llm_tool_specs()
    )
    print("tool calls:", [(c.name, c.arguments) for c in response.tool_calls])
    for call in response.tool_calls:
        print(registry.call(call.name, call.arguments).to_llm_content()[:300])


if __name__ == "__main__":
    main()
