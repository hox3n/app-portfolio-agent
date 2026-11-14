"""KPI formulas: revenue, profit, ROAS, CPI, ARPI."""

from collections.abc import Iterable

from portfolio_agent.domain.models import KpiRow, MetricRow


def _ratio(numeratior: float, denominator: float) -> float | None:
    return round(numeratior / denominator, 4) if denominator > 0 else None


def compute_kpis(row: MetricRow) -> KpiRow:

    revenue = round(row.in_app_revenue + row.ads_revenue, 2)
    return KpiRow(
        app_name=row.app_name,
        platform=row.platform,
        country=row.country,
        installs=row.installs,
        ua_cost=row.ua_cost,
        revenue=revenue,
        profit=round(revenue - row.ua_cost, 2),
        roas=_ratio(revenue, row.ua_cost),
        cpi=_ratio(row.ua_cost, row.installs),
        arpi=_ratio(revenue, row.installs),
    )


def compute_all(rows: Iterable[MetricRow]) -> list[KpiRow]:
    return [compute_kpis(row) for row in rows]
