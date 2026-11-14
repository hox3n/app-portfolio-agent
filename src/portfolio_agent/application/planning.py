"""Plan check: resolves periods and validates the planner's output against the real data."""

import calendar
from datetime import date, timedelta

from portfolio_agent.application.schemas import Plan
from portfolio_agent.domain.models import DatasetInfo, Period


class PlanError(ValueError):
    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def last_full_month(today: date) -> tuple[date, date]:
    start, end = _month_bounds(today.year, today.month)
    if today == end:
        return start, end
    previous = start - timedelta(days=1)
    return _month_bounds(previous.year, previous.month)


def last_full_quarter(today: date) -> tuple[date, date]:
    quarter_start_month = 3 * ((today.month - 1) // 3) + 1
    start = date(today.year, quarter_start_month, 1)
    end = _month_bounds(today.year, quarter_start_month + 2)[1]
    if today == end:
        return start, end
    previous_end = start - timedelta(days=1)
    return date(previous_end.year, previous_end.month - 2, 1), previous_end


def resolve_period(plan: Plan, today: date, anomaly_days: int) -> tuple[date, date] | None:
    hint = plan.period
    if hint == "none" and plan.start and plan.end:
        hint = "custom"
    if hint == "none":
        if plan.workflow == "budget_review":
            hint = "last_month"
        elif plan.workflow == "anomaly_check":
            return today - timedelta(days=anomaly_days - 1), today
        else:
            return None
    if hint == "custom":
        if plan.start is None or plan.end is None:
            raise PlanError("a custom period needs both start and end dates")
        return plan.start, plan.end
    if hint == "last_month":
        return last_full_month(today)
    if hint == "last_quarter":
        return last_full_quarter(today)
    days = {"last_7_days": 7, "last_14_days": 14, "last_30_days": 30}[hint]
    return today - timedelta(days=days - 1), today


def _canonical(values: list[str] | None, allowed: list[str], field: str) -> list[str] | None:
    if not values:
        return None
    lookup = {a.lower(): a for a in allowed}
    unknown = [v for v in values if v.strip().lower() not in lookup]
    if unknown:
        raise PlanError(
            f"unknown {field}: {', '.join(unknown)}. Allowed values: {', '.join(allowed)}"
        )
    found = {lookup[v.strip().lower()] for v in values}
    return [a for a in allowed if a in found]


def normalize_plan(plan: Plan, info: DatasetInfo, anomaly_days: int = 7) -> Plan:
    if plan.workflow in ("refuse", "clarify", "export"):
        return plan

    apps = _canonical(plan.apps, info.apps, "apps")
    platforms = _canonical(plan.platforms, info.platforms, "platforms")
    countries = _canonical(plan.countries, info.countries, "countries")

    bounds = resolve_period(plan, info.date_max, anomaly_days)
    start, end = bounds if bounds else (None, None)
    if start is not None and end is not None:
        if start > end:
            raise PlanError(f"the period start {start} is after its end {end}")
        if start < info.date_min or end > info.date_max:
            raise PlanError(
                f"data is only available from {info.date_min} to {info.date_max}",
                retryable=False,
            )
        if plan.workflow == "anomaly_check":
            previous = Period(start=start, end=end).previous()
            if previous.start < info.date_min:
                raise PlanError(
                    f"there is no earlier data to compare {start} to {end} with; "
                    f"data starts on {info.date_min}",
                    retryable=False,
                )

    return plan.model_copy(
        update={
            "period": "custom" if start else "none",
            "start": start,
            "end": end,
            "apps": apps,
            "platforms": platforms,
            "countries": countries,
            "reason": plan.reason[:300],
        }
    )
