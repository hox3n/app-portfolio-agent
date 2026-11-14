"""MetricsRepository on DuckDB, read-only connection."""

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb

from portfolio_agent.application.ports import QueryResult, RepositoryError
from portfolio_agent.domain.models import DatasetInfo, MetricRow, Period

TABLE = "app_metrics"

_FETCH_METRICS_SQL = f"""
SELECT app_name, platform, country,
       SUM(installs)::BIGINT          AS installs,
       ROUND(SUM(in_app_revenue), 2)  AS in_app_revenue,
       ROUND(SUM(ads_revenue), 2)     AS ads_revenue,
       ROUND(SUM(ua_cost), 2)         AS ua_cost
FROM {TABLE}
WHERE date BETWEEN $start AND $end {{filters}}
GROUP BY app_name, platform, country
ORDER BY app_name, platform, country
"""


class DuckDBMetricsRepository:
    def __init__(self, db_path: Path) -> None:
        if not db_path.exists():
            raise RepositoryError(f"database not found: {db_path} (run `make seed`)")
        self._db_path = db_path

    def _connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(
            str(self._db_path),
            read_only=True,
            config={"enable_external_access": False, "lock_configuration": True},
        )

    def describe(self) -> DatasetInfo:
        try:
            with self._connect() as con:
                columns = {
                    name: dtype for name, dtype, *_ in con.execute(f"DESCRIBE {TABLE}").fetchall()
                }

                def distinct(col: str) -> list[str]:
                    sql = f"SELECT DISTINCT {col} FROM {TABLE} ORDER BY 1"
                    return [r[0] for r in con.execute(sql).fetchall()]

                stats = con.execute(f"SELECT MIN(date), MAX(date), COUNT(*) FROM {TABLE}")
                date_min, date_max, row_count = stats.fetchone() or (None, None, 0)
                return DatasetInfo(
                    table=TABLE,
                    columns=columns,
                    apps=distinct("app_name"),
                    platforms=distinct("platform"),
                    countries=distinct("country"),
                    date_min=date_min,
                    date_max=date_max,
                    row_count=row_count,
                )
        except duckdb.Error as e:
            raise RepositoryError(str(e)) from e

    def fetch_metrics(
        self,
        period: Period,
        *,
        apps: Sequence[str] | None = None,
        platforms: Sequence[str] | None = None,
        countries: Sequence[str] | None = None,
    ) -> list[MetricRow]:
        params: dict[str, Any] = {"start": period.start, "end": period.end}
        filters = ""
        for column, values in (("app_name", apps), ("platform", platforms), ("country", countries)):
            if values:
                params[column] = list(values)
                filters += f" AND list_contains(${column}, {column})"

        try:
            with self._connect() as con:
                cursor = con.execute(_FETCH_METRICS_SQL.format(filters=filters), params)
                names = [d[0] for d in cursor.description]
                rows = cursor.fetchall()
                return [MetricRow(**dict(zip(names, row, strict=True))) for row in rows]

        except duckdb.Error as e:
            raise RepositoryError(str(e)) from e

    def run_select(self, sql: str, max_rows: int) -> QueryResult:
        try:
            with self._connect() as con:
                cursor = con.execute(sql)
                if cursor.description is None:
                    return QueryResult(columns=[], rows=[], truncated=False)
                names = [d[0] for d in cursor.description]
                fetched = cursor.fetchmany(max_rows + 1)
        except duckdb.Error as e:
            raise RepositoryError(str(e)) from e

        rows = [
            {name: _to_json_value(value) for name, value in zip(names, row, strict=True)}
            for row in fetched[:max_rows]
        ]
        return QueryResult(columns=names, rows=rows, truncated=len(fetched) > max_rows)


def _to_json_value(value: Any) -> Any:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value
