from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rich.console import Console

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hibench.agents import list_agent_ids, load_agent
from hibench.anthropic_tokens import anthropic_token_counter_from_env
from hibench.automation import (
    DEFAULT_INITIAL_AGENT_VERSION_LIMIT,
    DockerUnavailableError,
    run_benchmark_batch,
    run_benchmark_batches,
)
from hibench.benchmark import (
    export_benchmark_results,
    format_benchmark_report,
    write_run_artifacts,
)
from hibench.rich_report import (
    BenchmarkAllProgress,
    print_benchmark_batch_report,
    print_benchmark_batches_report,
)
from hibench.runner import build_image, ensure_docker_available, run_agent
from hibench.versioning import (
    fetch_and_store_agent_versions,
    load_version_catalog,
    version_catalog_path,
)


def cmd_agents(_args: argparse.Namespace) -> int:
    for agent_id in list_agent_ids():
        spec = load_agent(agent_id)
        print(f"{spec.id}\t{spec.display_name}\t{spec.version}\t{spec.image}")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    if not ensure_docker_available():
        print("docker executable not found", file=sys.stderr)
        return 127
    spec = load_agent(args.agent, version=args.version)
    build_image(spec, image=args.image)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    if not ensure_docker_available():
        print("docker executable not found", file=sys.stderr)
        return 127
    result = run_agent(
        agent_id=args.agent,
        prompt_path=args.prompt,
        out_dir=args.out,
        timeout=args.timeout,
        image=args.image,
        build=args.build,
        version=args.version,
        run_id=args.run_id,
        replace=args.replace,
    )
    summary = result.summary
    counter = anthropic_token_counter_from_env()
    if counter is not None:
        try:
            counter.count_run(result.run_dir)
            summary_path = Path(result.run_dir) / "summary.json"
            if summary_path.exists():
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"warning: Anthropic token count failed: {exc}", file=sys.stderr)
    print(format_benchmark_report(result.run_dir, summary))
    return 0


def cmd_versions(args: argparse.Namespace) -> int:
    if args.refresh:
        catalog, path = fetch_and_store_agent_versions(
            args.agent,
            storage_dir=args.versions_dir,
            timeout=args.versions_timeout,
        )
    else:
        path = version_catalog_path(args.agent, args.versions_dir)
        if path.exists():
            catalog = load_version_catalog(args.agent, storage_dir=args.versions_dir)
        else:
            catalog, path = fetch_and_store_agent_versions(
                args.agent,
                storage_dir=args.versions_dir,
                timeout=args.versions_timeout,
            )

    if args.json:
        print(json.dumps(catalog.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(f"agent_id: {catalog.agent_id}")
        source_packages = catalog.source.get("packages") or catalog.source.get(
            "package"
        )
        if isinstance(source_packages, list):
            source_package_text = ", ".join(str(package) for package in source_packages)
        else:
            source_package_text = str(source_packages or "")
        print(f"source: {catalog.source.get('type')} {source_package_text}")
        print(f"catalog_path: {path}")
        print(f"fetched_at: {catalog.fetched_at}")
        print(f"version_count: {len(catalog.versions)}")
        print(f"benchmark_version_policy: {catalog.benchmark_version_policy}")
        if catalog.benchmark_min_version:
            print(f"benchmark_min_version: {catalog.benchmark_min_version}")
        print(f"benchmark_version_count: {len(catalog.benchmark_versions)}")
        print(f"benchmark_exclusion_count: {len(catalog.excluded_benchmark_versions)}")
        print(f"latest: {catalog.latest}")
    return 0


def _benchmark_initial_version_limit(args: argparse.Namespace) -> int | None:
    return None if args.initial_version_limit <= 0 else args.initial_version_limit


def _benchmark_batch_kwargs(args: argparse.Namespace) -> dict:
    initial_version_limit = _benchmark_initial_version_limit(args)
    return {
        "prompt_path": args.prompt,
        "out_dir": args.out,
        "timeout": args.timeout,
        "versions_dir": args.versions_dir,
        "versions_timeout": args.versions_timeout,
        "use_local_versions": args.use_local_versions,
        "requested_versions": args.requested_versions,
        "max_versions": args.max_versions,
        "initial_version_limit": initial_version_limit,
        "include_platform_versions": args.include_platform_versions,
        "build": not args.no_build,
        "dry_run": args.dry_run,
        "skip_existing": args.skip_existing,
        "rerun_existing": args.rerun_existing,
        "stop_on_error": args.stop_on_error,
        "results_out": args.results_out,
        "export_results": not args.no_export,
    }


def _run_benchmark_batch_from_args(args: argparse.Namespace, *, agent_id: str):
    return run_benchmark_batch(agent_id=agent_id, **_benchmark_batch_kwargs(args))


def _run_benchmark_batches_from_args(
    args: argparse.Namespace, *, on_agent_progress=None
):
    return run_benchmark_batches(
        **_benchmark_batch_kwargs(args),
        on_agent_progress=on_agent_progress,
    )


def cmd_benchmark_all(args: argparse.Namespace) -> int:
    console = Console()
    if args.requested_versions:
        Console(stderr=True).print(
            "[bold red]benchmark all does not support --version[/]; "
            "target a specific agent instead"
        )
        return 2

    try:
        with BenchmarkAllProgress(console=console) as progress:
            batches = _run_benchmark_batches_from_args(args, on_agent_progress=progress)
    except DockerUnavailableError as exc:
        Console(stderr=True).print(f"[bold red]{exc}[/]")
        return 127

    print_benchmark_batches_report(batches, console=console)
    return 1 if batches.has_errors else 0


def cmd_benchmark(args: argparse.Namespace) -> int:
    if args.agent == "all":
        return cmd_benchmark_all(args)

    console = Console()
    try:
        batch = _run_benchmark_batch_from_args(args, agent_id=args.agent)
    except DockerUnavailableError as exc:
        Console(stderr=True).print(f"[bold red]{exc}[/]")
        return 127

    print_benchmark_batch_report(batch, console=console)
    return 1 if batch.has_errors else 0


def cmd_summarize(args: argparse.Namespace) -> int:
    summary = write_run_artifacts(args.run_dir)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    result = export_benchmark_results(args.runs_dir, args.out)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hibench", description="Benchmark coding-agent context and tool footprint."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    agents = subparsers.add_parser("agents", help="List configured coding agents.")
    agents.set_defaults(func=cmd_agents)

    build = subparsers.add_parser("build", help="Build an agent Docker image.")
    build.add_argument("agent", choices=list_agent_ids())
    build.add_argument("--image", help="Override target image tag.")
    build.add_argument("--version", help="Override configured agent version.")
    build.set_defaults(func=cmd_build)

    run = subparsers.add_parser(
        "run", help="Run an agent against the local request recorder."
    )
    run.add_argument("agent", choices=list_agent_ids())
    run.add_argument("--prompt", default="prompts/hi.txt")
    run.add_argument("--out", default="runs")
    run.add_argument("--timeout", type=int, default=30)
    run.add_argument("--image", help="Override Docker image tag.")
    run.add_argument(
        "--build", action="store_true", help="Build the image before running."
    )
    run.add_argument("--version", help="Override configured agent version.")
    run.add_argument("--run-id", help="Override run directory name.")
    run.add_argument(
        "--replace",
        action="store_true",
        help="Replace the run directory when --run-id already exists.",
    )
    run.set_defaults(func=cmd_run)

    versions = subparsers.add_parser(
        "versions", help="Fetch or display stored agent versions."
    )
    versions.add_argument("agent", choices=list_agent_ids())
    versions.add_argument("--versions-dir", default="agent_versions")
    versions.add_argument("--versions-timeout", type=int, default=60)
    versions.add_argument(
        "--refresh",
        action="store_true",
        help="Fetch fresh versions from the configured source.",
    )
    versions.add_argument(
        "--json", action="store_true", help="Print the full stored catalog as JSON."
    )
    versions.set_defaults(func=cmd_versions)

    benchmark = subparsers.add_parser(
        "benchmark",
        help=(
            "Fetch versions and run one canonical benchmark per agent version "
            "for one agent, or for every agent with 'all'."
        ),
    )
    benchmark.add_argument(
        "agent",
        choices=[*list_agent_ids(), "all"],
        help="Agent ID to benchmark, or 'all' for every configured agent.",
    )
    benchmark.add_argument("--prompt", default="prompts/hi.txt")
    benchmark.add_argument("--out", default="runs")
    benchmark.add_argument("--timeout", type=int, default=30)
    benchmark.add_argument("--versions-dir", default="agent_versions")
    benchmark.add_argument("--versions-timeout", type=int, default=60)
    benchmark.add_argument(
        "--use-local-versions",
        action="store_true",
        help="Use stored versions instead of refreshing from source.",
    )
    benchmark.add_argument(
        "--version",
        dest="requested_versions",
        action="append",
        help="Benchmark only this version; repeatable.",
    )
    benchmark.add_argument(
        "--max-versions",
        type=int,
        help="Benchmark only the first N selected/catalog versions.",
    )
    benchmark.add_argument(
        "--initial-version-limit",
        type=int,
        default=DEFAULT_INITIAL_AGENT_VERSION_LIMIT,
        help=(
            "For automatic selection, consider only the latest N benchmarkable versions "
            f"(default: {DEFAULT_INITIAL_AGENT_VERSION_LIMIT}; use 0 to disable)."
        ),
    )
    benchmark.add_argument(
        "--include-platform-versions",
        action="store_true",
        help=(
            "Include stored platform, prerelease, and timestamp/internal variants "
            "in automatic selection. For diagnostics only."
        ),
    )
    benchmark.add_argument(
        "--no-build",
        action="store_true",
        help="Do not build Docker images before running.",
    )
    benchmark.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan benchmarks without building or running agents.",
    )
    benchmark.add_argument(
        "--skip-existing",
        action="store_true",
        help=(
            "Skip versions that already have a stored run when explicitly requested "
            "or when --rerun-existing is used."
        ),
    )
    benchmark.add_argument(
        "--rerun-existing",
        action="store_true",
        help=(
            "Include versions that already have stored runs in automatic selection. "
            "By default benchmark runs select only missing agent/version rows."
        ),
    )
    benchmark.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop the batch at the first version error.",
    )
    benchmark.add_argument(
        "--results-out", default="results", help="Aggregate dashboard output directory."
    )
    benchmark.add_argument(
        "--no-export",
        action="store_true",
        help="Do not refresh aggregate dashboard tables after each completed run.",
    )
    benchmark.set_defaults(func=cmd_benchmark)

    summarize = subparsers.add_parser(
        "summarize", help="Rebuild summary.json for a run directory."
    )
    summarize.add_argument("run_dir")
    summarize.set_defaults(func=cmd_summarize)

    export = subparsers.add_parser(
        "export", help="Export Power BI-friendly CSV tables from run directories."
    )
    export.add_argument("--runs-dir", default="runs")
    export.add_argument("--out", default="results")
    export.set_defaults(func=cmd_export)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
