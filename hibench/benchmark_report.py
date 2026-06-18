from __future__ import annotations

from pathlib import Path
from typing import Any

from .marker_dimensions import MARKER_DIMENSIONS, MarkerDimension


def display_value(value: Any) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def preview_text(value: Any, limit: int = 80) -> str:
    text = str(value or "").replace("\r", "\\r").replace("\n", "\\n")
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def append_metrics(lines: list[str], metrics: list[tuple[str, Any]]) -> None:
    for label, value in metrics:
        lines.append(f"  {label}: {display_value(value)}")


def marker_metric_items(totals: dict[str, Any], prefix: str) -> list[tuple[str, Any]]:
    metrics: list[tuple[str, Any]] = []
    for dimension in MARKER_DIMENSIONS:
        field_prefix = dimension.run_field_prefix
        metrics.extend(
            [
                (
                    f"{prefix}_{field_prefix}_marker_count",
                    totals.get(f"{field_prefix}_marker_count"),
                ),
                (
                    f"{prefix}_{field_prefix}_mention_count",
                    totals.get(f"{field_prefix}_mention_count"),
                ),
            ]
        )
    return metrics


def marker_footprint_metrics(run: dict[str, Any]) -> list[tuple[str, Any]]:
    metrics: list[tuple[str, Any]] = []
    for dimension in MARKER_DIMENSIONS:
        prefix = dimension.run_field_prefix
        metrics.extend(
            [
                (f"{prefix}_count", run.get(f"{prefix}_count")),
                (f"{prefix}_tokens", run.get(f"{prefix}_tokens")),
                (f"{prefix}_marker_count", run.get(f"{prefix}_marker_count")),
                (f"{prefix}_mention_count", run.get(f"{prefix}_mention_count")),
                (f"{prefix}_mention_tokens", run.get(f"{prefix}_mention_tokens")),
            ]
        )
    return metrics


def append_marker_section(
    lines: list[str],
    dimension: MarkerDimension,
    items: list[dict[str, Any]],
    run: dict[str, Any],
) -> None:
    prefix = dimension.run_field_prefix
    lines.extend(
        [
            "",
            (
                f"{dimension.report_heading} ({display_value(len(items))}; "
                f"counted={display_value(run.get(f'{prefix}_count'))})"
            ),
        ]
    )
    if items:
        for item in items:
            lines.append(
                "  - "
                f"{item.get('name', '-')} "
                f"source={display_value(item.get('source_type'))} "
                f"counted={display_value(item.get('is_counted'))} "
                f"tokens={display_value(item.get('tokens'))} "
                f"chars={display_value(item.get('chars'))} "
                f"path={display_value(item.get('path'))} "
                f'preview="{preview_text(item.get("preview"))}"'
            )
    else:
        lines.append("  - none")


def format_benchmark_report(run_dir: str | Path, summary: dict[str, Any]) -> str:
    """Human-readable run report aligned with benchmark_result.json."""

    run = summary.get("benchmark") if isinstance(summary.get("benchmark"), dict) else {}
    primary = (
        summary.get("primary_request")
        if isinstance(summary.get("primary_request"), dict)
        else {}
    )
    tokenizer = (
        primary.get("tokenizer") if isinstance(primary.get("tokenizer"), dict) else {}
    )
    text_fields = (
        list((primary.get("text_fields") or {}).get("fields") or []) if primary else []
    )
    tools = list((primary.get("tools") or {}).get("items") or []) if primary else []
    marker_items = {
        dimension.summary_key: (
            list((primary.get(dimension.summary_key) or {}).get("items") or [])
            if primary
            else []
        )
        for dimension in MARKER_DIMENSIONS
    }
    skill_items = (
        list((primary.get("skills") or {}).get("items") or []) if primary else []
    )
    totals = summary.get("totals") if isinstance(summary.get("totals"), dict) else {}
    post_totals = (
        summary.get("post_totals")
        if isinstance(summary.get("post_totals"), dict)
        else {}
    )

    lines = [
        "HiBench benchmark report",
        "========================",
        "",
        "Run",
    ]
    append_metrics(
        lines,
        [
            ("run_dir", run.get("run_dir") or str(run_dir)),
            ("run_id", run.get("run_id")),
            ("prompt_file", run.get("prompt_file")),
            ("started_at", run.get("started_at")),
            ("ended_at", run.get("ended_at")),
            ("real_api_call", run.get("real_api_call")),
            ("process_exit_code", run.get("process_exit_code")),
            ("process_timed_out", run.get("process_timed_out")),
        ],
    )

    lines.extend(["", "Agent"])
    append_metrics(
        lines,
        [
            ("agent_id", run.get("agent_id")),
            ("agent_name", run.get("agent_name")),
            ("agent_version", run.get("agent_version")),
            ("agent_image", run.get("agent_image")),
        ],
    )

    lines.extend(["", "Capture"])
    append_metrics(
        lines,
        [
            ("request_count", run.get("request_count")),
            ("post_request_count", run.get("post_request_count")),
            ("has_primary_request", run.get("has_primary_request")),
            ("primary_request_index", run.get("primary_request_index")),
            ("request_method", run.get("request_method")),
            ("request_path", run.get("request_path")),
            ("model", run.get("model")),
            (
                (
                    "tokenizer",
                    f"{tokenizer.get('library', '-')}/{tokenizer.get('encoding', '-')}",
                )
                if tokenizer
                else ("tokenizer", run.get("tokenizer_encoding"))
            ),
            ("tokenizer_source", tokenizer.get("source") if tokenizer else ""),
        ],
    )

    if not primary:
        run_path = Path(run_dir)
        lines.extend(
            [
                "",
                "No primary POST request was captured. Benchmark metric fields are zero/blank.",
                "",
                "Diagnostic totals across captured requests/retries",
            ]
        )
        append_metrics(
            lines,
            [
                ("all_request_body_tokens", totals.get("body_tokens")),
                ("all_request_body_bytes", totals.get("body_bytes")),
                ("all_request_skill_count", totals.get("skill_count")),
                ("all_request_tool_count", totals.get("tool_count")),
                *marker_metric_items(totals, "all_request"),
                ("post_body_tokens", post_totals.get("body_tokens")),
                ("post_body_bytes", post_totals.get("body_bytes")),
                ("post_skill_count", post_totals.get("skill_count")),
                ("post_tool_count", post_totals.get("tool_count")),
            ],
        )
        lines.extend(
            [
                "",
                "Artifacts",
                f"  summary_json: {run_path / 'summary.json'}",
                f"  benchmark_result_json: {run_path / 'benchmark_result.json'}",
                f"  benchmark_tables: {run_path / 'benchmark_tables'}",
            ]
        )
        return "\n".join(lines)

    lines.extend(["", "Primary request token metrics"])
    append_metrics(
        lines,
        [
            ("total_body_tokens", run.get("total_body_tokens")),
            ("body_tokens", run.get("body_tokens")),
            ("body_bytes", run.get("body_bytes")),
            ("body_chars", run.get("body_chars")),
            ("text_field_count", run.get("text_field_count")),
            ("text_tokens", run.get("text_tokens")),
        ],
    )

    lines.extend(["", "Text token breakdown"])
    append_metrics(
        lines,
        [
            ("system_prompt_tokens", run.get("system_prompt_tokens")),
            ("environment_context_tokens", run.get("environment_context_tokens")),
            ("user_prompt_tokens", run.get("user_prompt_tokens")),
            ("assistant_context_tokens", run.get("assistant_context_tokens")),
            ("tool_context_tokens", run.get("tool_context_tokens")),
            ("other_text_tokens", run.get("other_text_tokens")),
        ],
    )

    lines.extend(["", "Instruction sources"])
    append_metrics(
        lines,
        [
            ("instruction_tokens", run.get("instruction_tokens")),
            ("main_instructions_tokens", run.get("main_instructions_tokens")),
            ("developer_instructions_tokens", run.get("developer_instructions_tokens")),
            (
                "permissions_instructions_tokens",
                run.get("permissions_instructions_tokens"),
            ),
            ("skills_instructions_tokens", run.get("skills_instructions_tokens")),
            ("injected_user_context_tokens", run.get("injected_user_context_tokens")),
        ],
    )

    lines.extend(["", "Default footprint"])
    append_metrics(
        lines,
        [
            ("default_context_tokens", run.get("default_context_tokens")),
            ("skills_count", run.get("skills_count")),
            ("skills_tokens", run.get("skills_tokens")),
            ("skill_definition_tokens", run.get("skill_definition_tokens")),
            ("tool_count", run.get("tool_count")),
            ("tool_definition_tokens", run.get("tool_definition_tokens")),
            *marker_footprint_metrics(run),
        ],
    )

    lines.extend(["", f"Skills ({display_value(run.get('skills_count'))})"])
    if skill_items:
        for skill in skill_items:
            lines.append(
                "  - "
                f"{skill.get('name', '-')} "
                f"tokens={display_value(skill.get('tokens'))} "
                f"chars={display_value(skill.get('chars'))} "
                f"file={display_value(skill.get('file'))}"
            )
    else:
        lines.append("  - none")

    lines.extend(["", f"Tools ({display_value(run.get('tool_count'))})"])
    if tools:
        for tool in tools:
            lines.append(
                "  - "
                f"{tool.get('name', '-')} "
                f"[{tool.get('type', '-') or '-'}] "
                f"tokens={display_value(tool.get('tokens'))} "
                f"chars={display_value(tool.get('chars'))} "
                f"path={display_value(tool.get('path'))}"
            )
    else:
        lines.append("  - none")

    for dimension in MARKER_DIMENSIONS:
        append_marker_section(
            lines, dimension, marker_items[dimension.summary_key], run
        )

    lines.extend(["", f"Text fields ({display_value(run.get('text_field_count'))})"])
    if text_fields:
        for field in text_fields:
            lines.append(
                "  - "
                f"{field.get('category', '-')} "
                f"source={display_value(field.get('source'))} "
                f"role={display_value(field.get('role'))} "
                f"tokens={display_value(field.get('tokens'))} "
                f"chars={display_value(field.get('chars'))} "
                f"path={display_value(field.get('path'))} "
                f'preview="{preview_text(field.get("preview"))}"'
            )
    else:
        lines.append("  - none")

    lines.extend(["", "Diagnostic totals across captured requests/retries"])
    append_metrics(
        lines,
        [
            ("all_request_body_tokens", totals.get("body_tokens")),
            ("all_request_body_bytes", totals.get("body_bytes")),
            ("all_request_skill_count", totals.get("skill_count")),
            ("all_request_tool_count", totals.get("tool_count")),
            *marker_metric_items(totals, "all_request"),
            ("post_body_tokens", post_totals.get("body_tokens")),
            ("post_body_bytes", post_totals.get("body_bytes")),
            ("post_skill_count", post_totals.get("skill_count")),
            ("post_tool_count", post_totals.get("tool_count")),
        ],
    )
    lines.append(
        "  note: benchmark comparisons use the primary request metrics above, not retry totals."
    )

    run_path = Path(run_dir)
    lines.extend(
        [
            "",
            "Artifacts",
            f"  summary_json: {run_path / 'summary.json'}",
            f"  benchmark_result_json: {run_path / 'benchmark_result.json'}",
            f"  benchmark_tables: {run_path / 'benchmark_tables'}",
        ]
    )
    return "\n".join(lines)
