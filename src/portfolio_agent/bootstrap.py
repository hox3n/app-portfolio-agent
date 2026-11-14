"""Composition root: builds infrastructure adapters and wires them into the application."""

import os
from functools import lru_cache

from portfolio_agent.application.agent.deps import AgentDeps
from portfolio_agent.application.agent.graph import build_graph
from portfolio_agent.application.ports import Exporter, LLMClient, MetricsRepository
from portfolio_agent.application.service import AgentService
from portfolio_agent.application.tools.catalog import build_tool_registry
from portfolio_agent.config import Settings, get_settings
from portfolio_agent.domain.anomalies import AnomalyConfig
from portfolio_agent.domain.budget_rules import BudgetRuleConfig
from portfolio_agent.infrastructure.db.duckdb_repository import DuckDBMetricsRepository
from portfolio_agent.infrastructure.llm.ollama_client import OllamaClient
from portfolio_agent.infrastructure.storage.csv_exporter import CsvExporter
from portfolio_agent.infrastructure.storage.session_store import InMemorySessionStore


def create_service(
    llm: LLMClient, repository: MetricsRepository, exporter: Exporter, settings: Settings
) -> AgentService:
    tools = build_tool_registry(
        repository,
        exporter,
        budget_config=BudgetRuleConfig(
            cut_roas_below=settings.budget_cut_roas_below,
            scale_roas_at_least=settings.budget_scale_roas_at_least,
            scale_min_spend=settings.budget_scale_min_spend,
        ),
        anomaly_config=AnomalyConfig(
            min_change_pct=settings.anomaly_min_change_pct,
            min_spend=settings.anomaly_min_spend,
            metrics=tuple(settings.anomaly_metrics),
        ),
        sql_row_limit=settings.sql_row_limit,
        max_sql_chars=settings.max_sql_chars,
    )
    deps = AgentDeps(
        llm=llm,
        tools=tools,
        dataset=lru_cache(maxsize=1)(repository.describe),
        max_input_chars=settings.max_input_chars,
        max_tool_steps=settings.max_tool_steps,
        max_retries=settings.llm_max_retries,
        anomaly_days=settings.anomaly_default_days,
        llm_summaries=settings.llm_summaries,
        max_tool_calls_per_step=settings.max_tool_calls_per_step,
        max_tool_result_chars=settings.max_tool_result_chars,
        max_summary_chars=settings.max_summary_chars,
        summary_top_n=settings.summary_top_n,
        summary_max_anomalies=settings.summary_max_anomalies,
        history_turns=settings.session_history_turns,
    )
    return AgentService(
        build_graph(deps),
        InMemorySessionStore(settings.session_max_sessions),
        max_turns=settings.session_max_turns,
        recursion_limit=2 * settings.max_tool_steps + 30,
    )


def _enable_langsmith(settings: Settings) -> None:
    if settings.langsmith_api_key is None or not settings.langsmith_api_key.get_secret_value():
        return
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_API_KEY", settings.langsmith_api_key.get_secret_value())
    os.environ.setdefault("LANGSMITH_PROJECT", settings.langsmith_project)


def build_service(settings: Settings | None = None) -> AgentService:
    settings = settings or get_settings()
    _enable_langsmith(settings)
    llm = OllamaClient(
        settings.ollama_model,
        settings.ollama_base_url,
        think=settings.ollama_think,
        temperature=settings.llm_temperature,
        timeout_s=settings.llm_timeout_s,
    )
    return create_service(
        llm,
        DuckDBMetricsRepository(settings.db_path),
        CsvExporter(settings.export_dir),
        settings,
    )
