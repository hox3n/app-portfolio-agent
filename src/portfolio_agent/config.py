"""Settings loaded from environment variables and an optional .env file."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_path: Path = Path("data/portfolio.duckdb")
    export_dir: Path = Path("exports")

    llm_provider: Literal["ollama", "fake"] = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:4b"

    ollama_think: bool = False
    llm_timeout_s: float = Field(default=60.0, gt=0)
    llm_max_retries: int = Field(default=2, ge=0, le=5)

    max_input_chars: int = Field(default=2000, ge=1)
    max_tool_steps: int = Field(default=6, ge=1, le=20)
    sql_row_limit: int = Field(default=100, ge=1, le=10_000)

    budget_cut_roas_below: float = 0.8
    budget_scale_roas_at_least: float = 1.5
    budget_scale_min_spend: float = 1000.0
    anomaly_min_change_pct: float = 30.0
    anomaly_min_spend: float = 500.0

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "text"] = "json"
    langsmith_api_key: SecretStr | None = Field(default=None, validation_alias="LANGSMITH_API_KEY")
    langsmith_project: str = Field(
        default="app-portfolio-agent", validation_alias="LANGSMITH_PROJECT"
    )

    slack_bot_token: SecretStr | None = Field(default=None, validation_alias="SLACK_BOT_TOKEN")
    slack_app_token: SecretStr | None = Field(default=None, validation_alias="SLACK_APP_TOKEN")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
