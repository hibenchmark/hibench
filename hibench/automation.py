from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any

from .agents import list_agent_ids, load_agent
from .anthropic_tokens import (
    anthropic_token_counter_from_env,
    anthropic_tokenizer_settings_from_env,
)
from .benchmark_artifacts import write_run_artifacts
from .benchmark_export import export_benchmark_results
from .benchmark_runs import (
    BenchmarkRunInfo,
    benchmark_run_info_from_summary,
    iter_benchmark_run_infos,
)
from .runner import RunResult, ensure_docker_available, purge_docker_image, run_agent
from .versioning import (
    VersionCatalog,
    fetch_and_store_agent_versions,
    load_version_catalog,
    select_versions,
    version_catalog_path,
)


SAFE_PART_RE = re.compile(r"[^A-Za-z0-9_.-]+")
DEFAULT_INITIAL_AGENT_VERSION_LIMIT = 100


@dataclass(frozen=True)
class VersionSelection:
    versions: list[str]
    existing_versions: list[str]
    skipped_existing_versions: list[str]
    initial_limit: int | None
    initial_limit_applied: bool
    available_version_count: int
    candidate_version_count: int

    @property
    def has_existing_agent_benchmarks(self) -> bool:
        return bool(self.existing_versions)


@dataclass(frozen=True)
class VersionBenchmarkResult:
    agent_id: str
    version: str
    status: str
    run_id: str
    run_dir: str
    replaced_run_dirs: list[str]
    has_primary_request: bool | None = None
    total_body_tokens: int | None = None
    tool_count: int | None = None
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "version": self.version,
            "status": self.status,
            "run_id": self.run_id,
            "run_dir": self.run_dir,
            "replaced_run_dirs": self.replaced_run_dirs,
            "has_primary_request": self.has_primary_request,
            "total_body_tokens": self.total_body_tokens,
            "tool_count": self.tool_count,
            "error": self.error,
        }


class DockerUnavailableError(RuntimeError):
    """Raised when a non-dry-run benchmark batch needs Docker but cannot find it."""


@dataclass(frozen=True)
class BenchmarkBatchResult:
    agent_id: str
    catalog: VersionCatalog
    catalog_path: Path
    available_version_count: int
    selected_versions: list[str]
    selection: VersionSelection
    results: list[VersionBenchmarkResult]
    manifest: dict[str, Any]
    manifest_path: Path
    export_manifest: dict[str, Any] | None
    aggregate_refresh_count: int

    @property
    def has_errors(self) -> bool:
        return any(result.status == "error" for result in self.results)


@dataclass(frozen=True)
class AllBenchmarkBatchResult:
    agent_ids: list[str]
    batches: list[BenchmarkBatchResult]
    manifest: dict[str, Any]
    manifest_path: Path

    @property
    def has_errors(self) -> bool:
        return any(batch.has_errors for batch in self.batches)


@dataclass(frozen=True)
class BenchmarkAgentProgress:
    agent_id: str
    agent_index: int
    agent_count: int
    event: str
    batch: BenchmarkBatchResult | None = None


def safe_path_part(value: str) -> str:
    sanitized = SAFE_PART_RE.sub("-", value.strip()).strip("-")
    return sanitized or "unknown"


def canonical_run_id(agent_id: str, version: str, prompt_path: str | Path) -> str:
    prompt_name = safe_path_part(Path(prompt_path).stem)
    return f"{safe_path_part(agent_id)}-{safe_path_part(version)}-{prompt_name}"


def _run_infos_for_agent_version(
    runs_dir: str | Path, agent_id: str, version: str
) -> list[BenchmarkRunInfo]:
    return [
        info
        for info in iter_benchmark_run_infos(runs_dir)
        if info.agent_version_identity == (agent_id, version)
    ]


def existing_run_dirs_for_agent_version(
    runs_dir: str | Path, agent_id: str, version: str
) -> list[Path]:
    return [
        info.run_path
        for info in _run_infos_for_agent_version(runs_dir, agent_id, version)
        if info.counts_as_existing_benchmark
    ]


def existing_versions_for_agent(runs_dir: str | Path, agent_id: str) -> list[str]:
    versions: list[str] = []
    seen: set[str] = set()
    for info in iter_benchmark_run_infos(runs_dir):
        identity = info.agent_version_identity
        if identity is None or not info.counts_as_existing_benchmark:
            continue
        run_agent_id, version = identity
        if run_agent_id != agent_id or version in seen:
            continue
        seen.add(version)
        versions.append(version)
    return versions


def _path_key(path: Path) -> str:
    return str(path.resolve(strict=False))


def _unique_paths(paths: list[Path]) -> list[Path]:
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = _path_key(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def select_agent_benchmark_versions(
    available_versions: list[str],
    agent_id: str,
    runs_dir: str | Path,
    requested_versions: list[str] | None = None,
    max_versions: int | None = None,
    initial_version_limit: int | None = DEFAULT_INITIAL_AGENT_VERSION_LIMIT,
    include_existing: bool = False,
) -> VersionSelection:
    existing_versions = existing_versions_for_agent(runs_dir, agent_id)
    candidates = list(available_versions)
    initial_limit_applied = False
    skipped_existing_versions: list[str] = []

    if requested_versions:
        selected = select_versions(
            candidates, requested_versions=requested_versions, max_versions=max_versions
        )
    else:
        if initial_version_limit and initial_version_limit > 0:
            initial_limit_applied = len(candidates) > initial_version_limit
            candidates = candidates[-initial_version_limit:]
        if not include_existing:
            existing = set(existing_versions)
            skipped_existing_versions = [
                version for version in candidates if version in existing
            ]
            candidates = [version for version in candidates if version not in existing]
        selected = select_versions(candidates, max_versions=max_versions)

    return VersionSelection(
        versions=selected,
        existing_versions=existing_versions,
        skipped_existing_versions=skipped_existing_versions,
        initial_limit=initial_version_limit,
        initial_limit_applied=initial_limit_applied,
        available_version_count=len(available_versions),
        candidate_version_count=len(candidates),
    )


def _empty_temp_path(parent: Path, prefix: str) -> Path:
    path = Path(tempfile.mkdtemp(prefix=prefix, dir=parent))
    path.rmdir()
    return path


def _same_path(left: Path, right: Path) -> bool:
    return _path_key(left) == _path_key(right)


def _move_staged_result(
    staged: RunResult, target_run_dir: Path, replacement_paths: list[Path]
) -> dict[str, Any]:
    target_run_dir.parent.mkdir(parents=True, exist_ok=True)
    staged_install_dir = _empty_temp_path(
        target_run_dir.parent, f".{target_run_dir.name}.staged-"
    )
    shutil.move(str(staged.run_dir), str(staged_install_dir))

    backup_dir: Path | None = None
    if target_run_dir.exists():
        backup_dir = _empty_temp_path(
            target_run_dir.parent, f".{target_run_dir.name}.backup-"
        )
        target_run_dir.rename(backup_dir)

    try:
        staged_install_dir.rename(target_run_dir)
    except Exception:
        if backup_dir is not None and backup_dir.exists():
            backup_dir.rename(target_run_dir)
        if staged_install_dir.exists():
            shutil.rmtree(staged_install_dir)
        raise

    try:
        summary = write_run_artifacts(target_run_dir)
    except Exception:
        failed_dir: Path | None = None
        if target_run_dir.exists():
            failed_dir = _empty_temp_path(
                target_run_dir.parent, f".{target_run_dir.name}.failed-"
            )
            target_run_dir.rename(failed_dir)
        if backup_dir is not None and backup_dir.exists():
            backup_dir.rename(target_run_dir)
        if failed_dir is not None and failed_dir.exists():
            shutil.rmtree(failed_dir, ignore_errors=True)
        raise

    if backup_dir is not None and backup_dir.exists():
        shutil.rmtree(backup_dir)
    for run_path in replacement_paths:
        if _same_path(run_path, target_run_dir):
            continue
        if run_path.exists():
            shutil.rmtree(run_path)
    return summary


def _missing_primary_request_error(
    staged: RunResult, agent_id: str, version: str
) -> str | None:
    run_info = benchmark_run_info_from_summary(
        staged.run_dir,
        agent_id=agent_id,
        agent_version=version,
        summary=staged.summary,
        manifest=staged.manifest,
    )
    if run_info.has_primary_benchmark_request:
        return None
    return run_info.missing_primary_request_error()


def run_version_benchmark(
    agent_id: str,
    version: str,
    prompt_path: str | Path,
    out_dir: str | Path = "runs",
    timeout: int = 30,
    build: bool = True,
    dry_run: bool = False,
    skip_existing: bool = False,
) -> VersionBenchmarkResult:
    run_id = canonical_run_id(agent_id, version, prompt_path)
    target_run_dir = Path(out_dir) / run_id
    existing_infos = _run_infos_for_agent_version(out_dir, agent_id, version)
    existing_benchmarks = [
        info for info in existing_infos if info.counts_as_existing_benchmark
    ]
    existing = [info.run_path for info in existing_infos]
    path_conflicts = (
        [target_run_dir]
        if target_run_dir.exists()
        and not any(_same_path(path, target_run_dir) for path in existing)
        else []
    )
    replacement_paths = _unique_paths([*existing, *path_conflicts])
    replaced = [str(path) for path in replacement_paths]

    if skip_existing and existing_benchmarks:
        return VersionBenchmarkResult(
            agent_id=agent_id,
            version=version,
            status="skipped",
            run_id=run_id,
            run_dir=str(existing_benchmarks[0].run_path),
            replaced_run_dirs=[],
        )

    if dry_run:
        return VersionBenchmarkResult(
            agent_id=agent_id,
            version=version,
            status="planned",
            run_id=run_id,
            run_dir=str(target_run_dir),
            replaced_run_dirs=replaced,
        )

    image_to_purge = load_agent(agent_id, version=version).image if build else None
    try:
        with tempfile.TemporaryDirectory(prefix="hibench-version-run-") as staged_out:
            staged = run_agent(
                agent_id=agent_id,
                version=version,
                prompt_path=prompt_path,
                out_dir=staged_out,
                timeout=timeout,
                build=build,
                run_id=run_id,
                replace=True,
            )
            if error := _missing_primary_request_error(staged, agent_id, version):
                raise RuntimeError(error)
            summary = _move_staged_result(staged, target_run_dir, replacement_paths)
    finally:
        if image_to_purge:
            purge_docker_image(image_to_purge)

    run_info = benchmark_run_info_from_summary(
        target_run_dir,
        agent_id=agent_id,
        agent_version=version,
        summary=summary,
        manifest={},
    )
    return VersionBenchmarkResult(
        agent_id=agent_id,
        version=version,
        status="replaced" if replaced else "created",
        run_id=run_id,
        run_dir=str(target_run_dir),
        replaced_run_dirs=replaced,
        has_primary_request=run_info.has_primary_benchmark_request,
        total_body_tokens=run_info.total_body_tokens,
        tool_count=run_info.tool_count,
    )


def run_version_benchmarks(
    agent_id: str,
    versions: list[str],
    prompt_path: str | Path,
    out_dir: str | Path = "runs",
    timeout: int = 30,
    build: bool = True,
    dry_run: bool = False,
    skip_existing: bool = False,
    stop_on_error: bool = False,
    after_each: Callable[[VersionBenchmarkResult], None] | None = None,
) -> list[VersionBenchmarkResult]:
    results: list[VersionBenchmarkResult] = []
    for version in versions:
        try:
            result = run_version_benchmark(
                agent_id=agent_id,
                version=version,
                prompt_path=prompt_path,
                out_dir=out_dir,
                timeout=timeout,
                build=build,
                dry_run=dry_run,
                skip_existing=skip_existing,
            )
        except Exception as exc:
            if stop_on_error:
                raise
            run_id = canonical_run_id(agent_id, version, prompt_path)
            result = VersionBenchmarkResult(
                agent_id=agent_id,
                version=version,
                status="error",
                run_id=run_id,
                run_dir=str(Path(out_dir) / run_id),
                replaced_run_dirs=[],
                error=str(exc),
            )
        results.append(result)
        if after_each is not None:
            after_each(result)
    return results


def load_or_fetch_version_catalog(
    agent_id: str,
    versions_dir: str | Path = "agent_versions",
    versions_timeout: int = 60,
    use_local_versions: bool = False,
) -> tuple[VersionCatalog, Path]:
    if use_local_versions:
        catalog = load_version_catalog(agent_id, storage_dir=versions_dir)
        return catalog, version_catalog_path(agent_id, versions_dir)
    return fetch_and_store_agent_versions(
        agent_id,
        storage_dir=versions_dir,
        timeout=versions_timeout,
    )


def build_benchmark_batch_manifest(
    *,
    agent_id: str,
    catalog: VersionCatalog,
    catalog_path: Path,
    selection: VersionSelection,
    selected_versions: list[str],
    requested_versions: list[str] | None,
    prompt_path: str | Path,
    out_dir: str | Path,
    results_out: str | Path,
    dry_run: bool,
    build: bool,
    skip_existing: bool,
    rerun_existing: bool,
    export_results: bool,
    anthropic_tokenizer: dict[str, Any],
    results: list[VersionBenchmarkResult],
) -> dict[str, Any]:
    return {
        "schema_version": "hibench.benchmark_batch.v1",
        "agent_id": agent_id,
        "catalog_path": str(catalog_path),
        "version_count": len(catalog.versions),
        "benchmark_version_policy_id": catalog.benchmark_version_policy_id,
        "benchmark_version_policy": catalog.benchmark_version_policy,
        "benchmark_min_version": catalog.benchmark_min_version,
        "benchmark_version_count": len(catalog.benchmark_versions),
        "benchmark_exclusion_count": len(catalog.excluded_benchmark_versions),
        "excluded_benchmark_versions": catalog.excluded_benchmark_versions,
        "selected_version_count": len(selected_versions),
        "requested_versions": requested_versions or [],
        "existing_agent_benchmark_version_count": len(selection.existing_versions),
        "skipped_existing_version_count": len(selection.skipped_existing_versions),
        "candidate_version_count": selection.candidate_version_count,
        "initial_version_limit": selection.initial_limit,
        "initial_version_limit_applied": selection.initial_limit_applied,
        "prompt_file": str(prompt_path),
        "out_dir": str(out_dir),
        "results_out": str(results_out),
        "dry_run": dry_run,
        "build": build,
        "skip_existing": skip_existing,
        "rerun_existing": rerun_existing,
        "export_results": export_results,
        "anthropic_tokenizer": anthropic_tokenizer,
        "results": [result.to_dict() for result in results],
    }


def run_benchmark_batch(
    *,
    agent_id: str,
    prompt_path: str | Path = "prompts/hi.txt",
    out_dir: str | Path = "runs",
    timeout: int = 30,
    versions_dir: str | Path = "agent_versions",
    versions_timeout: int = 60,
    use_local_versions: bool = False,
    requested_versions: list[str] | None = None,
    max_versions: int | None = None,
    initial_version_limit: int | None = DEFAULT_INITIAL_AGENT_VERSION_LIMIT,
    include_platform_versions: bool = False,
    build: bool = True,
    dry_run: bool = False,
    skip_existing: bool = False,
    rerun_existing: bool = False,
    stop_on_error: bool = False,
    results_out: str | Path = "results",
    export_results: bool = True,
    manifest_name: str = "benchmark_batch.json",
) -> BenchmarkBatchResult:
    if not dry_run and not ensure_docker_available():
        raise DockerUnavailableError("docker executable not found")

    catalog, catalog_path = load_or_fetch_version_catalog(
        agent_id,
        versions_dir=versions_dir,
        versions_timeout=versions_timeout,
        use_local_versions=use_local_versions,
    )
    available_versions = (
        catalog.versions
        if include_platform_versions or requested_versions
        else catalog.benchmark_versions
    )
    selection = select_agent_benchmark_versions(
        available_versions,
        agent_id=agent_id,
        runs_dir=out_dir,
        requested_versions=requested_versions,
        max_versions=max_versions,
        initial_version_limit=initial_version_limit,
        include_existing=rerun_existing,
    )
    selected_versions = selection.versions
    should_export = export_results and not dry_run
    anthropic_settings = anthropic_tokenizer_settings_from_env()
    anthropic_counter = (
        anthropic_token_counter_from_env()
        if not dry_run and anthropic_settings["enabled"]
        else None
    )
    anthropic_counted_run_count = 0
    anthropic_errors: list[dict[str, str]] = []
    export_manifest = None
    completed_run_export_count = 0

    def after_completed_run(result: VersionBenchmarkResult) -> None:
        nonlocal anthropic_counted_run_count, completed_run_export_count, export_manifest
        if result.status not in {"created", "replaced"}:
            return
        if anthropic_counter is not None:
            try:
                counted = anthropic_counter.count_run(result.run_dir)
                if counted.updated:
                    anthropic_counted_run_count += 1
            except Exception as exc:
                anthropic_errors.append(
                    {
                        "agent_id": result.agent_id,
                        "version": result.version,
                        "run_dir": result.run_dir,
                        "error": str(exc),
                    }
                )
        if should_export:
            export_manifest = export_benchmark_results(out_dir, results_out)
            completed_run_export_count += 1

    results = run_version_benchmarks(
        agent_id=agent_id,
        versions=selected_versions,
        prompt_path=prompt_path,
        out_dir=out_dir,
        timeout=timeout,
        build=build,
        dry_run=dry_run,
        skip_existing=skip_existing,
        stop_on_error=stop_on_error,
        after_each=(
            after_completed_run if should_export or anthropic_counter is not None else None
        ),
    )
    anthropic_tokenizer = {
        "enabled": bool(anthropic_counter),
        "api_key_env": anthropic_settings["api_key_env"],
        "model": anthropic_settings["model"],
        "base_url": anthropic_settings["base_url"],
        "rpm": anthropic_settings["rpm"],
        "dotenv_path": anthropic_settings.get("dotenv_path", ""),
        "disabled_reason": (
            "dry run" if dry_run else anthropic_settings["disabled_reason"]
        ),
        "counted_run_count": anthropic_counted_run_count,
        "error_count": len(anthropic_errors),
        "errors": anthropic_errors,
    }

    manifest = build_benchmark_batch_manifest(
        agent_id=agent_id,
        catalog=catalog,
        catalog_path=catalog_path,
        selection=selection,
        selected_versions=selected_versions,
        requested_versions=requested_versions,
        prompt_path=prompt_path,
        out_dir=out_dir,
        results_out=results_out,
        dry_run=dry_run,
        build=build,
        skip_existing=skip_existing,
        rerun_existing=rerun_existing,
        export_results=should_export,
        anthropic_tokenizer=anthropic_tokenizer,
        results=results,
    )
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    manifest_path = out_path / manifest_name
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if should_export and completed_run_export_count == 0:
        export_manifest = export_benchmark_results(out_dir, results_out)

    return BenchmarkBatchResult(
        agent_id=agent_id,
        catalog=catalog,
        catalog_path=catalog_path,
        available_version_count=len(available_versions),
        selected_versions=selected_versions,
        selection=selection,
        results=results,
        manifest=manifest,
        manifest_path=manifest_path,
        export_manifest=export_manifest,
        aggregate_refresh_count=completed_run_export_count,
    )


def build_benchmark_batches_manifest(
    *,
    agent_ids: list[str],
    batches: list[BenchmarkBatchResult],
    requested_versions: list[str] | None,
    prompt_path: str | Path,
    out_dir: str | Path,
    results_out: str | Path,
    dry_run: bool,
    build: bool,
    skip_existing: bool,
    rerun_existing: bool,
    export_results: bool,
) -> dict[str, Any]:
    return {
        "schema_version": "hibench.benchmark_batches.v1",
        "agent_ids": agent_ids,
        "agent_count": len(agent_ids),
        "completed_agent_count": len(batches),
        "has_errors": any(batch.has_errors for batch in batches),
        "requested_versions": requested_versions or [],
        "prompt_file": str(prompt_path),
        "out_dir": str(out_dir),
        "results_out": str(results_out),
        "dry_run": dry_run,
        "build": build,
        "skip_existing": skip_existing,
        "rerun_existing": rerun_existing,
        "export_results": export_results,
        "batches": [
            {
                "agent_id": batch.agent_id,
                "has_errors": batch.has_errors,
                "selected_version_count": len(batch.selected_versions),
                "batch_manifest": str(batch.manifest_path),
                "aggregate_refresh_count": batch.aggregate_refresh_count,
                "manifest": batch.manifest,
            }
            for batch in batches
        ],
    }


def run_benchmark_batches(
    *,
    agent_ids: list[str] | None = None,
    prompt_path: str | Path = "prompts/hi.txt",
    out_dir: str | Path = "runs",
    timeout: int = 30,
    versions_dir: str | Path = "agent_versions",
    versions_timeout: int = 60,
    use_local_versions: bool = False,
    requested_versions: list[str] | None = None,
    max_versions: int | None = None,
    initial_version_limit: int | None = DEFAULT_INITIAL_AGENT_VERSION_LIMIT,
    include_platform_versions: bool = False,
    build: bool = True,
    dry_run: bool = False,
    skip_existing: bool = False,
    rerun_existing: bool = False,
    stop_on_error: bool = False,
    results_out: str | Path = "results",
    export_results: bool = True,
    manifest_name: str = "benchmark_batches.json",
    on_agent_progress: Callable[[BenchmarkAgentProgress], None] | None = None,
) -> AllBenchmarkBatchResult:
    if requested_versions:
        raise ValueError(
            "run_benchmark_batches does not support requested_versions; "
            "target a specific agent instead"
        )

    selected_agent_ids = list(agent_ids) if agent_ids is not None else list_agent_ids()
    should_export = export_results and not dry_run
    batches: list[BenchmarkBatchResult] = []
    agent_count = len(selected_agent_ids)
    for agent_index, agent_id in enumerate(selected_agent_ids, start=1):
        if on_agent_progress is not None:
            on_agent_progress(
                BenchmarkAgentProgress(
                    agent_id=agent_id,
                    agent_index=agent_index,
                    agent_count=agent_count,
                    event="started",
                )
            )
        batch = run_benchmark_batch(
            agent_id=agent_id,
            prompt_path=prompt_path,
            out_dir=out_dir,
            timeout=timeout,
            versions_dir=versions_dir,
            versions_timeout=versions_timeout,
            use_local_versions=use_local_versions,
            requested_versions=None,
            max_versions=max_versions,
            initial_version_limit=initial_version_limit,
            include_platform_versions=include_platform_versions,
            build=build,
            dry_run=dry_run,
            skip_existing=skip_existing,
            rerun_existing=rerun_existing,
            stop_on_error=stop_on_error,
            results_out=results_out,
            export_results=export_results,
            manifest_name=f"benchmark_batch-{safe_path_part(agent_id)}.json",
        )
        batches.append(batch)
        if on_agent_progress is not None:
            on_agent_progress(
                BenchmarkAgentProgress(
                    agent_id=agent_id,
                    agent_index=agent_index,
                    agent_count=agent_count,
                    event="completed",
                    batch=batch,
                )
            )

    manifest = build_benchmark_batches_manifest(
        agent_ids=selected_agent_ids,
        batches=batches,
        requested_versions=requested_versions,
        prompt_path=prompt_path,
        out_dir=out_dir,
        results_out=results_out,
        dry_run=dry_run,
        build=build,
        skip_existing=skip_existing,
        rerun_existing=rerun_existing,
        export_results=should_export,
    )
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    manifest_path = out_path / manifest_name
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return AllBenchmarkBatchResult(
        agent_ids=selected_agent_ids,
        batches=batches,
        manifest=manifest,
        manifest_path=manifest_path,
    )


def format_benchmark_batch_report(batch: BenchmarkBatchResult) -> str:
    lines = [
        "HiBench automated benchmark",
        "===========================",
        f"agent_id: {batch.agent_id}",
        f"catalog_path: {batch.catalog_path}",
        f"available_versions: {batch.available_version_count}",
        f"stored_versions: {len(batch.catalog.versions)}",
        f"benchmark_version_policy: {batch.catalog.benchmark_version_policy}",
    ]
    if batch.catalog.benchmark_min_version:
        lines.append(f"benchmark_min_version: {batch.catalog.benchmark_min_version}")
    lines.extend(
        [
            f"benchmark_exclusions: {len(batch.catalog.excluded_benchmark_versions)}",
            (
                "existing_agent_benchmark_versions: "
                f"{len(batch.selection.existing_versions)}"
            ),
            (
                "skipped_existing_versions: "
                f"{len(batch.selection.skipped_existing_versions)}"
            ),
            f"candidate_versions_after_skip: {batch.selection.candidate_version_count}",
        ]
    )
    if batch.selection.initial_limit and batch.selection.initial_limit > 0:
        state = "applied" if batch.selection.initial_limit_applied else "not needed"
        lines.append(
            f"version_window: latest {batch.selection.initial_limit} versions ({state})"
        )
    else:
        lines.append("version_window: disabled")

    if batch.manifest["requested_versions"] or batch.manifest["rerun_existing"]:
        mode = (
            "skip existing"
            if batch.manifest["skip_existing"]
            else "replace selected existing"
        )
    else:
        mode = "missing versions only"

    lines.extend(
        [
            f"selected_versions: {len(batch.selected_versions)}",
            f"out_dir: {batch.manifest['out_dir']}",
            f"build: {str(batch.manifest['build']).lower()}",
            f"dry_run: {str(batch.manifest['dry_run']).lower()}",
            f"mode: {mode}",
            f"aggregate_export: {str(batch.manifest['export_results']).lower()}",
            "",
        ]
    )
    anthropic_tokenizer = batch.manifest.get("anthropic_tokenizer") or {}
    if anthropic_tokenizer:
        status = "enabled" if anthropic_tokenizer.get("enabled") else "disabled"
        reason = anthropic_tokenizer.get("disabled_reason") or ""
        suffix = f" ({reason})" if reason and status == "disabled" else ""
        lines.extend(
            [
                (
                    "anthropic_tokenizer: "
                    f"{status}{suffix} "
                    f"model={anthropic_tokenizer.get('model', '')} "
                    f"counted={anthropic_tokenizer.get('counted_run_count', 0)} "
                    f"errors={anthropic_tokenizer.get('error_count', 0)}"
                ),
                "",
            ]
        )
    for result in batch.results:
        suffix = ""
        if result.error:
            suffix = f" error={result.error}"
        elif result.status in {"created", "replaced"}:
            suffix = (
                f" tokens={result.total_body_tokens} tools={result.tool_count} "
                f"primary={result.has_primary_request}"
            )
        lines.append(f"- {result.version}: {result.status} -> {result.run_dir}{suffix}")

    lines.extend(["", f"batch_manifest: {batch.manifest_path}"])
    if batch.export_manifest:
        aggregate_refreshes = max(batch.aggregate_refresh_count, 1)
        lines.extend(
            [
                f"aggregate_results: {batch.manifest['results_out']}",
                f"aggregate_refreshes: {aggregate_refreshes}",
                (
                    "aggregate_runs: "
                    f"{batch.export_manifest['run_count']} unique agent/version rows"
                ),
                (
                    "aggregate_deduplicated_runs: "
                    f"{batch.export_manifest['deduplicated_run_count']}"
                ),
                f"aggregate_manifest: {Path(batch.manifest['results_out']) / 'export.json'}",
            ]
        )
    return "\n".join(lines)


def format_benchmark_batches_report(result: AllBenchmarkBatchResult) -> str:
    sections = [
        "\n".join(
            [
                "HiBench all-agent benchmark",
                "===========================",
                f"agents: {len(result.agent_ids)}",
                f"completed_agents: {len(result.batches)}",
                f"has_errors: {str(result.has_errors).lower()}",
            ]
        )
    ]
    sections.extend(format_benchmark_batch_report(batch) for batch in result.batches)
    sections.append(f"all_batch_manifest: {result.manifest_path}")
    return "\n\n".join(sections)
