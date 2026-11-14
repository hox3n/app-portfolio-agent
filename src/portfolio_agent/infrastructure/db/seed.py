"""Deterministic sample data generator for the app_metrics table."""

import argparse
import csv
import hashlib
import math
import random
import tempfile
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import duckdb

from portfolio_agent.config import get_settings

APPS = ("Paint", "Countdown", "Puzzle", "Fitness", "News")
PLATFORMS = ("iOS", "Android")
COUNTRIES = ("USA", "UK", "Germany", "France", "India")

DEFAULT_SEED = 42
DEFAULT_START = date(2024, 1, 1)
DEFAULT_END = date(2025, 1, 31)

APP_POPULARITY = {"Paint": 0.8, "Countdown": 0.5, "Puzzle": 1.2, "Fitness": 1.0, "News": 0.7}
APP_ADS_SHARE = {"Paint": 0.4, "Countdown": 0.6, "Puzzle": 0.5, "Fitness": 0.15, "News": 0.85}
COUNTRY_INSTALLS = {"USA": 900, "UK": 350, "Germany": 300, "France": 260, "India": 1200}
COUNTRY_CPI = {"USA": 2.6, "UK": 2.1, "Germany": 1.9, "France": 1.7, "India": 0.35}
PLATFORM_INSTALLS = {"iOS": 0.8, "Android": 1.2}
PLATFORM_CPI = {"iOS": 1.3, "Android": 1.0}
PAID_SHARE = 0.7

Pair = tuple[str, str, str]

ROAS_OVERRIDES: dict[Pair, float] = {
    ("Puzzle", "Android", "India"): 0.55,
    ("Countdown", "Android", "USA"): 0.70,
    ("Fitness", "iOS", "USA"): 2.10,
}


@dataclass(frozen=True)
class Event:
    pair: Pair
    start: date
    description: str
    installs: float = 1.0
    cpi: float = 1.0
    in_app: float = 1.0


EVENTS = (
    Event(("News", "iOS", "UK"), date(2025, 1, 25), "CPI spike x2.2", cpi=2.2),
    Event(("Paint", "Android", "Germany"), date(2025, 1, 25), "in-app revenue drop", in_app=0.35),
    Event(("Countdown", "iOS", "France"), date(2025, 1, 25), "install surge x2.5", installs=2.5),
)

SCHEMA_SQL = """
CREATE TABLE app_metrics (
    app_name       VARCHAR NOT NULL,
    platform       VARCHAR NOT NULL CHECK (platform IN ('iOS', 'Android')),
    date           DATE    NOT NULL,
    country        VARCHAR NOT NULL,
    installs       INTEGER NOT NULL CHECK (installs >= 0),
    in_app_revenue DOUBLE  NOT NULL CHECK (in_app_revenue >= 0),
    ads_revenue    DOUBLE  NOT NULL CHECK (ads_revenue >= 0),
    ua_cost        DOUBLE  NOT NULL CHECK (ua_cost >= 0),
    PRIMARY KEY (app_name, platform, date, country)
)
"""

Row = tuple[str, str, str, str, int, float, float, float]


def _pairs() -> list[Pair]:
    return [(a, p, c) for a in APPS for p in PLATFORMS for c in COUNTRIES]


def generate_rows(
    seed: int = DEFAULT_SEED, start: date = DEFAULT_START, end: date = DEFAULT_END
) -> list[Row]:
    rng = random.Random(seed)
    pairs = _pairs()
    pair_scale = {pair: rng.uniform(0.7, 1.3) for pair in pairs}
    pair_roas = {pair: ROAS_OVERRIDES.get(pair, rng.uniform(0.85, 1.6)) for pair in pairs}

    rows: list[Row] = []
    for pair in pairs:
        app, platform, country = pair
        events = [e for e in EVENTS if e.pair == pair]
        for offset in range((end - start).days + 1):
            day = start + timedelta(days=offset)
            active = [e for e in events if day >= e.start]
            installs_mult = math.prod(e.installs for e in active)
            cpi_mult = math.prod(e.cpi for e in active)
            in_app_mult = math.prod(e.in_app for e in active)

            weekend = 1.15 if day.weekday() >= 5 else 1.0
            season = 1 + 0.15 * math.sin(2 * math.pi * day.timetuple().tm_yday / 365)
            installs = round(
                COUNTRY_INSTALLS[country]
                * APP_POPULARITY[app]
                * PLATFORM_INSTALLS[platform]
                * pair_scale[pair]
                * weekend
                * season
                * installs_mult
                * rng.lognormvariate(0, 0.12)
            )
            # Revenue is tied to the cost before CPI events, so a CPI spike raises cost only.
            base_cost = installs * PAID_SHARE * COUNTRY_CPI[country] * PLATFORM_CPI[platform]
            revenue = base_cost * pair_roas[pair] * rng.lognormvariate(0, 0.15)
            ads_revenue = revenue * APP_ADS_SHARE[app]
            in_app_revenue = (revenue - ads_revenue) * in_app_mult
            ua_cost = base_cost * cpi_mult * rng.lognormvariate(0, 0.08)

            rows.append(
                (
                    app,
                    platform,
                    day.isoformat(),
                    country,
                    installs,
                    round(in_app_revenue, 2),
                    round(ads_revenue, 2),
                    round(ua_cost, 2),
                )
            )
    return rows


def checksum(rows: list[Row]) -> str:
    return hashlib.sha256(repr(rows).encode()).hexdigest()[:12]


def write_database(rows: list[Row], db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    for path in (db_path, db_path.with_name(db_path.name + ".wal")):
        path.unlink(missing_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "app_metrics.csv"
        with csv_path.open("w", newline="") as f:
            csv.writer(f).writerows(rows)
        with duckdb.connect(str(db_path)) as con:
            con.execute(SCHEMA_SQL)
            con.execute(f"COPY app_metrics FROM '{csv_path}' (HEADER false)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the sample app_metrics database.")
    settings = get_settings()
    parser.add_argument("--db-path", type=Path, default=settings.db_path)
    parser.add_argument("--seed", type=int, default=settings.seed)
    parser.add_argument("--start", type=date.fromisoformat, default=settings.seed_start)
    parser.add_argument("--end", type=date.fromisoformat, default=settings.seed_end)
    args = parser.parse_args(argv)

    rows = generate_rows(args.seed, args.start, args.end)
    write_database(rows, args.db_path)

    print(f"Database:   {args.db_path}")
    print(f"Rows:       {len(rows):,} ({len(_pairs())} app/platform/country pairs)")
    print(f"Date range: {args.start} to {args.end}")
    print(f"Seed:       {args.seed}  checksum: {checksum(rows)}")
    print("Planted patterns:")
    for pair, roas in ROAS_OVERRIDES.items():
        print(f"  {' / '.join(pair):<28} ROAS ~{roas:.2f} for the whole period")
    for event in EVENTS:
        print(f"  {' / '.join(event.pair):<28} {event.description} from {event.start}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
