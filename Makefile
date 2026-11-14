PYTHON ?= python3
VENV   := .venv
BIN    := $(VENV)/bin

.DEFAULT_GOAL := help
.PHONY: help setup test test-unit test-integration test-cov lint format check seed run chat smoke samples clean

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

$(BIN)/activate:
	$(PYTHON) -m venv $(VENV)

setup: $(BIN)/activate ## Create .venv and install the project with dev tools
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -e ".[dev]"
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example")

test: ## Run unit + integration tests (no Ollama needed)
	$(BIN)/pytest

test-unit: ## Run only the unit tests
	$(BIN)/pytest tests/unit

test-integration: ## Run only the end-to-end graph tests (fake LLM, seeded DB)
	$(BIN)/pytest tests/integration

test-cov: ## Run tests with a coverage report
	$(BIN)/pytest --cov=portfolio_agent --cov-report=term-missing

lint: ## Check style, formatting and types
	$(BIN)/ruff check src tests
	$(BIN)/ruff format --check src tests
	$(BIN)/mypy

format: ## Auto-fix style and formatting
	$(BIN)/ruff check --fix src tests
	$(BIN)/ruff format src tests

check: lint test ## Lint, type-check and test

seed: ## Generate the sample DuckDB database (deterministic)
	$(BIN)/python -m portfolio_agent.infrastructure.db.seed

run: ## Ask one question, e.g. make run Q="Review UA for January 2025"
	$(BIN)/portfolio-agent "$(Q)"

chat: ## Start an interactive chat session
	$(BIN)/portfolio-agent

clean: ## Remove caches (keeps .venv and data)
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

smoke: ## Check the local Ollama model (needs Ollama running)
	$(BIN)/python scripts/llm_smoke.py

samples: ## Run samples/requests.json against the local model and check expectations
	$(BIN)/python scripts/run_samples.py
