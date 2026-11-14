"""Period-over-period anomaly detection."""

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field

from portfolio_agent.domain.models import Anomaly, KpiMetric, KpiRow


class AnomalyConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    min_change_pct: float = Field(default=30.0, gt=0)
    min_spend: float = Field(default=500.0, ge=0)
    metrics: tuple[KpiMetric, ...] = ("installs", "ua_cost", "revenue", "roas", "cpi")


def detect_anomalies(
    previous: Iterable[KpiRow], current: Iterable[KpiRow], config: AnomalyConfig
) -> list[Anomaly]:

    previous_by_pair = {kpi.pair: kpi for kpi in previous}
    anomalies: list[Anomaly] = []

    for cur in current:
        prev = previous_by_pair.get(cur.pair)

        if prev is None or max(prev.ua_cost, cur.ua_cost) < config.min_spend:
            continue

        for metric in config.metrics:
            before, after = getattr(prev, metric), getattr(cur, metric)

            if before is None or after is None or before == 0:
                continue
            change_pct = round((after - before) / abs(before) * 100, 1)

            if abs(change_pct) >= config.min_change_pct:
                anomalies.append(
                    Anomaly(
                        app_name=cur.app_name,
                        platform=cur.platform,
                        country=cur.country,
                        metric=metric,
                        previous=before,
                        current=after,
                        change_pct=change_pct,
                        direction="up" if change_pct > 0 else "down",
                    )
                )

    return sorted(anomalies, key=lambda a: -abs(a.change_pct))
