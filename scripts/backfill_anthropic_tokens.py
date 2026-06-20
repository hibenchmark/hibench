#!/usr/bin/env python3
"""Backfill Anthropic tokenizer totals for captured HiBench runs.

This temporary utility does not rerun agents. It reads each exported run's
stored primary request, sends the exact captured request body text through the
Anthropic Messages token-count endpoint, stores only the returned total on the
run row, and refreshes aggregate CSVs.

Usage:
  ANTHROPIC_API_KEY=... uv run python scripts/backfill_anthropic_tokens.py

The default RPM is intentionally below Anthropic tier-1's documented 100 RPM.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hibench.analyze import compact_json  # noqa: E402
from hibench.benchmark_export import export_benchmark_results  # noqa: E402

ANTHROPIC_COUNT_PATH = "/v1/messages/count_tokens"
DEFAULT_MODEL = "claude-opus-4-8"


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
        default="https://api.anthropic.com",
        help="Anthropic API base URL.",
    )
    parser.add_argument(
        "--api-key-env",
        default="ANTHROPIC_API_KEY",
        help="Environment variable containing the Anthropic API key.",
    )
    parser.add_argument(
        "--rpm",
        type=float,
        default=90.0,
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


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} does not contain a JSON object")
    return data


def primary_request_record(run_path: Path, result: dict[str, Any]) -> dict[str, Any]:
    run = result.get("run") if isinstance(result.get("run"), dict) else {}
    primary_index = int(run.get("primary_request_index") or 0)
    if primary_index <= 0:
        raise ValueError(f"{run_path}: missing primary_request_index")
    request_paths = sorted((run_path / "requests").glob("*.json"))
    try:
        request_path = request_paths[primary_index - 1]
    except IndexError as exc:
        raise ValueError(f"{run_path}: primary request file is missing") from exc
    return read_json(request_path)


def captured_body_text(record: dict[str, Any]) -> str:
    body_text = record.get("body_text")
    if isinstance(body_text, str) and body_text:
        return body_text
    body = record.get("json")
    if isinstance(body, str):
        return body
    return compact_json(body)


def count_tokens_payload(body_text: str, model: str) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": body_text,
            }
        ],
    }


class RateLimiter:
    def __init__(self, rpm: float) -> None:
        self.interval = 60.0 / rpm if rpm > 0 else 0.0
        self.next_at = 0.0

    def wait(self) -> None:
        if self.interval <= 0:
            return
        now = time.monotonic()
        if self.next_at > now:
            time.sleep(self.next_at - now)
        self.next_at = max(now, self.next_at) + self.interval


def retry_after_seconds(error: HTTPError) -> float | None:
    header = error.headers.get("retry-after")
    if not header:
        return None
    try:
        return max(0.0, float(header))
    except ValueError:
        return None


def anthropic_count_tokens(
    *,
    api_key: str,
    base_url: str,
    model: str,
    body_text: str,
    limiter: RateLimiter,
    max_retries: int = 5,
) -> int:
    url = base_url.rstrip("/") + ANTHROPIC_COUNT_PATH
    data = json.dumps(
        count_tokens_payload(body_text, model), ensure_ascii=False
    ).encode("utf-8")
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    for attempt in range(max_retries + 1):
        limiter.wait()
        request = Request(url, data=data, headers=headers, method="POST")
        try:
            with urlopen(request, timeout=120) as response:
                result = json.loads(response.read().decode("utf-8"))
            tokens = result.get("input_tokens")
            if not isinstance(tokens, int):
                raise ValueError(f"Anthropic response missing input_tokens: {result}")
            return tokens
        except HTTPError as error:
            retryable = error.code == 429 or 500 <= error.code < 600
            if not retryable or attempt >= max_retries:
                detail = error.read().decode("utf-8", errors="replace")
                raise RuntimeError(
                    f"Anthropic token count failed with HTTP {error.code}: {detail}"
                ) from error
            delay = retry_after_seconds(error) or min(60.0, 2.0**attempt)
            time.sleep(delay)
        except URLError as error:
            if attempt >= max_retries:
                raise RuntimeError(f"Anthropic token count failed: {error}") from error
            time.sleep(min(60.0, 2.0**attempt))

    raise RuntimeError("unreachable Anthropic retry state")


def write_result(path: Path, result: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def main() -> int:
    args = parse_args()
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

    selected: list[tuple[Path, Path, dict[str, Any], str]] = []
    for run_path in exported_run_paths(results_dir, runs_dir):
        result_path = run_path / "benchmark_result.json"
        if not result_path.exists():
            print(f"skip missing result: {run_path}", file=sys.stderr)
            continue
        result = read_json(result_path)
        run = result.get("run") if isinstance(result.get("run"), dict) else {}
        if not run.get("has_primary_request"):
            continue
        existing = int(run.get("anthropic_total_body_tokens") or 0)
        if existing > 0 and not args.force:
            continue
        record = primary_request_record(run_path, result)
        selected.append((run_path, result_path, result, captured_body_text(record)))
        if args.limit and len(selected) >= args.limit:
            break

    print(f"selected {len(selected)} run(s)")
    if args.dry_run:
        for run_path, _result_path, result, body_text in selected:
            run = result["run"]
            print(
                f"dry-run {run.get('agent_id')} {run.get('agent_version')} "
                f"{run_path.name} body_chars={len(body_text)}"
            )
        return 0

    limiter = RateLimiter(args.rpm)
    updated = 0
    for index, (run_path, result_path, result, body_text) in enumerate(
        selected, start=1
    ):
        run = result["run"]
        label = f"{run.get('agent_id')} {run.get('agent_version')}"
        tokens = anthropic_count_tokens(
            api_key=api_key,
            base_url=args.base_url,
            model=args.model,
            body_text=body_text,
            limiter=limiter,
        )
        run["anthropic_tokenizer_model"] = args.model
        run["anthropic_total_body_tokens"] = tokens
        write_result(result_path, result)
        updated += 1
        print(f"[{index}/{len(selected)}] {label}: {tokens}")

    if updated and not args.no_export:
        manifest = export_benchmark_results(export_runs_dir, export_results_dir)
        print(f"exported {manifest['run_count']} aggregate row(s)")

    print(f"updated {updated} run(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())