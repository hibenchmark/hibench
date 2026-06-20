#!/usr/bin/env python3
"""Backfill Anthropic tokenizer totals for captured HiBench runs.

This temporary utility does not rerun agents. It reads each exported run's
stored primary request, sends the exact captured request body text through the
Anthropic Messages token-count endpoint, stores only the returned total on the
run row, and refreshes aggregate CSVs.

Usage:
  ANTHROPIC_API_KEY=... uv run python scripts/backfill_anthropic_tokens.py

ANTHROPIC_API_KEY may also be stored in a repo-local .env file.

The default RPM is intentionally below Anthropic tier-1's documented 100 RPM.
"""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hibench.anthropic_tokens import (  # noqa: E402
    DEFAULT_API_KEY_ENV,
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_RPM,
    AnthropicTokenCounter,
    captured_body_text,
    load_dotenv_file,
    primary_request_record,
    read_json,
)
from hibench.benchmark_export import export_benchmark_results  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill Anthropic total token counts from stored requests."
    )
    parser.add_argument("--runs-dir", default="runs", help="Captured runs directory.")
    parser.add_argument(
        "--results-dir", default="results", help="Aggregate results directory."
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Anthropic model whose tokenizer should be used.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="Anthropic API base URL.",
    )
    parser.add_argument(
        "--api-key-env",
        default=DEFAULT_API_KEY_ENV,
        help="Environment variable containing the Anthropic API key.",
    )
    parser.add_argument(
        "--rpm",
        type=float,
        default=DEFAULT_RPM,
        help="Maximum token-count requests per minute.",
    )
    parser.add_argument("--limit", type=int, help="Maximum runs to process.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recount rows that already have anthropic_total_body_tokens.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List selected rows without calling Anthropic or writing files.",
    )
    parser.add_argument(
        "--no-export",
        action="store_true",
        help="Do not refresh results/*.csv after updating benchmark_result.json files.",
    )
    return parser.parse_args()


def exported_run_paths(results_dir: Path, runs_dir: Path) -> list[Path]:
    runs_csv = results_dir / "runs.csv"
    if runs_csv.exists():
        paths: list[Path] = []
        with runs_csv.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("has_primary_request") not in {"True", "true", "1"}:
                    continue
                raw = row.get("run_dir") or ""
                if not raw:
                    continue
                path = Path(raw)
                if not path.is_absolute():
                    path = ROOT / path
                paths.append(path)
        return paths

    if not runs_dir.exists():
        return []
    return [
        path
        for path in sorted(runs_dir.iterdir())
        if path.is_dir() and (path / "benchmark_result.json").exists()
    ]


def _run_row(result: dict[str, Any]) -> dict[str, Any]:
    run = result.get("run") if isinstance(result.get("run"), dict) else {}
    return run


def main() -> int:
    args = parse_args()
    load_dotenv_file()
    export_runs_dir = args.runs_dir
    export_results_dir = args.results_dir
    runs_dir = Path(args.runs_dir)
    if not runs_dir.is_absolute():
        runs_dir = ROOT / runs_dir
    results_dir = Path(args.results_dir)
    if not results_dir.is_absolute():
        results_dir = ROOT / results_dir

    api_key = os.environ.get(args.api_key_env, "")
    if not api_key and not args.dry_run:
        print(
            f"error: {args.api_key_env} is not set; use --dry-run to inspect selection",
            file=sys.stderr,
        )
        return 2

    selected: list[tuple[Path, dict[str, Any], str]] = []
    for run_path in exported_run_paths(results_dir, runs_dir):
        result_path = run_path / "benchmark_result.json"
        if not result_path.exists():
            print(f"skip missing result: {run_path}", file=sys.stderr)
            continue
        result = read_json(result_path)
        run = _run_row(result)
        if not run.get("has_primary_request"):
            continue
        existing = int(run.get("anthropic_total_body_tokens") or 0)
        if existing > 0 and not args.force:
            continue
        record = primary_request_record(run_path, result)
        selected.append((run_path, result, captured_body_text(record)))
        if args.limit and len(selected) >= args.limit:
            break

    print(f"selected {len(selected)} run(s)")
    if args.dry_run:
        for run_path, result, body_text in selected:
            run = _run_row(result)
            print(
                f"dry-run {run.get('agent_id')} {run.get('agent_version')} "
                f"{run_path.name} body_chars={len(body_text)}"
            )
        return 0

    counter = AnthropicTokenCounter(
        api_key=api_key,
        base_url=args.base_url,
        model=args.model,
        rpm=args.rpm,
    )
    updated = 0
    for index, (run_path, result, _body_text) in enumerate(selected, start=1):
        run = _run_row(result)
        label = f"{run.get('agent_id')} {run.get('agent_version')}"
        counted = counter.count_run(run_path, force=args.force)
        if counted.updated:
            updated += 1
        print(f"[{index}/{len(selected)}] {label}: {counted.total_tokens}")

    if updated and not args.no_export:
        manifest = export_benchmark_results(export_runs_dir, export_results_dir)
        print(f"exported {manifest['run_count']} aggregate row(s)")

    print(f"updated {updated} run(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())