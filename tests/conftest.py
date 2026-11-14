"""Shared fixtures: seeded test DB, fake LLM, service instance."""

from pathlib import Path

import pytest

from portfolio_agent.infrastructure.db.duckdb_repository import DuckDBMetricsRepository
from portfolio_agent.infrastructure.db.seed import generate_rows, write_database


@pytest.fixture(scope="session")
def seeded_test_db(tmp_path_factory: pytest.TempPathFactory) -> Path:

    db_path = tmp_path_factory.mktemp("db") / "test.duckdb"
    rows = generate_rows()
    write_database(rows, db_path)
    return db_path


@pytest.fixture
def repository(seeded_test_db: Path) -> DuckDBMetricsRepository:
    return DuckDBMetricsRepository(seeded_test_db)
