"""Settings loaded from environment variables and an optional .env file."""

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from portfolio_agent.domain.models import KpiMetric


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    db_path: Path = Path("data/portfolio.duckdb")
    export_dir: Path = Path("exports")

    seed: int = 42
    seed_start: date = date(2024, 1, 1)
    seed_end: date = date(2025, 1, 31)

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:4b"
    ollama_think: bool = False
    llm_temperature: float = Field(default=0.0, ge=0, le=2)
    llm_timeout_s: float = Field(default=60.0, gt=0)
    llm_max_retries: int = Field(default=2, ge=0, le=5)

    max_input_chars: int = Field(default=2000, ge=1)
    max_sql_chars: int = Field(default=2000, ge=50, le=20_000)
    sql_row_limit: int = Field(default=100, ge=1, le=10_000)
    max_tool_steps: int = Field(default=6, ge=1, le=20)
    max_tool_calls_per_step: int = Field(default=3, ge=1, le=10)
    max_tool_result_chars: int = Field(default=6000, ge=500)

    budget_cut_roas_below: float = Field(default=0.8, gt=0)
    budget_scale_roas_at_least: float = Field(default=1.5, gt=0)
    budget_scale_min_spend: float = Field(default=1000.0, ge=0)
    anomaly_min_change_pct: float = Field(default=30.0, gt=0)
    anomaly_min_spend: float = Field(default=500.0, ge=0)
    anomaly_default_days: int = Field(default=7, ge=1, le=90)
    anomaly_metrics: list[KpiMetric] = Field(
        default=["installs", "ua_cost", "revenue", "roas", "cpi"], min_length=1
    )

    llm_summaries: bool = True
    max_summary_chars: int = Field(default=1500, ge=200)
    summary_top_n: int = Field(default=5, ge=1, le=50)
    summary_max_anomalies: int = Field(default=10, ge=1, le=100)

    session_max_turns: int = Field(default=10, ge=1, le=100)
    session_history_turns: int = Field(default=3, ge=0, le=20)
    session_max_sessions: int = Field(default=1000, ge=1)

    display_max_rows: int = Field(default=10, ge=1, le=500)

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "text"] = "json"
    log_max_value_chars: int = Field(default=500, ge=50)
    langsmith_api_key: SecretStr | None = Field(default=None, validation_alias="LANGSMITH_API_KEY")
    langsmith_project: str = Field(
        default="app-portfolio-agent", validation_alias="LANGSMITH_PROJECT"
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
