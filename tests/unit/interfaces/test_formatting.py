"""Tests for plain-text rendering of results."""

from portfolio_agent.application.schemas import AgentResult, Table, ToolCallRecord
from portfolio_agent.interfaces.formatting import format_value, render_table, render_text


def test_format_value() -> None:
    assert [format_value(v) for v in (None, 1234, 1234.5, True, "x")] == [
        "-",
        "1,234",
        "1,234.50",
        "True",
        "x",
    ]


def test_table_aligns_numbers_and_reports_hidden_rows() -> None:
    table = Table(
        columns=["app", "installs"],
        rows=[{"app": f"A{i}", "installs": i * 1000} for i in range(12)],
        source="qa",
    )
    lines = render_table(table, max_rows=3).splitlines()
    assert lines[0].split() == ["app", "installs"]
    assert lines[3].endswith("1,000")
    assert lines[-1].startswith("… 9 more rows")


def test_render_text_has_summary_table_and_footer() -> None:
    result = AgentResult(
        trace_id="abc",
        session_id="s",
        workflow="qa",
        status="ok",
        summary="Done.",
        table=Table(columns=["x"], rows=[{"x": 1}], source="qa"),
        tool_calls=[ToolCallRecord(tool="run_sql", ok=True, duration_ms=3)],
        duration_ms=1500,
    )
    text = render_text(result)
    assert text.startswith("Done.")
    assert "[ok · qa · 1 tool calls · 1.5s · trace abc]" in text
