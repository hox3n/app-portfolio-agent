"""Exporter that writes CSV files into the export folder."""

import csv
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _safe_cell(value: Any) -> Any:
    # Prevents spreadsheet formula injection when the CSV is opened in Excel/Sheets.
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value


class CsvExporter:
    def __init__(self, export_dir: Path) -> None:
        self._dir = export_dir

    def export_csv(
        self, columns: Sequence[str], rows: Sequence[Mapping[str, Any]], name: str
    ) -> Path:

        self._dir.mkdir(parents=True, exist_ok=True)
        path = (self._dir / f"{name}.csv").resolve()

        if path.parent != self._dir.resolve():
            raise ValueError("export path must stay inside the export folder")

        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(columns), extrasaction="ignore")
            writer.writeheader()
            writer.writerows({k: _safe_cell(v) for k, v in row.items()} for row in rows)

        return path
