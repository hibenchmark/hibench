from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BenchmarkRunInfo:
    run_path: Path
    agent_id: str = ""
    agent_version: str = ""
    run_id: str = ""
    has_primary_request: bool | None = None
    request_count: int = 0
    post_request_count: int = 0
    total_body_tokens: int = 0
    tool_count: int = 0
    started_at: str = ""
    ended_at: str = ""
    process_exit_code: Any = ""
    process_timed_out: Any = ""

    @property
    def agent_version_identity(self) -> tuple[str, str] | None:
        if not self.agent_id or not self.agent_version:
            return None
        return (self.agent_id, self.agent_version)

    @property
    def counts_as_existing_benchmark(self) -> bool:
        return self.has_primary_request is not False

    @property
    def has_primary_benchmark_request(self) -> bool:
        return self.has_primary_request is True

    @property
    def export_identity(self) -> tuple[str, str, str]:
        if self.agent_id and self.agent_version:
            return ("agent_version", self.agent_id, self.agent_version)
        return ("run", self.run_id or self.run_path.name, str(self.run_path))

    @property
    def export_preference_key(self) -> tuple[int, str, str, str, str]:
        return (
            1 if self.has_primary_benchmark_request else 0,
            self.ended_at,
            self.started_at,
            self.run_id or self.run_path.name,
            str(self.run_path),
        )

    def missing_primary_request_error(self) -> str:
        return (
            f"no primary request captured for {self.agent_id} {self.agent_version} "
            f"(request_count={self.request_count}, "
            f"post_request_count={self.post_request_count}, "
            f"process_timed_out={self.process_timed_out}, "
            f"process_exit_code={self.process_exit_code})"
        )


def _read_json_object(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _bool_or_none(value: Any) -> bool | None:
    if value is True:
        return True
    if value is False:
        return False
    return None


def _int_or_zero(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def benchmark_run_info_from_result(
    run_path: str | Path, result: dict[str, Any]
) -> BenchmarkRunInfo:
    path = Path(run_path)
    run = result.get("run") if isinstance(result.get("run"), dict) else {}
    return BenchmarkRunInfo(
        run_path=path,
        agent_id=str(run.get("agent_id") or ""),
        agent_version=str(run.get("agent_version") or ""),
        run_id=str(run.get("run_id") or path.name),
        has_primary_request=_bool_or_none(run.get("has_primary_request")),
        request_count=_int_or_zero(run.get("request_count")),
        post_request_count=_int_or_zero(run.get("post_request_count")),
        total_body_tokens=_int_or_zero(run.get("total_body_tokens")),
        tool_count=_int_or_zero(run.get("tool_count")),
        started_at=str(run.get("started_at") or ""),
        ended_at=str(run.get("ended_at") or ""),
        process_exit_code=run.get("process_exit_code", ""),
        process_timed_out=run.get("process_timed_out", ""),
    )


def benchmark_run_info_from_summary(
    run_path: str | Path,
    *,
    agent_id: str,
    agent_version: str,
    summary: dict[str, Any],
    manifest: dict[str, Any],
) -> BenchmarkRunInfo:
    path = Path(run_path)
    benchmark = (
        summary.get("benchmark") if isinstance(summary.get("benchmark"), dict) else {}
    )
    process = (
        manifest.get("process") if isinstance(manifest.get("process"), dict) else {}
    )
    return BenchmarkRunInfo(
        run_path=path,
        agent_id=agent_id,
        agent_version=agent_version,
        run_id=str(manifest.get("run_id") or path.name),
        has_primary_request=_bool_or_none(benchmark.get("has_primary_request")),
        request_count=_int_or_zero(benchmark.get("request_count")),
        post_request_count=_int_or_zero(benchmark.get("post_request_count")),
        total_body_tokens=_int_or_zero(benchmark.get("total_body_tokens")),
        tool_count=_int_or_zero(benchmark.get("tool_count")),
        started_at=str(manifest.get("started_at") or ""),
        ended_at=str(manifest.get("ended_at") or ""),
        process_exit_code=process.get("exit_code", ""),
        process_timed_out=process.get("timed_out", ""),
    )


def _manifest_identity(manifest: dict[str, Any]) -> tuple[str, str] | None:
    agent = manifest.get("agent") if isinstance(manifest.get("agent"), dict) else {}
    agent_id = agent.get("id")
    version = agent.get("version")
    if not agent_id or not version:
        return None
    return (str(agent_id), str(version))


def load_benchmark_run_info(run_path: str | Path) -> BenchmarkRunInfo:
    path = Path(run_path)
    result_info: BenchmarkRunInfo | None = None
    result_path = path / "benchmark_result.json"
    if result_path.exists():
        result = _read_json_object(result_path)
        if result is not None:
            result_info = benchmark_run_info_from_result(path, result)
            if result_info.agent_version_identity is not None:
                return result_info

    manifest_path = path / "manifest.json"
    if manifest_path.exists():
        manifest = _read_json_object(manifest_path)
        if manifest is not None and (identity := _manifest_identity(manifest)):
            agent_id, agent_version = identity
            return BenchmarkRunInfo(
                run_path=path,
                agent_id=agent_id,
                agent_version=agent_version,
                run_id=(
                    result_info.run_id
                    if result_info is not None
                    else str(manifest.get("run_id") or path.name)
                ),
                has_primary_request=(
                    result_info.has_primary_request if result_info is not None else None
                ),
                request_count=(
                    result_info.request_count if result_info is not None else 0
                ),
                post_request_count=(
                    result_info.post_request_count if result_info is not None else 0
                ),
                total_body_tokens=(
                    result_info.total_body_tokens if result_info is not None else 0
                ),
                tool_count=result_info.tool_count if result_info is not None else 0,
                started_at=str(manifest.get("started_at") or ""),
                ended_at=str(manifest.get("ended_at") or ""),
                process_exit_code=(
                    result_info.process_exit_code if result_info is not None else ""
                ),
                process_timed_out=(
                    result_info.process_timed_out if result_info is not None else ""
                ),
            )

    return result_info or BenchmarkRunInfo(run_path=path, run_id=path.name)


def iter_benchmark_run_infos(
    runs_dir: str | Path, *, require_requests_dir: bool = False
) -> list[BenchmarkRunInfo]:
    runs_path = Path(runs_dir)
    if not runs_path.exists():
        return []
    return [
        load_benchmark_run_info(run_path)
        for run_path in sorted(path for path in runs_path.iterdir() if path.is_dir())
        if not require_requests_dir or (run_path / "requests").is_dir()
    ]
