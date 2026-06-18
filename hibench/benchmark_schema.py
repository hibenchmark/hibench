from __future__ import annotations

from pathlib import Path
from typing import Any

from .marker_dimensions import MARKER_DIMENSIONS, MarkerDimension

RESULT_SCHEMA_VERSION = "hibench.benchmark.v1"

RUN_CSV_FIELDS = [
    "schema_version",
    "run_id",
    "run_dir",
    "agent_id",
    "agent_name",
    "agent_version",
    "agent_image",
    "prompt_file",
    "prompt_name",
    "started_at",
    "ended_at",
    "subject_workspace",
    "real_api_call",
    "process_exit_code",
    "process_timed_out",
    "request_count",
    "post_request_count",
    "has_primary_request",
    "primary_request_index",
    "request_method",
    "request_path",
    "model",
    "tokenizer_library",
    "tokenizer_encoding",
    "total_body_tokens",
    "body_tokens",
    "body_bytes",
    "body_chars",
    "text_field_count",
    "text_tokens",
    "system_prompt_tokens",
    "environment_context_tokens",
    "user_prompt_tokens",
    "assistant_context_tokens",
    "tool_context_tokens",
    "other_text_tokens",
    "main_instructions_tokens",
    "developer_instructions_tokens",
    "permissions_instructions_tokens",
    "skills_instructions_tokens",
    "injected_user_context_tokens",
    "instruction_tokens",
    "default_context_tokens",
    "skills_count",
    "skills_tokens",
    "skill_definition_tokens",
    "tool_count",
    "tool_definition_tokens",
    *[
        field
        for dimension in MARKER_DIMENSIONS
        for field in (
            f"{dimension.run_field_prefix}_count",
            f"{dimension.run_field_prefix}_tokens",
            f"{dimension.run_field_prefix}_marker_count",
            f"{dimension.run_field_prefix}_mention_count",
            f"{dimension.run_field_prefix}_mention_tokens",
        )
    ],
]
TOOL_CSV_FIELDS = [
    "schema_version",
    "run_id",
    "agent_id",
    "agent_version",
    "request_index",
    "tool_index",
    "tool_name",
    "tool_type",
    "path",
    "definition_chars",
    "definition_tokens",
    *[dimension.tool_related_field for dimension in MARKER_DIMENSIONS],
    "keys",
]
MARKER_CSV_FIELDS = [
    "schema_version",
    "run_id",
    "agent_id",
    "agent_version",
    "request_index",
    "marker_index",
    "marker_name",
    "source_type",
    "is_counted",
    "path",
    "chars",
    "tokens",
    "preview",
]
SKILL_CSV_FIELDS = [
    "schema_version",
    "run_id",
    "agent_id",
    "agent_version",
    "request_index",
    "skill_index",
    "skill_name",
    "skill_file",
    "source_path",
    "definition_chars",
    "definition_tokens",
    "description",
    "preview",
]
TEXT_FIELD_CSV_FIELDS = [
    "schema_version",
    "run_id",
    "agent_id",
    "agent_version",
    "request_index",
    "text_index",
    "category",
    "source",
    "role",
    "path",
    "chars",
    "tokens",
    "preview",
]


def category_tokens(fields: list[dict[str, Any]], category: str) -> int:
    return sum(
        int(field.get("tokens") or 0)
        for field in fields
        if field.get("category") == category
    )


def source_tokens(fields: list[dict[str, Any]], source: str) -> int:
    return sum(
        int(field.get("tokens") or 0)
        for field in fields
        if field.get("source") == source
    )


def common_dimensions(manifest: dict[str, Any], run_path: Path) -> dict[str, Any]:
    agent = manifest.get("agent") if isinstance(manifest.get("agent"), dict) else {}
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "run_id": manifest.get("run_id") or run_path.name,
        "agent_id": agent.get("id", ""),
        "agent_version": agent.get("version", ""),
    }


def marker_run_metrics(primary: dict[str, Any]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for dimension in MARKER_DIMENSIONS:
        summary = primary.get(dimension.summary_key) or {}
        prefix = dimension.run_field_prefix
        metrics.update(
            {
                f"{prefix}_count": summary.get("count", 0),
                f"{prefix}_tokens": summary.get("tokens", 0),
                f"{prefix}_marker_count": summary.get("marker_count", 0),
                f"{prefix}_mention_count": summary.get("mention_count", 0),
                f"{prefix}_mention_tokens": summary.get("mention_tokens", 0),
            }
        )
    return metrics


def marker_rows(
    dimension: MarkerDimension,
    items: list[dict[str, Any]],
    dims: dict[str, Any],
    primary_index: Any,
) -> list[dict[str, Any]]:
    return [
        {
            **dims,
            "request_index": primary_index,
            "marker_index": item.get("marker_index", index),
            "marker_name": item.get("name", ""),
            "source_type": item.get("source_type", ""),
            "is_counted": item.get("is_counted", False),
            "path": item.get("path", ""),
            "chars": item.get("chars", 0),
            "tokens": item.get("tokens", 0),
            "preview": item.get("preview", ""),
        }
        for index, item in enumerate(items, start=1)
    ]


def build_benchmark_result(
    run_path: Path, manifest: dict[str, Any], summary: dict[str, Any]
) -> dict[str, Any]:
    primary = summary.get("primary_request") or {}
    primary_index = summary.get("primary_request_index") or ""
    text_fields = list((primary.get("text_fields") or {}).get("fields") or [])
    tool_items = list((primary.get("tools") or {}).get("items") or [])
    marker_items = {
        dimension.summary_key: list(
            (primary.get(dimension.summary_key) or {}).get("items") or []
        )
        for dimension in MARKER_DIMENSIONS
    }
    skill_items = list((primary.get("skills") or {}).get("items") or [])
    agent = manifest.get("agent") if isinstance(manifest.get("agent"), dict) else {}
    process = (
        manifest.get("process") if isinstance(manifest.get("process"), dict) else {}
    )
    prompt_file = str(manifest.get("prompt_file") or "")
    tokenizer = primary.get("tokenizer") or {}
    dims = common_dimensions(manifest, run_path)

    run_row = {
        **dims,
        "run_dir": str(run_path),
        "agent_name": agent.get("display_name", ""),
        "agent_image": agent.get("image", ""),
        "prompt_file": prompt_file,
        "prompt_name": Path(prompt_file).stem if prompt_file else "",
        "started_at": manifest.get("started_at", ""),
        "ended_at": manifest.get("ended_at", ""),
        "subject_workspace": manifest.get("subject_workspace", ""),
        "real_api_call": manifest.get("real_api_call", ""),
        "process_exit_code": process.get("exit_code", ""),
        "process_timed_out": process.get("timed_out", ""),
        "request_count": summary.get("request_count", 0),
        "post_request_count": summary.get("post_request_count", 0),
        "has_primary_request": bool(primary),
        "primary_request_index": primary_index,
        "request_method": primary.get("method", ""),
        "request_path": primary.get("path", ""),
        "model": primary.get("model", ""),
        "tokenizer_library": tokenizer.get("library", ""),
        "tokenizer_encoding": tokenizer.get("encoding", ""),
        "total_body_tokens": primary.get("body_tokens", 0),
        "body_tokens": primary.get("body_tokens", 0),
        "body_bytes": primary.get("body_bytes", 0),
        "body_chars": primary.get("body_chars", 0),
        "text_field_count": (primary.get("text_fields") or {}).get("count", 0),
        "text_tokens": (primary.get("text_fields") or {}).get("tokens", 0),
        "system_prompt_tokens": category_tokens(text_fields, "system_prompt"),
        "environment_context_tokens": category_tokens(
            text_fields, "environment_context"
        ),
        "user_prompt_tokens": category_tokens(text_fields, "user_prompt"),
        "assistant_context_tokens": category_tokens(text_fields, "assistant_context"),
        "tool_context_tokens": category_tokens(text_fields, "tool_context"),
        "other_text_tokens": category_tokens(text_fields, "other_text"),
        "main_instructions_tokens": source_tokens(text_fields, "main_instructions"),
        "developer_instructions_tokens": source_tokens(
            text_fields, "developer_instructions"
        )
        + source_tokens(text_fields, "permissions_instructions")
        + source_tokens(text_fields, "skills_instructions"),
        "permissions_instructions_tokens": source_tokens(
            text_fields, "permissions_instructions"
        ),
        "skills_instructions_tokens": source_tokens(text_fields, "skills_instructions"),
        "injected_user_context_tokens": source_tokens(
            text_fields, "injected_user_context"
        ),
        "instruction_tokens": source_tokens(text_fields, "main_instructions")
        + source_tokens(text_fields, "developer_instructions")
        + source_tokens(text_fields, "permissions_instructions")
        + source_tokens(text_fields, "skills_instructions")
        + source_tokens(text_fields, "injected_user_context"),
        "default_context_tokens": category_tokens(text_fields, "system_prompt")
        + category_tokens(text_fields, "environment_context")
        + int((primary.get("tools") or {}).get("tokens", 0)),
        "skills_count": (primary.get("skills") or {}).get("count", 0),
        "skills_tokens": (primary.get("skills") or {}).get("tokens", 0),
        "skill_definition_tokens": (primary.get("skills") or {}).get(
            "definition_tokens", 0
        ),
        "tool_count": (primary.get("tools") or {}).get("count", 0),
        "tool_definition_tokens": (primary.get("tools") or {}).get("tokens", 0),
        **marker_run_metrics(primary),
    }

    tools = [
        {
            **dims,
            "request_index": primary_index,
            "tool_index": tool.get("tool_index", index),
            "tool_name": tool.get("name", ""),
            "tool_type": tool.get("type", ""),
            "path": tool.get("path", ""),
            "definition_chars": tool.get("chars", 0),
            "definition_tokens": tool.get("tokens", 0),
            **{
                dimension.tool_related_field: tool.get(
                    dimension.tool_related_field, False
                )
                for dimension in MARKER_DIMENSIONS
            },
            "keys": "|".join(tool.get("keys") or []),
        }
        for index, tool in enumerate(tool_items, start=1)
    ]
    marker_tables = {
        dimension.summary_key: marker_rows(
            dimension, marker_items[dimension.summary_key], dims, primary_index
        )
        for dimension in MARKER_DIMENSIONS
    }
    skills = [
        {
            **dims,
            "request_index": primary_index,
            "skill_index": item.get("skill_index", index),
            "skill_name": item.get("name", ""),
            "skill_file": item.get("file", ""),
            "source_path": item.get("source_path", ""),
            "definition_chars": item.get("chars", 0),
            "definition_tokens": item.get("tokens", 0),
            "description": item.get("description", ""),
            "preview": item.get("preview", ""),
        }
        for index, item in enumerate(skill_items, start=1)
    ]
    text_field_rows = [
        {
            **dims,
            "request_index": primary_index,
            "text_index": index,
            "category": field.get("category", ""),
            "source": field.get("source", ""),
            "role": field.get("role", ""),
            "path": field.get("path", ""),
            "chars": field.get("chars", 0),
            "tokens": field.get("tokens", 0),
            "preview": field.get("preview", ""),
        }
        for index, field in enumerate(text_fields, start=1)
    ]

    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "run": run_row,
        "tools": tools,
        **marker_tables,
        "skills": skills,
        "text_fields": text_field_rows,
    }
