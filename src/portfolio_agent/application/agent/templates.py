"""Structured facts for each workflow and the deterministic summaries built from them."""

from collections.abc import Mapping
from typing import Any

from portfolio_agent.application.schemas import Table
from portfolio_agent.domain.models import Action, Anomaly, Decision, KpiRow, Period

TOP_N = 5
MAX_ANOMALIES = 10
METRIC_LABELS = {
    "installs": "installs",
    "ua_cost": "UA cost",
    "revenue": "revenue",
    "profit": "profit",
    "roas": "ROAS",
    "cpi": "CPI",
    "arpi": "ARPI",
}


def money(value: float) -> str:
    return f"-${abs(value):,.2f}" if value < 0 else f"${value:,.2f}"


def pair_name(app: str, platform: str, country: str) -> str:
    return f"{app} / {platform} / {country}"


def _period(period: Period) -> dict[str, str]:
    return {"start": period.start.isoformat(), "end": period.end.isoformat()}


def budget_facts(
    period: Period,
    decisions: list[Decision],
    kpis: list[KpiRow],
    counts: Mapping[Action, int],
    top_n: int = TOP_N,
) -> dict[str, Any]:
    cost = round(sum(k.ua_cost for k in kpis), 2)
    revenue = round(sum(k.revenue for k in kpis), 2)

    def item(d: Decision) -> dict[str, Any]:
        return {
            "pair": pair_name(d.app_name, d.platform, d.country),
            "roas": round(d.roas, 2) if d.roas is not None else None,
            "ua_cost": d.ua_cost,
            "profit": d.profit,
            "rule": d.rule,
        }

    return {
        "period": _period(period),
        "pairs_reviewed": len(decisions),
        "counts": counts,
        "total_ua_cost": cost,
        "total_revenue": revenue,
        "total_profit": round(revenue - cost, 2),
        "portfolio_roas": round(revenue / cost, 2) if cost else None,
        "top_cuts": [item(d) for d in decisions if d.action == "cut"][:top_n],
        "top_scales": [item(d) for d in decisions if d.action == "scale"][:top_n],
    }


def budget_summary(facts: dict[str, Any]) -> str:
    period, counts = facts["period"], facts["counts"]
    headline = (
        f"UA budget review for {period['start']} to {period['end']}: "
        f"{facts['pairs_reviewed']} app/platform/country pairs, "
        f"UA cost {money(facts['total_ua_cost'])}, revenue {money(facts['total_revenue'])}, "
        f"profit {money(facts['total_profit'])}"
    )
    if facts["portfolio_roas"] is not None:
        headline += f", ROAS {facts['portfolio_roas']:.2f}"
    lines = [
        headline + ".",
        f"Recommendation: cut {counts.get('cut', 0)}, scale {counts.get('scale', 0)}, "
        f"maintain {counts.get('maintain', 0)}.",
    ]
    for label, key in (("Cut", "top_cuts"), ("Scale", "top_scales")):
        if facts[key]:
            items = "; ".join(
                f"{i['pair']} (ROAS {i['roas']:.2f}, profit {money(i['profit'])})"
                for i in facts[key]
            )
            shown = "" if len(facts[key]) == counts.get(label.lower(), 0) else " (largest)"
            lines.append(f"{label}{shown}: {items}.")
    return "\n".join(lines)


def anomaly_facts(
    current: Period, previous: Period, anomalies: list[Anomaly], max_items: int = MAX_ANOMALIES
) -> dict[str, Any]:
    return {
        "current_period": _period(current),
        "previous_period": _period(previous),
        "anomaly_count": len(anomalies),
        "top_anomalies": [
            {
                "pair": pair_name(a.app_name, a.platform, a.country),
                "metric": a.metric,
                "previous": round(a.previous, 2),
                "current": round(a.current, 2),
                "change_pct": a.change_pct,
                "direction": a.direction,
            }
            for a in anomalies[:max_items]
        ],
    }


def anomaly_summary(facts: dict[str, Any]) -> str:
    cur, prev, count = facts["current_period"], facts["previous_period"], facts["anomaly_count"]
    head = f"Compared {cur['start']} to {cur['end']} with {prev['start']} to {prev['end']}: "
    if count == 0:
        return head + "no significant changes."
    lines = [head + f"{count} significant change{'s' if count != 1 else ''}."]
    for i in facts["top_anomalies"]:
        label = METRIC_LABELS.get(i["metric"], i["metric"])
        lines.append(
            f"- {i['pair']}: {label} {i['direction']} {abs(i['change_pct']):.1f}% "
            f"({i['previous']:,.2f} → {i['current']:,.2f})"
        )
    if count > len(facts["top_anomalies"]):
        lines.append(f"(showing the {len(facts['top_anomalies'])} largest)")
    return "\n".join(lines)


def table_fallback_summary(table: Table) -> str:
    rows = len(table.rows)
    return (
        "I couldn't verify the wording of the answer against the data, so here is the "
        f"result from {table.source} ({rows} row{'s' if rows != 1 else ''})."
    )
