"""KPI formulas: revenue, profit, ROAS, CPI, ARPI."""

from collections.abc import Iterable, Sequence

from portfolio_agent.domain.models import GroupDimension, GroupTotals, KpiRow, MetricRow, Totals

GROUP_FIELDS: dict[GroupDimension, str] = {
    "app": "app_name",
    "platform": "platform",
    "country": "country",
}


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


def totals_of(rows: Iterable[MetricRow]) -> Totals:
    rows = list(rows)
    installs = sum(r.installs for r in rows)
    in_app = round(sum(r.in_app_revenue for r in rows), 2)
    ads = round(sum(r.ads_revenue for r in rows), 2)
    cost = round(sum(r.ua_cost for r in rows), 2)
    revenue = round(in_app + ads, 2)
    return Totals(
        rows=len(rows),
        installs=installs,
        in_app_revenue=in_app,
        ads_revenue=ads,
        revenue=revenue,
        ua_cost=cost,
        profit=round(revenue - cost, 2),
        roas=_ratio(revenue, cost),
        cpi=_ratio(cost, installs),
        arpi=_ratio(revenue, installs),
    )


def group_totals(
    rows: Iterable[MetricRow], dimensions: Sequence[GroupDimension]
) -> list[GroupTotals]:
    buckets: dict[tuple[str, ...], list[MetricRow]] = {}
    for row in rows:
        key = tuple(getattr(row, GROUP_FIELDS[d]) for d in dimensions)
        buckets.setdefault(key, []).append(row)
    return [
        GroupTotals(
            group=dict(zip(dimensions, key, strict=True)), **totals_of(members).model_dump()
        )
        for key, members in sorted(buckets.items())
    ]
