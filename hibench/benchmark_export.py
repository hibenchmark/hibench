from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .analyze import build_run_summary
from .benchmark_artifacts import load_manifest, parser_id_from_manifest
from .benchmark_io import write_csv
from .benchmark_runs import BenchmarkRunInfo, benchmark_run_info_from_result
from .benchmark_schema import (
    MARKER_CSV_FIELDS,
    RESULT_SCHEMA_VERSION,
    RUN_CSV_FIELDS,
    SKILL_CSV_FIELDS,
    TEXT_FIELD_CSV_FIELDS,
    TOOL_CSV_FIELDS,
    build_benchmark_result,
)
from .marker_dimensions import MARKER_DIMENSIONS


def load_benchmark_result(run_path: Path) -> dict[str, Any]:
    return json.loads((run_path / "benchmark_result.json").read_text(encoding="utf-8"))


def _benchmark_result_for_export(run_path: Path) -> dict[str, Any]:
    if (run_path / "benchmark_result.json").exists():
        return load_benchmark_result(run_path)

    manifest = load_manifest(run_path)
    summary = build_run_summary(run_path, parser_id=parser_id_from_manifest(manifest))
    return build_benchmark_result(run_path, manifest, summary)


def _dedupe_export_results(
    results: list[tuple[Path, dict[str, Any], BenchmarkRunInfo]],
) -> list[tuple[Path, dict[str, Any], BenchmarkRunInfo]]:
    selected: dict[
        tuple[str, str, str], tuple[Path, dict[str, Any], BenchmarkRunInfo]
    ] = {}
    for run_path, result, info in results:
        identity = info.export_identity
        current = selected.get(identity)
        if (
            current is None
            or info.export_preference_key >= current[2].export_preference_key
        ):
            selected[identity] = (run_path, result, info)
    return sorted(selected.values(), key=lambda item: str(item[0]))


def export_benchmark_results(
    runs_dir: str | Path = "runs", out_dir: str | Path = "results"
) -> dict[str, Any]:
    runs_path = Path(runs_dir)
    out_path = Path(out_dir)
    source_results: list[tuple[Path, dict[str, Any], BenchmarkRunInfo]] = []
    run_rows: list[dict[str, Any]] = []
    tool_rows: list[dict[str, Any]] = []
    marker_rows = {dimension.summary_key: [] for dimension in MARKER_DIMENSIONS}
    skill_rows: list[dict[str, Any]] = []
    text_field_rows: list[dict[str, Any]] = []

    if runs_path.exists():
        for run_path in sorted(
            path
            for path in runs_path.iterdir()
            if path.is_dir() and (path / "requests").is_dir()
        ):
            result = _benchmark_result_for_export(run_path)
            source_results.append(
                (run_path, result, benchmark_run_info_from_result(run_path, result))
            )

    benchmarkable_results = [
        item for item in source_results if item[2].has_primary_benchmark_request
    ]
    selected_results = _dedupe_export_results(benchmarkable_results)
    for _run_path, result, _info in selected_results:
        run_rows.append(result["run"])
        tool_rows.extend(result["tools"])
        for dimension in MARKER_DIMENSIONS:
            marker_rows[dimension.summary_key].extend(result[dimension.summary_key])
        skill_rows.extend(result.get("skills") or [])
        text_field_rows.extend(result["text_fields"])

    write_csv(out_path / "runs.csv", run_rows, RUN_CSV_FIELDS)
    write_csv(out_path / "tools.csv", tool_rows, TOOL_CSV_FIELDS)
    for dimension in MARKER_DIMENSIONS:
        write_csv(
            out_path / f"{dimension.table_name}.csv",
            marker_rows[dimension.summary_key],
            MARKER_CSV_FIELDS,
        )
    write_csv(out_path / "skills.csv", skill_rows, SKILL_CSV_FIELDS)
    write_csv(out_path / "text_fields.csv", text_field_rows, TEXT_FIELD_CSV_FIELDS)
    manifest = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "runs_dir": str(runs_path),
        "out_dir": str(out_path),
        "unique_by": ["agent_id", "agent_version"],
        "source_run_count": len(source_results),
        "skipped_no_primary_run_count": len(source_results)
        - len(benchmarkable_results),
        "deduplicated_run_count": len(benchmarkable_results) - len(run_rows),
        "run_count": len(run_rows),
        "tool_row_count": len(tool_rows),
        **{
            f"{dimension.run_field_prefix}_row_count": len(
                marker_rows[dimension.summary_key]
            )
            for dimension in MARKER_DIMENSIONS
        },
        "skill_row_count": len(skill_rows),
        "text_field_row_count": len(text_field_rows),
        "files": {
            "runs": str(out_path / "runs.csv"),
            "tools": str(out_path / "tools.csv"),
            **{
                dimension.summary_key: str(out_path / f"{dimension.table_name}.csv")
                for dimension in MARKER_DIMENSIONS
            },
            "skills": str(out_path / "skills.csv"),
            "text_fields": str(out_path / "text_fields.csv"),
        },
    }
    (out_path / "export.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest
