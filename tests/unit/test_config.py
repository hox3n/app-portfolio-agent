"""Tests for settings: defaults, environment overrides, validation."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from portfolio_agent.config import Settings


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    for var in ("AGENT_OLLAMA_MODEL", "AGENT_MAX_TOOL_STEPS", "AGENT_OLLAMA_THINK"):
        monkeypatch.delenv(var, raising=False)


def test_defaults() -> None:
    s = Settings()
    assert s.ollama_model == "qwen3.5:4b"
    assert s.ollama_think is False
    assert s.max_tool_steps == 6


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_OLLAMA_MODEL", "gemma4:12b")
    monkeypatch.setenv("AGENT_MAX_TOOL_STEPS", "3")
    s = Settings()
    assert s.ollama_model == "gemma4:12b"
    assert s.max_tool_steps == 3


def test_dotenv_file_is_read(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("AGENT_OLLAMA_THINK=true\n")
    assert Settings().ollama_think is True


def test_invalid_value_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_MAX_TOOL_STEPS", "0")
    with pytest.raises(ValidationError):
        Settings()


def test_secrets_are_masked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGSMITH_API_KEY", "lsv2-secret")
    s = Settings()
    assert s.langsmith_api_key is not None
    assert "lsv2-secret" not in repr(s)
    assert s.langsmith_api_key.get_secret_value() == "lsv2-secret"


def env_names() -> set[str]:
    names = set()
    for name, field in Settings.model_fields.items():
        alias = field.validation_alias
        names.add(alias if isinstance(alias, str) else f"AGENT_{name.upper()}")
    return names


def test_env_example_documents_every_setting() -> None:
    example = Path(__file__).resolve().parents[2] / ".env.example"
    keys = {
        line.split("=", 1)[0]
        for line in example.read_text().splitlines()
        if line and not line.startswith("#")
    }
    assert keys == env_names()


def test_env_example_values_are_valid(tmp_path: Path) -> None:
    example = Path(__file__).resolve().parents[2] / ".env.example"
    (tmp_path / ".env").write_text(example.read_text())
    assert Settings().anomaly_metrics == ["installs", "ua_cost", "revenue", "roas", "cpi"]
