"""Tests for the plan check: period resolution, name normalization and data-range checks."""

from datetime import date

import pytest

from portfolio_agent.application.planning import (
    PlanError,
    last_full_month,
    last_full_quarter,
    normalize_plan,
)
from portfolio_agent.application.schemas import Plan
from portfolio_agent.domain.models import DatasetInfo

INFO = DatasetInfo(
    table="app_metrics",
    columns={},
    apps=["Countdown", "Fitness", "News", "Paint", "Puzzle"],
    platforms=["Android", "iOS"],
    countries=["France", "Germany", "India", "UK", "USA"],
    date_min=date(2024, 1, 1),
    date_max=date(2025, 1, 31),
    row_count=19850,
)


def test_names_are_normalized_to_canonical_spelling() -> None:
    plan = Plan(workflow="qa", apps=["puzzle"], platforms=["ios", "ANDROID"], countries=["uk"])
    out = normalize_plan(plan, INFO)
    assert (out.apps, out.platforms, out.countries) == (["Puzzle"], ["Android", "iOS"], ["UK"])


def test_unknown_name_lists_allowed_values() -> None:
    with pytest.raises(PlanError, match="Allowed values: Countdown, Fitness"):
        normalize_plan(Plan(workflow="qa", apps=["Chess"]), INFO)


def test_custom_period_kept() -> None:
    plan = Plan(workflow="qa", period="custom", start=date(2024, 10, 1), end=date(2024, 12, 31))
    out = normalize_plan(plan, INFO)
    assert (out.start, out.end) == (date(2024, 10, 1), date(2024, 12, 31))


def test_dates_without_hint_treated_as_custom() -> None:
    out = normalize_plan(Plan(workflow="qa", start="2024-03-01", end="2024-03-31"), INFO)
    assert out.start == date(2024, 3, 1)


@pytest.mark.parametrize(
    ("workflow", "period", "expected"),
    [
        ("budget_review", "none", (date(2025, 1, 1), date(2025, 1, 31))),
        ("anomaly_check", "none", (date(2025, 1, 25), date(2025, 1, 31))),
        ("qa", "last_7_days", (date(2025, 1, 25), date(2025, 1, 31))),
        ("qa", "last_14_days", (date(2025, 1, 18), date(2025, 1, 31))),
        ("qa", "last_30_days", (date(2025, 1, 2), date(2025, 1, 31))),
        ("qa", "last_month", (date(2025, 1, 1), date(2025, 1, 31))),
        ("qa", "last_quarter", (date(2024, 10, 1), date(2024, 12, 31))),
    ],
)
def test_relative_periods_resolved_against_last_data_day(
    workflow: str, period: str, expected: tuple[date, date]
) -> None:
    out = normalize_plan(Plan.model_validate({"workflow": workflow, "period": period}), INFO)
    assert (out.start, out.end) == expected


def test_qa_without_period_has_no_dates() -> None:
    out = normalize_plan(Plan(workflow="qa"), INFO)
    assert (out.start, out.end) == (None, None)


def test_last_full_month_mid_month() -> None:
    assert last_full_month(date(2025, 1, 15)) == (date(2024, 12, 1), date(2024, 12, 31))


def test_last_full_quarter_mid_quarter() -> None:
    assert last_full_quarter(date(2024, 5, 10)) == (date(2024, 1, 1), date(2024, 3, 31))


def test_period_outside_data_rejected() -> None:
    plan = Plan(workflow="budget_review", start="2023-01-01", end="2023-01-31")
    with pytest.raises(PlanError, match="only available from 2024-01-01 to 2025-01-31"):
        normalize_plan(plan, INFO)


def test_custom_needs_both_dates() -> None:
    with pytest.raises(PlanError, match="both start and end"):
        normalize_plan(Plan(workflow="qa", period="custom", start="2024-01-01"), INFO)


def test_start_after_end_rejected() -> None:
    with pytest.raises(PlanError, match="after its end"):
        normalize_plan(Plan(workflow="qa", start="2024-02-01", end="2024-01-01"), INFO)


def test_anomaly_check_needs_earlier_data() -> None:
    plan = Plan(workflow="anomaly_check", start="2024-01-01", end="2024-01-07")
    with pytest.raises(PlanError, match="no earlier data"):
        normalize_plan(plan, INFO)


def test_refuse_and_export_pass_through() -> None:
    plan = Plan(workflow="refuse", apps=["Chess"])
    assert normalize_plan(plan, INFO) == plan


def test_plan_accepts_sloppy_llm_values() -> None:
    plan = Plan.model_validate(
        {"workflow": "qa", "start": "", "apps": "Puzzle", "countries": '["UK", "USA"]'}
    )
    assert (plan.start, plan.apps, plan.countries) == (None, ["Puzzle"], ["UK", "USA"])


def test_data_range_errors_are_not_retryable() -> None:
    plan = Plan(workflow="budget_review", start="2023-01-01", end="2023-01-31")
    with pytest.raises(PlanError) as err:
        normalize_plan(plan, INFO)
    assert err.value.retryable is False


def test_name_errors_are_retryable() -> None:
    with pytest.raises(PlanError) as err:
        normalize_plan(Plan(workflow="qa", apps=["Chess"]), INFO)
    assert err.value.retryable is True
