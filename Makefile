PYTHON ?= python3
VENV   := .venv
BIN    := $(VENV)/bin

.DEFAULT_GOAL := help
.PHONY: help setup test test-cov lint format seed run clean

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

test-cov: ## Run tests with a coverage report
	$(BIN)/pytest --cov=portfolio_agent --cov-report=term-missing

lint: ## Check style, formatting and types
	$(BIN)/ruff check src tests
	$(BIN)/ruff format --check src tests
	$(BIN)/mypy

format: ## Auto-fix style and formatting
	$(BIN)/ruff check --fix src tests
	$(BIN)/ruff format src tests

seed: ## Generate the sample DuckDB database (step 1)
	@echo "Not implemented yet: see step 1 in docs/DEVELOPMENT_PLAN.md"

run: ## Run the agent CLI
	$(BIN)/portfolio-agent

clean: ## Remove caches (keeps .venv and data)
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
