"""Shared fixtures: seeded test DB, fake LLM, service instance."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from portfolio_agent.application.ports import LLMResponse
from portfolio_agent.application.service import AgentService
from portfolio_agent.bootstrap import create_service
from portfolio_agent.config import Settings
from portfolio_agent.infrastructure.db.duckdb_repository import DuckDBMetricsRepository
from portfolio_agent.infrastructure.db.seed import generate_rows, write_database
from portfolio_agent.infrastructure.llm.fake_client import FakeLLMClient
from portfolio_agent.infrastructure.storage.csv_exporter import CsvExporter


@pytest.fixture(scope="session")
def seeded_test_db(tmp_path_factory: pytest.TempPathFactory) -> Path:

    db_path = tmp_path_factory.mktemp("db") / "test.duckdb"
    rows = generate_rows()
    write_database(rows, db_path)
    return db_path


@pytest.fixture
def repository(seeded_test_db: Path) -> DuckDBMetricsRepository:
    return DuckDBMetricsRepository(seeded_test_db)


@pytest.fixture
def make_service(
    seeded_test_db: Path, tmp_path: Path
) -> Callable[..., tuple[AgentService, FakeLLMClient]]:
    def factory(
        responses: list[LLMResponse | BaseModel | str], **overrides: Any
    ) -> tuple[AgentService, FakeLLMClient]:
        llm = FakeLLMClient(responses)
        settings = Settings(_env_file=None, export_dir=tmp_path / "exports", **overrides)
        service = create_service(
            llm, DuckDBMetricsRepository(seeded_test_db), CsvExporter(settings.export_dir), settings
        )
        return service, llm

    return factory
