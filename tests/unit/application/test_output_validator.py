"""Tests for the number check that guards LLM summaries and answers."""

import pytest

from portfolio_agent.application.guardrails.output_validator import (
    numbers_in,
    unsupported_numbers,
)

FACTS = {
    "total_profit": 248224.2,
    "portfolio_roas": 1.2467,
    "change_pct": -54.5,
    "share": 0.375,
    "pairs": [{"installs": 62569}, {"installs": 1500}],
}


@pytest.mark.parametrize(
    "text",
    [
        "Profit was $248,224.20 with ROAS 1.25.",
        "Profit was about $248K, ROAS 1.2467.",
        "ROAS fell 54.5% while the share was 37.5%.",
        "Installs were 62,569 on 2025-01-31 and January 31, 2025.",
        "The top 3 pairs in 2024 had 2 pairs reviewed.",
        "Profit was $0.25M.",
        "Profit was $248,224 (rounded and truncated agree here).",
    ],
)
def test_supported_numbers_pass(text: str) -> None:
    assert unsupported_numbers(text, FACTS) == []


@pytest.mark.parametrize(
    ("text", "bad"),
    [
        ("Profit was $238,000.", "$238,000"),
        ("Profit was $238K.", "$238K"),
        ("ROAS was 1.31.", "1.31"),
        ("Installs reached 61,000.", "61,000"),
        ("Five pairs were scaled.", "5"),
        ("We found 7 changes.", "7"),
    ],
)
def test_invented_numbers_flagged(text: str, bad: str) -> None:
    assert unsupported_numbers(text, FACTS) == [bad]


def test_list_lengths_count_as_data() -> None:
    assert 2.0 in numbers_in(FACTS)


def test_booleans_ignored() -> None:
    assert numbers_in({"ok": True, "x": 3}) == [3.0]


def test_counts_must_come_from_count_fields_not_sample_lists() -> None:
    facts = {"counts": {"scale": 10, "cut": 2}, "top_scales": [{"x": 0.1}] * 5}
    assert unsupported_numbers("Ten pairs scale and two are cut.", facts) == []
    assert unsupported_numbers("Five pairs were scaled.", facts) == ["5"]
    assert unsupported_numbers("The top 5 scales are listed.", facts) == []


def test_list_lengths_of_full_lists_are_facts() -> None:
    assert unsupported_numbers("We have 5 apps.", {"apps": ["a", "b", "c", "d", "e"]}) == []


def test_zero_and_one_are_not_checked() -> None:
    assert unsupported_numbers("One pair stands out; none had 0 installs.", {}) == []


def test_off_by_one_on_exact_values_is_flagged() -> None:
    facts = {"counts": {"cut": 2, "scale": 10, "maintain": 38}}
    assert unsupported_numbers("cut 2, scale 10, maintain 37", facts) == ["37"]
    assert unsupported_numbers("cut 2, scale 10, maintain 38", facts) == []


def test_rounding_and_truncation_both_accepted() -> None:
    facts = {"profit": 379754.68}
    assert unsupported_numbers("$379,754 or $379,755", facts) == []
    assert unsupported_numbers("$379,753", facts) == ["$379,753"]
