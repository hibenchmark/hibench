from __future__ import annotations

from collections import Counter
from pathlib import Path
from types import TracebackType

from rich import box
from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

from .automation import (
    AllBenchmarkBatchResult,
    BenchmarkAgentProgress,
    BenchmarkBatchResult,
    VersionBenchmarkResult,
)


STATUS_STYLES = {
    "created": "green",
    "replaced": "cyan",
    "planned": "yellow",
    "skipped": "dim",
    "error": "bold red",
}


def _status_text(status: str) -> Text:
    return Text(status, style=STATUS_STYLES.get(status, "white"))


def _bool_text(value: bool | None) -> Text:
    if value is True:
        return Text("yes", style="green")
    if value is False:
        return Text("no", style="bold red")
    return Text("—", style="dim")


def _value(value: object | None) -> str:
    return "—" if value is None else str(value)


def _mode(batch: BenchmarkBatchResult) -> str:
    if batch.manifest["requested_versions"] or batch.manifest["rerun_existing"]:
        if batch.manifest["skip_existing"]:
            return "skip existing"
        return "replace selected existing"
    return "missing versions only"


def _summary_table(batch: BenchmarkBatchResult) -> Table:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold cyan", no_wrap=True)
    table.add_column()
    table.add_row("agent_id", batch.agent_id)
    table.add_row("catalog", str(batch.catalog_path))
    table.add_row("available_versions", str(batch.available_version_count))
    table.add_row("stored_versions", str(len(batch.catalog.versions)))
    table.add_row("policy", batch.catalog.benchmark_version_policy)
    if batch.catalog.benchmark_min_version:
        table.add_row("min_version", batch.catalog.benchmark_min_version)
    table.add_row(
        "benchmark_exclusions", str(len(batch.catalog.excluded_benchmark_versions))
    )
    table.add_row("existing_versions", str(len(batch.selection.existing_versions)))
    table.add_row(
        "skipped_existing", str(len(batch.selection.skipped_existing_versions))
    )
    table.add_row("candidate_versions", str(batch.selection.candidate_version_count))
    if batch.selection.initial_limit and batch.selection.initial_limit > 0:
        state = "applied" if batch.selection.initial_limit_applied else "not needed"
        table.add_row(
            "version_window", f"latest {batch.selection.initial_limit} ({state})"
        )
    else:
        table.add_row("version_window", "disabled")
    table.add_row("selected_versions", str(len(batch.selected_versions)))
    table.add_row("out_dir", batch.manifest["out_dir"])
    table.add_row("build", str(batch.manifest["build"]).lower())
    table.add_row("dry_run", str(batch.manifest["dry_run"]).lower())
    table.add_row("mode", _mode(batch))
    table.add_row("aggregate_export", str(batch.manifest["export_results"]).lower())
    return table


def _result_detail(result: VersionBenchmarkResult) -> str:
    if result.error:
        return result.error
    return result.run_dir


def _results_table(results: list[VersionBenchmarkResult]) -> Table:
    table = Table(
        title="Version results",
        box=box.SIMPLE_HEAVY,
        expand=True,
        show_lines=False,
    )
    table.add_column("Version", style="bold", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Tokens", justify="right", no_wrap=True)
    table.add_column("Tools", justify="right", no_wrap=True)
    table.add_column("Primary", justify="center", no_wrap=True)
    table.add_column("Run / error", overflow="fold")
    if not results:
        table.add_row(
            "—", Text("none", style="dim"), "—", "—", "—", "no selected versions"
        )
        return table
    for result in results:
        table.add_row(
            result.version,
            _status_text(result.status),
            _value(result.total_body_tokens),
            _value(result.tool_count),
            _bool_text(result.has_primary_request),
            _result_detail(result),
        )
    return table


def _aggregate_table(batch: BenchmarkBatchResult) -> Table | None:
    if not batch.export_manifest:
        return None
    aggregate_refreshes = max(batch.aggregate_refresh_count, 1)
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold cyan", no_wrap=True)
    table.add_column()
    table.add_row("aggregate_results", batch.manifest["results_out"])
    table.add_row("aggregate_refreshes", str(aggregate_refreshes))
    table.add_row(
        "aggregate_runs",
        f"{batch.export_manifest['run_count']} unique agent/version rows",
    )
    table.add_row(
        "deduplicated_runs",
        str(batch.export_manifest["deduplicated_run_count"]),
    )
    table.add_row(
        "aggregate_manifest",
        str(Path(batch.manifest["results_out"]) / "export.json"),
    )
    return table


def benchmark_batch_renderable(batch: BenchmarkBatchResult) -> RenderableType:
    sections: list[RenderableType] = [
        _summary_table(batch),
        Text(""),
        _results_table(batch.results),
        Text(""),
        Text.assemble(("batch_manifest: ", "bold cyan"), str(batch.manifest_path)),
    ]
    if aggregate := _aggregate_table(batch):
        sections.extend([Text(""), aggregate])
    border_style = "red" if batch.has_errors else "cyan"
    return Panel(
        Group(*sections),
        title=f"[bold]HiBench benchmark[/] [cyan]{batch.agent_id}[/]",
        border_style=border_style,
        expand=True,
    )


def _counts_text(batch: BenchmarkBatchResult) -> str:
    counts = Counter(result.status for result in batch.results)
    ordered = [
        f"{status}:{counts[status]}"
        for status in ("created", "replaced", "planned", "skipped", "error")
        if counts[status]
    ]
    return ", ".join(ordered) if ordered else "no versions"


def _agent_advancement_table(result: AllBenchmarkBatchResult) -> Table:
    table = Table(
        title="Agent advancement",
        box=box.SIMPLE_HEAVY,
        expand=True,
        show_lines=False,
    )
    table.add_column("#", justify="right", no_wrap=True)
    table.add_column("Agent", style="bold", no_wrap=True)
    table.add_column("Selected", justify="right", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Results")
    table.add_column("Manifest", overflow="fold")
    for index, batch in enumerate(result.batches, start=1):
        status = (
            Text("error", style="bold red")
            if batch.has_errors
            else Text("ok", style="green")
        )
        table.add_row(
            f"{index}/{len(result.agent_ids)}",
            batch.agent_id,
            str(len(batch.selected_versions)),
            status,
            _counts_text(batch),
            str(batch.manifest_path),
        )
    if not result.batches:
        table.add_row("0/0", "—", "0", Text("none", style="dim"), "no agents", "—")
    return table


def benchmark_batches_renderable(result: AllBenchmarkBatchResult) -> RenderableType:
    overview = Table.grid(padding=(0, 2))
    overview.add_column(style="bold cyan", no_wrap=True)
    overview.add_column()
    overview.add_row("agents", str(len(result.agent_ids)))
    overview.add_row("completed_agents", str(len(result.batches)))
    overview.add_row("has_errors", str(result.has_errors).lower())

    sections: list[RenderableType] = [
        Panel(
            overview,
            title="[bold]HiBench all-agent benchmark[/]",
            border_style="red" if result.has_errors else "cyan",
            expand=True,
        ),
        _agent_advancement_table(result),
    ]
    sections.extend(benchmark_batch_renderable(batch) for batch in result.batches)
    sections.append(
        Text.assemble(("all_batch_manifest: ", "bold cyan"), str(result.manifest_path))
    )
    return Group(*sections)


def print_benchmark_batch_report(
    batch: BenchmarkBatchResult, *, console: Console | None = None
) -> None:
    (console or Console()).print(benchmark_batch_renderable(batch))


def print_benchmark_batches_report(
    result: AllBenchmarkBatchResult, *, console: Console | None = None
) -> None:
    (console or Console()).print(benchmark_batches_renderable(result))


def _completed_agent_line(update: BenchmarkAgentProgress) -> Text:
    batch = update.batch
    if batch is None:
        return Text("")
    mark = "✗" if batch.has_errors else "✓"
    style = "bold red" if batch.has_errors else "bold green"
    return Text.assemble(
        (mark, style),
        f" [{update.agent_index}/{update.agent_count}] ",
        (update.agent_id, "bold"),
        " — ",
        (f"{len(batch.selected_versions)} selected", "cyan"),
        f", {_counts_text(batch)}",
    )


class BenchmarkAllProgress:
    def __init__(self, *, console: Console | None = None) -> None:
        self.console = console or Console()
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self.console,
            transient=True,
        )
        self.task_id: int | None = None

    def __enter__(self) -> BenchmarkAllProgress:
        self.progress.start()
        self.task_id = self.progress.add_task("agents", total=None)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.progress.stop()

    def __call__(self, update: BenchmarkAgentProgress) -> None:
        if self.task_id is None:
            return
        description = f"[{update.agent_index}/{update.agent_count}] {update.agent_id}"
        self.progress.update(
            self.task_id,
            total=update.agent_count,
            description=description,
        )
        if update.event == "completed":
            self.progress.update(self.task_id, completed=update.agent_index)
            self.progress.console.print(_completed_agent_line(update))
