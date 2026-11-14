# Development Plan

Step-by-step plan for building the App Portfolio Analytics Agent. The final design is in [ARCHITECTURE.md](ARCHITECTURE.md) and the [README](../README.md).

We build **from the inside out**: data and business rules first, then tools, then the LLM, then the agent. Every step ends with something that can be run and checked. Move to the next step only once the current one is verified.

**Status:** ⬜ not started · 🟨 in progress · ✅ done

| # | Step | Status |
|---|---|---|
| 0 | [Project setup](#step-0--project-setup) | ✅ |
| 1 | [Data layer](#step-1--data-layer) | ✅ |
| 2 | [Domain: business rules](#step-2--domain-business-rules) | ✅ |
| 3 | [Tools, contracts and logging](#step-3--tools-contracts-and-logging) (3a logging + SQL guard, 3b contracts + tools) | ✅ |
| 4 | [LLM adapters](#step-4--llm-adapters) | ✅ |
| 5 | [Agent core: guard and planner](#step-5--agent-core-guard-and-planner) | ✅ |
| 6 | [First full workflow: W2 budget review + CLI](#step-6--first-full-workflow-w2-budget-review--cli) | ✅ |
| 7 | [W1 Q&A with tool calling](#step-7--w1-qa-with-tool-calling) | ✅ |
| 8 | [W3 anomaly check, W4 export, sessions](#step-8--w3-anomaly-check-w4-export-sessions) | ✅ |
| 9 | [LLM summary and output validator](#step-9--llm-summary-and-output-validator) | ✅ |
| 10 | [Integration tests and samples](#step-10--integration-tests-and-samples) | ✅ |
| 11 | [Cleanup](#step-11--cleanup) (Slack adapter built, then removed) | ✅ |
| 12 | [Final README](#step-12--final-readme) | ✅ |

---

## Decisions

| Topic | Decision |
|---|---|
| Agent framework | LangGraph |
| Architecture | Clean Architecture: domain → application → infrastructure / interfaces |
| Database | DuckDB, opened read-only by the agent |
| Local LLM | `qwen3.5:4b` via Ollama, **thinking off** (thinking on took 216 s per call and answered wrong; off took under 1 s and answered correctly). Model name configurable. |
| Tool use | W1: the LLM chooses tools through function calling. W2–W4: fixed sequence. |
| Tool safety | Every tool has Pydantic input/output contracts enforced by one wrapper. |
| Tests | Use a fake LLM, so no Ollama is needed to run them. |
| Version control | Local only. Commit after each step if wanted; no push for now. |
| Budget rules | **Cut:** ROAS < 0.8 · **Scale:** ROAS ≥ 1.5 and spend ≥ $1,000 · **Maintain:** everything else. Configurable. |
| Anomalies | A KPI (installs, UA cost, revenue, ROAS, CPI) changes by ≥ 30% between two equal-length periods, for pairs that spent ≥ $500. Configurable. |

**Open questions** (decide in the step shown):
- [x] Budget rule thresholds for scale / maintain / cut (step 2)
- [x] Anomaly threshold and which KPIs to watch (step 2)
- [x] Optional hosted LLM: **no** for now; listed as a next step in the README (one extra adapter behind the `LLMClient` port)
- [x] Keep the Slack adapter: no. It was built and unit-tested, then removed to keep the scope to the verified CLI path; listed as a next step

---

## Step 0 — Project setup

**Goal:** a project that installs and runs its (empty) test suite with one command.

**Build**
- `pyproject.toml`: dependencies (langgraph, langchain-ollama, duckdb, pydantic, pydantic-settings, sqlglot, python-dotenv), dev tools (pytest, ruff, mypy), and a `portfolio-agent` CLI entry point
- `.venv`, installed in editable mode
- `Makefile`: `setup`, `seed`, `test`, `lint`, `run`
- `.env.example` with every setting documented
- `config.py`: typed settings loaded from the environment

**Verify**
- `make setup` completes
- `make test` runs and reports 0 tests
- `make lint` passes

**Concepts:** `src/` layout, editable installs, settings from the environment.

---

## Step 1 — Data layer

**Goal:** a reproducible sample database and a safe way to read it.

**Build**
- `infrastructure/db/seed.py`: generates the `app_metrics` data with a **fixed random seed** into DuckDB (same data on every machine). Dense daily data for every app × platform × country, so reviews and comparisons have full coverage. A few deliberate patterns, such as a loss-making pair and a sudden cost spike, give the budget rules and anomaly check something real to find.
- `infrastructure/db/duckdb_repository.py`: opens the database **read-only** and implements `MetricsRepository` (`fetch_metrics`, `run_select`, `get_schema`)
- `application/ports.py`: the `MetricsRepository` interface

**Verify**
- `make seed` prints the row count and date range
- Running seed twice produces identical data
- A write attempt through the repository fails

**Concepts:** ports and adapters, deterministic test data, read-only access as a guardrail.

---

## Step 2 — Domain: business rules

**Goal:** all business logic as pure, fully tested functions.

**Build**
- `domain/models.py`: `Period`, `MetricRow`, `KpiRow`, `Decision`, `Anomaly`
- `domain/kpis.py`: revenue, profit, ROAS, CPI, ARPI, with safe division by zero
- `domain/budget_rules.py`: scale / maintain / cut, with thresholds from config and the rule that fired recorded
- `domain/anomalies.py`: period-over-period change detection
- Unit tests in `tests/unit/domain/`

**Decide:** thresholds for the budget rules and anomaly detection, documented in the README.

**Verify**
- `make test`: KPI results match hand-computed values; every rule fires in at least one test; edge cases pass (zero cost, zero installs, empty input)

**Concepts:** keeping business logic free of I/O and frameworks; the LLM never calculates numbers.

---

## Step 3 — Tools, contracts and logging

**Goal:** every capability the agent has is a typed tool with checked input and output, and every call is logged.

**Build**
- `infrastructure/observability/`: JSON logger, `trace_id` context, decision record
- `application/tools/contracts.py`: Pydantic input/output models for all 7 tools
- `application/tools/registry.py`: wrapper that checks input → runs → checks output → logs, and returns a structured `ToolError` on failure
- `application/guardrails/sql_guard.py`: sqlglot check allowing a single SELECT on `app_metrics`, with a forced LIMIT
- The 7 tools: `get_schema`, `run_sql`, `fetch_metrics`, `compute_kpis`, `apply_budget_rules`, `detect_anomalies`, `export_csv`

**Verify**
- Call each tool from a short script and see one JSON log line per call
- `DROP TABLE`, `DELETE`, multiple statements and unknown tables are rejected with a clear error
- Unit tests for the contracts (valid input, invalid input, broken output) and the SQL guard

**Concepts:** contracts at boundaries, structured errors the LLM can act on, the SQL guard as the real defense against prompt injection.

---

## Step 4 — LLM adapters

**Goal:** talk to the local model through one interface that tests can replace.

**Build**
- `application/ports.py`: `LLMClient` interface (structured output + tool calling)
- `infrastructure/llm/ollama_client.py`: qwen3.5:4b with `think=False`, timeouts and retries
- `infrastructure/llm/fake_client.py`: returns scripted responses for tests
- `application/prompts/`: first prompt templates

**Verify**
- A smoke script sends a prompt to qwen and gets a valid Pydantic object back
- Time per call is logged
- The fake client returns its scripted responses in order

**Concepts:** dependency inversion; structured output; why tests must not depend on a real model.

---

## Step 5 — Agent core: guard and planner

**Goal:** the agent understands what is being asked, or refuses safely.

**Build**
- `application/schemas.py`: `Plan`, `AgentResult`, `ToolError`
- `application/guardrails/input_guard.py`: empty, too long, prompt-injection patterns
- `application/agent/state.py` and the nodes `guard.py` and `planner.py`: planner with plan check and retry with the error message
- `application/agent/graph.py`: first version of the graph (guard → planner → stop)

**Verify**
- Normal requests return the right workflow and parameters
- "Ignore previous instructions…", "delete all data" and off-topic requests are refused
- Ambiguous requests return `needs_clarification`
- Unit tests with the fake LLM, including the retry path

**Concepts:** guardrails before the LLM, validating LLM output, retry with error feedback.

---

## Step 6 — First full workflow: W2 budget review + CLI

**Goal:** the first end-to-end run, from a typed request to a structured decision.

**Build**
- Node `budget_review.py`: fetch_metrics → compute_kpis → apply_budget_rules
- Node `respond.py` with a **template summary** (no LLM yet)
- `application/service.py`: `AgentService.run()`
- `bootstrap.py`: wires the real adapters together
- `interfaces/cli.py`: `portfolio-agent "<request>"`, with flags for JSON output and showing the trace

**Verify**
- `portfolio-agent "Review UA performance for January 2025"` returns an `AgentResult` with decisions and a readable summary
- The same request twice gives identical decisions
- The logs show every step and tool call under one `trace_id`

**Concepts:** the composition root; why a fixed workflow suits business decisions.

---

## Step 7 — W1 Q&A with tool calling

**Goal:** the LLM answers open questions by choosing and calling tools itself.

**Build**
- Node `tool_agent.py`: function-calling loop over `get_schema`, `run_sql`, `compute_kpis`, with a step limit (default 6)
- Tool definitions generated from the Pydantic contracts
- Structured tool errors sent back to the LLM

**Verify**
- Ask several open questions and check the answers against direct SQL
- The logs show each tool call and its result
- Self-correction works, such as fixing a wrong value after an error or empty result
- The step limit stops a looping agent with `status: error`

**Concepts:** function calling, agent loops, keeping an autonomous agent within limits.

---

## Step 8 — W3 anomaly check, W4 export, sessions

**Goal:** the remaining workflows and multi-turn conversations.

**Build**
- Node `anomaly_check.py`: two periods → compute_kpis → detect_anomalies
- Node `export.py` and `infrastructure/storage/csv_exporter.py`
- `infrastructure/storage/session_store.py`: history and last result per session
- Interactive CLI mode (a chat loop)

**Verify**
- "Anything unusual last week?" finds the anomalies planted in step 1
- After a question, "export that" writes a CSV of the previous result
- "Export that" with no previous result asks the user to clarify

**Concepts:** session state; follow-up questions.

---

## Step 9 — LLM summary and output validator

**Goal:** natural-language summaries whose numbers can be trusted.

**Build**
- Node `summarize.py`: the LLM writes the summary from structured data only
- `application/guardrails/output_validator.py`: schema check, and every number quoted in the text must exist in the data
- Template summary kept as the fallback

**Verify**
- Compare the LLM summary with the template summary for the same request
- A fake LLM summary with a made-up number is caught and replaced by the template

**Concepts:** catching hallucinated numbers, graceful degradation.

---

## Step 10 — Integration tests and samples

**Goal:** prove the whole system works with one command.

**Build**
- `tests/integration/`: full graph runs with the fake LLM on a seeded test database, covering every workflow plus refusal, clarification and error paths
- `samples/`: example requests with expected outputs (JSON)
- `make samples`: runs the samples against the local model and compares results

**Verify**
- `make test` passes, all green
- `make samples` shows matches and any differences

**Concepts:** deterministic end-to-end tests for a non-deterministic system.

---

## Step 11 — Cleanup

**Goal:** a tidy repository. (An optional Slack adapter was also built here and later removed.)

**Build**
- Remove the old root files: `agent.py`, `database.py`, `models.py`, `slackbot.py`, `utils.py`, `requirements.txt`, `README.markdown`

**Verify**
- DM the bot and get the same results as the CLI
- `make lint` and `make test` still pass

---

## Step 12 — Final README

**Goal:** a README that covers every item the task asks for.

**Build:** `README.md` and `docs/ARCHITECTURE.md`, built from the working design notes:
- Problem statement
- Scope and non-scope
- Business cases
- Architecture
- Setup
- How to test
- Example inputs and outputs, with screenshots or logs
- Trade-offs and limitations, including the qwen thinking measurements
- Next steps
- Real-world usage

**Verify:** follow the README from a fresh clone on a clean machine, exactly as a reviewer would.
