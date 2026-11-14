"""Plain-text rendering of an AgentResult for the CLI."""

from typing import Any

from portfolio_agent.application.schemas import AgentResult, Table

MAX_ROWS = 10
MAX_COLS = 10


def format_value(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value)


def render_table(table: Table, max_rows: int = MAX_ROWS) -> str:
    columns = table.columns[:MAX_COLS]
    cells = [[format_value(row.get(c)) for c in columns] for row in table.rows[:max_rows]]
    widths = [max([len(c), *(len(r[i]) for r in cells)]) for i, c in enumerate(columns)]
    numeric = [
        all(isinstance(row.get(c), int | float) for row in table.rows[:max_rows] if row.get(c))
        for c in columns
    ]

    def line(values: list[str]) -> str:
        return "  ".join(
            v.rjust(w) if num else v.ljust(w)
            for v, w, num in zip(values, widths, numeric, strict=True)
        ).rstrip()

    lines = [line(columns), "  ".join("-" * w for w in widths), *(line(r) for r in cells)]
    hidden = len(table.rows) - max_rows
    if hidden > 0:
        lines.append(f"… {hidden} more rows (say 'export that' to get them all as CSV)")
    return "\n".join(lines)


def footer(result: AgentResult) -> str:
    return (
        f"[{result.status} · {result.workflow or '-'} · {len(result.tool_calls)} tool calls · "
        f"{result.duration_ms / 1000:.1f}s · trace {result.trace_id}]"
    )


def render_text(result: AgentResult, max_rows: int = MAX_ROWS) -> str:
    parts = [result.summary]
    if result.table and result.table.rows:
        parts.append(render_table(result.table, max_rows))
    parts.append(footer(result))
    return "\n\n".join(parts)
