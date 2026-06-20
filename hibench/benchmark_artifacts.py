from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .analyze import build_run_summary
from .benchmark_io import write_benchmark_result
from .benchmark_schema import build_benchmark_result
from .parsers import parser_id_for_agent

ANTHROPIC_RESULT_FIELDS = (
    "anthropic_tokenizer_model",
    "anthropic_total_body_tokens",
)


def load_manifest(run_path: Path) -> dict[str, Any]:
    manifest_path = run_path / "manifest.json"
    if not manifest_path.exists():
        return {}
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def parser_id_from_manifest(manifest: dict[str, Any]) -> str | None:
    agent = manifest.get("agent") if isinstance(manifest.get("agent"), dict) else {}
    parser_id = agent.get("parser_id") or manifest.get("parser_id")
    if parser_id:
        return str(parser_id)
    agent_id = agent.get("id")
    return parser_id_for_agent(str(agent_id) if agent_id else None)


def existing_anthropic_result_fields(run_path: Path) -> dict[str, Any]:
    result_path = run_path / "benchmark_result.json"
    if not result_path.exists():
        return {}
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    run = result.get("run") if isinstance(result.get("run"), dict) else {}
    try:
        total_tokens = int(run.get("anthropic_total_body_tokens") or 0)
    except (TypeError, ValueError):
        return {}
    if total_tokens <= 0:
        return {}
    return {
        "anthropic_tokenizer_model": str(run.get("anthropic_tokenizer_model") or ""),
        "anthropic_total_body_tokens": total_tokens,
    }


def preserve_anthropic_result_fields(
    benchmark_result: dict[str, Any], existing_fields: dict[str, Any]
) -> None:
    if not existing_fields:
        return
    run = (
        benchmark_result.get("run")
        if isinstance(benchmark_result.get("run"), dict)
        else {}
    )
    try:
        current_total = int(run.get("anthropic_total_body_tokens") or 0)
    except (TypeError, ValueError):
        current_total = 0
    if current_total > 0:
        return
    for field in ANTHROPIC_RESULT_FIELDS:
        run[field] = existing_fields[field]


def write_run_artifacts(run_dir: str | Path) -> dict[str, Any]:
    run_path = Path(run_dir)
    manifest = load_manifest(run_path)
    existing_anthropic_fields = existing_anthropic_result_fields(run_path)
    summary = build_run_summary(run_path, parser_id=parser_id_from_manifest(manifest))
    benchmark_result = build_benchmark_result(run_path, manifest, summary)
    preserve_anthropic_result_fields(benchmark_result, existing_anthropic_fields)
    summary["benchmark"] = benchmark_result["run"]
    (run_path / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    write_benchmark_result(run_path, benchmark_result)
    return summary
