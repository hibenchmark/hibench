from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .analyze import build_run_summary
from .benchmark_io import write_benchmark_result
from .benchmark_schema import build_benchmark_result
from .parsers import parser_id_for_agent


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


def write_run_artifacts(run_dir: str | Path) -> dict[str, Any]:
    run_path = Path(run_dir)
    manifest = load_manifest(run_path)
    summary = build_run_summary(run_path, parser_id=parser_id_from_manifest(manifest))
    benchmark_result = build_benchmark_result(run_path, manifest, summary)
    summary["benchmark"] = benchmark_result["run"]
    (run_path / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    write_benchmark_result(run_path, benchmark_result)
    return summary
