from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .benchmark_schema import (
    MARKER_CSV_FIELDS,
    RUN_CSV_FIELDS,
    SKILL_CSV_FIELDS,
    TEXT_FIELD_CSV_FIELDS,
    TOOL_CSV_FIELDS,
)
from .marker_dimensions import MARKER_DIMENSIONS


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def write_benchmark_result(run_path: Path, result: dict[str, Any]) -> None:
    (run_path / "benchmark_result.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    tables_dir = run_path / "benchmark_tables"
    write_csv(tables_dir / "run.csv", [result["run"]], RUN_CSV_FIELDS)
    write_csv(tables_dir / "tools.csv", result["tools"], TOOL_CSV_FIELDS)
    for dimension in MARKER_DIMENSIONS:
        write_csv(
            tables_dir / f"{dimension.table_name}.csv",
            result[dimension.summary_key],
            MARKER_CSV_FIELDS,
        )
    write_csv(tables_dir / "skills.csv", result["skills"], SKILL_CSV_FIELDS)
    write_csv(
        tables_dir / "text_fields.csv", result["text_fields"], TEXT_FIELD_CSV_FIELDS
    )
