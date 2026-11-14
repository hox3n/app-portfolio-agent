"""Runs samples/requests.json against the real local model and checks each expected outcome."""

import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from portfolio_agent.application.schemas import AgentResult
from portfolio_agent.bootstrap import build_service
from portfolio_agent.config import get_settings
from portfolio_agent.infrastructure.observability.logging import configure_logging

SAMPLES = Path("samples/requests.json")
OUTPUTS = Path("samples/outputs")


def check(result: AgentResult, expect: dict[str, Any]) -> list[str]:
    problems = []
    for key in ("workflow", "status"):
        if key in expect and getattr(result, key) != expect[key]:
            problems.append(f"{key}={getattr(result, key)} (expected {expect[key]})")
    for text in expect.get("summary_contains", []):
        if text.lower() not in result.summary.lower():
            problems.append(f"summary lacks {text!r}")
    options = expect.get("summary_contains_any", [])
    if options and not any(o.lower() in result.summary.lower() for o in options):
        problems.append(f"summary lacks any of {options}")
    rows = result.table.rows if result.table else []
    for wanted in expect.get("table_includes", []):
        if not any(all(row.get(k) == v for k, v in wanted.items()) for row in rows):
            problems.append(f"table lacks {wanted}")
    return problems


def main() -> int:
    settings = get_settings()
    configure_logging("WARNING", "text", max_value_chars=settings.log_max_value_chars)
    service = build_service(settings)
    samples = json.loads(SAMPLES.read_text())
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    failures = 0

    print(f"{'sample':<26} {'turn':>4} {'status':<20} {'workflow':<14} {'time':>6}  result")
    for sample in samples:
        session_id = uuid.uuid4().hex[:12]
        outputs = []
        for i, turn in enumerate(sample["turns"], 1):
            started = time.perf_counter()
            result = service.run(turn["request"], session_id)
            elapsed = time.perf_counter() - started
            problems = check(result, turn["expect"])
            failures += bool(problems)
            outputs.append({"request": turn["request"], "result": result.model_dump(mode="json")})
            verdict = "PASS" if not problems else "FAIL: " + "; ".join(problems)
            print(
                f"{sample['id']:<26} {i:>4} {result.status:<20} {result.workflow or '-':<14} "
                f"{elapsed:5.1f}s  {verdict}"
            )
        (OUTPUTS / f"{sample['id']}.json").write_text(json.dumps(outputs, indent=2) + "\n")

    total = sum(len(s["turns"]) for s in samples)
    print(f"\n{total - failures}/{total} turns passed. Full results in {OUTPUTS}/")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
