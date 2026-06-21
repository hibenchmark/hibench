from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
import re
from typing import Any

import tiktoken

from .marker_dimensions import (
    MARKER_DIMENSIONS,
    MARKER_DIMENSIONS_BY_KEY,
    MarkerDimension,
)
from .parsers import RequestParser, get_parser

TEXT_KEYS = {
    "content",
    "developer",
    "input",
    "instructions",
    "message",
    "prompt",
    "system",
    "text",
}
TOOL_KEYS = {"tools", "available_tools"}
COUNTED_MARKER_SOURCE_TYPES = {"declaration", "tool_declaration"}
DEFAULT_ENCODING = "o200k_base"
IDENTITY_KEYS = ("name", "server_label", "id", "title")


@lru_cache(maxsize=32)
def encoding_for_name(name: str) -> tiktoken.Encoding:
    return tiktoken.get_encoding(name)


def benchmark_tokenizer(model: str | None) -> tuple[tiktoken.Encoding, dict[str, Any]]:
    encoding = encoding_for_name(DEFAULT_ENCODING)
    return encoding, {
        "library": "tiktoken",
        "encoding": encoding.name,
        "model": model,
        "source": "benchmark_default",
    }


def count_tokens(text: str, encoding: tiktoken.Encoding | None = None) -> int:
    encoding = encoding or encoding_for_name(DEFAULT_ENCODING)
    return len(encoding.encode(text, disallowed_special=()))


def preview(value: str, limit: int = 120) -> str:
    return value[:limit].rstrip()


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def path_text(path: tuple[str, ...]) -> str:
    return ".".join(path) or "<root>"


def marker_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def walk(
    value: Any, path: tuple[str, ...] = ()
) -> Iterable[tuple[tuple[str, ...], Any]]:
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk(child, (*path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, (*path, str(index)))


def get_path(value: Any, path: tuple[str, ...]) -> Any:
    node = value
    for part in path:
        if isinstance(node, dict):
            node = node[part]
        elif isinstance(node, list):
            node = node[int(part)]
        else:
            raise KeyError(path)
    return node


def nearest_role(value: Any, path: tuple[str, ...]) -> str:
    for depth in range(len(path), -1, -1):
        try:
            node = get_path(value, path[:depth])
        except (KeyError, IndexError, ValueError):
            continue
        if isinstance(node, dict) and isinstance(node.get("role"), str):
            return node["role"].lower()
    return ""


def collect_text_fields(
    value: Any, encoding: tiktoken.Encoding, parser: RequestParser | None = None
) -> list[dict[str, Any]]:
    parser = parser or get_parser()
    fields: list[dict[str, Any]] = []
    for path, node in walk(value):
        if not isinstance(node, str) or not path:
            continue
        key = path[-1].lower()
        if key in TEXT_KEYS:
            role = nearest_role(value, path)
            classification = parser.classify_text(path, role, node)
            fields.append(
                {
                    "path": path_text(path),
                    "role": role,
                    "category": classification.category,
                    "source": classification.source,
                    "chars": len(node),
                    "tokens": count_tokens(node, encoding),
                    "preview": preview(node),
                }
            )
    return fields


@dataclass(frozen=True)
class ToolIdentity:
    display_name: str
    values: tuple[str, ...]


def tool_identity(value: Any, fallback: str = "") -> ToolIdentity:
    display_value: str | None = None
    identity_values: list[str] = []

    def add(item: Any) -> None:
        nonlocal display_value
        if not item:
            return
        text = str(item)
        identity_values.append(text)
        if display_value is None:
            display_value = text

    if isinstance(value, dict):
        for key in IDENTITY_KEYS:
            add(value.get(key))
        function = value.get("function")
        if isinstance(function, dict):
            for key in IDENTITY_KEYS:
                add(function.get(key))
        add(value.get("type"))
    return ToolIdentity(
        display_name=display_value or fallback, values=tuple(identity_values)
    )


def display_name(value: Any, fallback: str) -> str:
    return tool_identity(value, fallback).display_name


def collect_skills(
    value: Any, encoding: tiktoken.Encoding, parser: RequestParser | None = None
) -> dict[str, Any]:
    parser = parser or get_parser()
    items: list[dict[str, Any]] = []
    instruction_fields: list[dict[str, Any]] = []

    for path, node in walk(value):
        if not isinstance(node, str) or not path:
            continue
        role = nearest_role(value, path)
        sections = parser.skill_instruction_sections(path, role, node)
        if not sections:
            continue
        for section in sections:
            instruction_fields.append(
                {
                    "path": path_text(path),
                    "role": role,
                    "chars": len(section),
                    "tokens": count_tokens(section, encoding),
                    "preview": preview(section),
                }
            )
            for entry in parser.parse_skill_entries(section):
                items.append(
                    {
                        "skill_index": len(items) + 1,
                        "name": entry.name,
                        "description": entry.description,
                        "file": entry.file,
                        "source_path": path_text(path),
                        "chars": len(entry.text),
                        "tokens": count_tokens(entry.text, encoding),
                        "preview": preview(entry.text),
                    }
                )

    instruction_tokens = sum(field["tokens"] for field in instruction_fields)
    definition_tokens = sum(item["tokens"] for item in items)
    return {
        "count": len(items),
        "tokens": instruction_tokens,
        "definition_tokens": definition_tokens,
        "instruction_field_count": len(instruction_fields),
        "instruction_fields": instruction_fields,
        "items": items,
    }


@dataclass(frozen=True)
class MarkerHit:
    kind: str
    path: tuple[str, ...]
    source_type: str
    serialized: str
    tokens: int
    name: str

    @property
    def path_label(self) -> str:
        return path_text(self.path)


def key_matches_marker(key: str, markers: set[str]) -> bool:
    return marker_text(key) in {marker_text(marker) for marker in markers}


def text_matches_marker(node: Any, markers: set[str]) -> bool:
    if not isinstance(node, str):
        return False
    normalized = marker_text(node)
    return any(marker_text(marker) in normalized for marker in markers)


def marker_serialized_text(node: Any) -> str:
    return node if isinstance(node, str) else compact_json(node)


def is_tool_item_path(path: tuple[str, ...]) -> bool:
    return len(path) >= 2 and path[-2].lower() in TOOL_KEYS and path[-1].isdigit()


def identity_matches_marker(node: dict[str, Any], markers: set[str]) -> bool:
    return any(
        text_matches_marker(value, markers) for value in tool_identity(node).values
    )


def add_declaration_hits(
    add: Any,
    kind: str,
    path: tuple[str, ...],
    node: Any,
) -> None:
    if isinstance(node, list):
        for index, item in enumerate(node):
            add(kind, (*path, str(index)), item, "declaration")
        return
    if isinstance(node, dict):
        if any(key in node for key in ("name", "server_label", "id", "title", "type")):
            add(kind, path, node, "declaration")
            return
        for name, item in node.items():
            if isinstance(item, dict) and not any(
                key in item for key in ("name", "server_label", "id", "title")
            ):
                item = {**item, "name": str(name)}
            add(kind, (*path, str(name)), item, "declaration")
        return
    add(kind, path, node, "declaration")


def collect_marker_hits(
    value: Any, encoding: tiktoken.Encoding, parser: RequestParser | None = None
) -> list[MarkerHit]:
    parser = parser or get_parser()
    hits: list[MarkerHit] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()

    def add(kind: str, path: tuple[str, ...], node: Any, source_type: str) -> None:
        key = (kind, path)
        if key in seen:
            return
        seen.add(key)
        serialized = marker_serialized_text(node)
        hits.append(
            MarkerHit(
                kind=kind,
                path=path,
                source_type=source_type,
                serialized=serialized,
                tokens=count_tokens(serialized, encoding),
                name=display_name(node, ""),
            )
        )

    def add_parser_entry(
        kind: str,
        path: tuple[str, ...],
        name: str,
        serialized: str,
        source_type: str,
    ) -> None:
        key = (kind, path)
        if key in seen:
            return
        seen.add(key)
        hits.append(
            MarkerHit(
                kind=kind,
                path=path,
                source_type=source_type,
                serialized=serialized,
                tokens=count_tokens(serialized, encoding),
                name=name,
            )
        )

    for path, node in walk(value):
        if not path:
            continue
        key = path[-1].lower()
        if isinstance(node, str):
            for index, entry in enumerate(parser.parse_marker_entries(path, node)):
                add_parser_entry(
                    entry.kind,
                    (*path, entry.kind, str(index)),
                    entry.name,
                    entry.text,
                    entry.source_type,
                )
        for dimension in MARKER_DIMENSIONS:
            if key_matches_marker(key, set(dimension.declaration_keys)):
                add(dimension.key, path, node, "path_marker")
                add_declaration_hits(add, dimension.key, path, node)
        if isinstance(node, dict) and is_tool_item_path(path):
            for dimension in MARKER_DIMENSIONS:
                if identity_matches_marker(node, set(dimension.identity_markers)):
                    add(dimension.key, path, node, "tool_declaration")
        for dimension in MARKER_DIMENSIONS:
            if text_matches_marker(node, set(dimension.text_markers)):
                add(dimension.key, path, node, "text_mention")

    return hits


def marker_summary(
    marker_hits: list[MarkerHit], dimension: MarkerDimension | str
) -> dict[str, Any]:
    if isinstance(dimension, str):
        dimension = MARKER_DIMENSIONS_BY_KEY[dimension]
    kind_hits = [hit for hit in marker_hits if hit.kind == dimension.key]
    counted_paths = [
        hit.path for hit in kind_hits if hit.source_type in COUNTED_MARKER_SOURCE_TYPES
    ]
    item_hits = []
    for hit in kind_hits:
        if hit.source_type == "path_marker":
            continue
        if hit.source_type == "text_mention" and any(
            (
                len(hit.path) >= len(counted_path)
                and hit.path[: len(counted_path)] == counted_path
            )
            or (
                len(counted_path) >= len(hit.path)
                and counted_path[: len(hit.path)] == hit.path
            )
            for counted_path in counted_paths
        ):
            continue
        item_hits.append(hit)
    items = [
        {
            "marker_index": index,
            "name": hit.name or f"{dimension.key}_{index}",
            "source_type": hit.source_type,
            "is_counted": hit.source_type in COUNTED_MARKER_SOURCE_TYPES,
            "path": hit.path_label,
            "chars": len(hit.serialized),
            "tokens": hit.tokens,
            "preview": preview(hit.serialized),
        }
        for index, hit in enumerate(item_hits, start=1)
    ]
    counted_items = [item for item in items if item["is_counted"]]
    mention_items = [item for item in items if not item["is_counted"]]
    return {
        "marker_count": len({hit.path_label for hit in kind_hits}),
        "paths": sorted({hit.path_label for hit in kind_hits}),
        "count": len(counted_items),
        "tokens": sum(item["tokens"] for item in counted_items),
        "mention_count": len(mention_items),
        "mention_tokens": sum(item["tokens"] for item in mention_items),
        "items": items,
    }


def marker_kinds_under_path(
    marker_hits: list[MarkerHit], item_path: tuple[str, ...]
) -> set[str]:
    return {
        hit.kind
        for hit in marker_hits
        if len(hit.path) >= len(item_path) and hit.path[: len(item_path)] == item_path
    }


def collect_tools(
    value: Any, encoding: tiktoken.Encoding, marker_hits: list[MarkerHit] | None = None
) -> list[dict[str, Any]]:
    marker_hits = (
        marker_hits if marker_hits is not None else collect_marker_hits(value, encoding)
    )
    tools: list[dict[str, Any]] = []
    for path, node in walk(value):
        if not path or path[-1].lower() not in TOOL_KEYS or not isinstance(node, list):
            continue
        for index, item in enumerate(node):
            item_path = (*path, str(index))
            item_marker_kinds = marker_kinds_under_path(marker_hits, item_path)
            if isinstance(item, dict):
                identity = tool_identity(item, f"tool_{index}")
                serialized = compact_json(item)
                tools.append(
                    {
                        "tool_index": len(tools) + 1,
                        "array_index": index,
                        "path": path_text(item_path),
                        "name": identity.display_name,
                        "type": str(item.get("type", "")),
                        "keys": sorted(str(key) for key in item.keys()),
                        "chars": len(serialized),
                        "tokens": count_tokens(serialized, encoding),
                        **{
                            dimension.tool_related_field: dimension.key
                            in item_marker_kinds
                            for dimension in MARKER_DIMENSIONS
                        },
                    }
                )
            else:
                serialized = str(item)
                tools.append(
                    {
                        "tool_index": len(tools) + 1,
                        "array_index": index,
                        "path": path_text(item_path),
                        "name": serialized,
                        "type": type(item).__name__,
                        "keys": [],
                        "chars": len(serialized),
                        "tokens": count_tokens(serialized, encoding),
                        **{
                            dimension.tool_related_field: dimension.key
                            in item_marker_kinds
                            for dimension in MARKER_DIMENSIONS
                        },
                    }
                )
    return tools


def aggregate_by_category(fields: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    totals: dict[str, dict[str, int]] = {}
    for field in fields:
        category = str(field.get("category") or "other_text")
        item = totals.setdefault(category, {"count": 0, "chars": 0, "tokens": 0})
        item["count"] += 1
        item["chars"] += int(field.get("chars") or 0)
        item["tokens"] += int(field.get("tokens") or 0)
    return totals


def aggregate_by_source(fields: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    totals: dict[str, dict[str, int]] = {}
    for field in fields:
        source = str(field.get("source") or "other_text")
        item = totals.setdefault(source, {"count": 0, "chars": 0, "tokens": 0})
        item["count"] += 1
        item["chars"] += int(field.get("chars") or 0)
        item["tokens"] += int(field.get("tokens") or 0)
    return totals


def is_generation_request(summary: dict[str, Any]) -> bool:
    if str(summary.get("method") or "").upper() != "POST":
        return False
    path = str(summary.get("path") or "")
    normalized = path.split("?", 1)[0].rstrip("/")
    return normalized.endswith(("/responses", "/chat/completions")) or (
        normalized.endswith("/messages")
        and not normalized.endswith("/messages/count_tokens")
    )


def summarize_request(
    record: dict[str, Any], parser_id: str | None = None
) -> dict[str, Any]:
    raw_json = record.get("json")
    body = raw_json
    body_text = record.get("body_text") or ""
    if body is None:
        body = body_text
    parser = get_parser(parser_id)
    body = parser.normalize_body(record, body)
    serialized = compact_json(body) if not isinstance(body, str) else body
    token_text = serialized if raw_json is None and not isinstance(body, str) else (
        body_text or serialized
    )
    model = body.get("model") if isinstance(body, dict) else None
    encoding, tokenizer = benchmark_tokenizer(str(model) if model else None)
    text_fields = collect_text_fields(body, encoding, parser)
    skills = collect_skills(body, encoding, parser)
    marker_hits = collect_marker_hits(body, encoding, parser)
    tools = collect_tools(body, encoding, marker_hits)

    return {
        "method": record.get("method"),
        "path": record.get("path"),
        "model": model,
        "tokenizer": tokenizer,
        "body_bytes": len(body_text.encode("utf-8")),
        "body_chars": len(token_text),
        "body_tokens": count_tokens(token_text, encoding),
        "text_fields": {
            "count": len(text_fields),
            "chars": sum(field["chars"] for field in text_fields),
            "tokens": sum(field["tokens"] for field in text_fields),
            "by_category": aggregate_by_category(text_fields),
            "by_source": aggregate_by_source(text_fields),
            "fields": text_fields,
        },
        "skills": skills,
        "tools": {
            "count": len(tools),
            "names": sorted({tool["name"] for tool in tools}),
            "tokens": sum(tool["tokens"] for tool in tools),
            "items": tools,
        },
        **{
            dimension.summary_key: marker_summary(marker_hits, dimension)
            for dimension in MARKER_DIMENSIONS
        },
    }


def _marker_totals(request_summaries: list[dict[str, Any]]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for dimension in MARKER_DIMENSIONS:
        summaries = [item[dimension.summary_key] for item in request_summaries]
        prefix = dimension.run_field_prefix
        totals[f"{prefix}_marker_count"] = sum(
            summary["marker_count"] for summary in summaries
        )
        totals[f"{prefix}_mention_count"] = sum(
            summary["mention_count"] for summary in summaries
        )
    return totals


def build_run_summary(
    run_dir: str | Path, parser_id: str | None = None
) -> dict[str, Any]:
    run_path = Path(run_dir)
    parser = get_parser(parser_id)
    request_paths = sorted((run_path / "requests").glob("*.json"))
    requests = [json.loads(path.read_text(encoding="utf-8")) for path in request_paths]
    request_summaries = [
        summarize_request(record, parser_id=parser_id) for record in requests
    ]
    primary_index = next(
        (
            index
            for index, item in enumerate(request_summaries)
            if item["body_bytes"] > 0
            and is_generation_request(item)
            and not parser.is_auxiliary_request(item)
        ),
        None,
    )
    if primary_index is None:
        primary_index = next(
            (
                index
                for index, item in enumerate(request_summaries)
                if str(item["method"]).upper() == "POST"
                and item["body_bytes"] > 0
                and not parser.is_auxiliary_request(item)
            ),
            None,
        )
    post_summaries = [
        item for item in request_summaries if str(item["method"]).upper() == "POST"
    ]
    summary = {
        "run_dir": str(run_path),
        "request_count": len(requests),
        "post_request_count": len(post_summaries),
        "primary_request_index": None if primary_index is None else primary_index + 1,
        "primary_request": None
        if primary_index is None
        else request_summaries[primary_index],
        "requests": request_summaries,
        "totals": {
            "body_bytes": sum(item["body_bytes"] for item in request_summaries),
            "body_tokens": sum(item["body_tokens"] for item in request_summaries),
            "skill_count": sum(item["skills"]["count"] for item in request_summaries),
            "tool_count": sum(item["tools"]["count"] for item in request_summaries),
            **_marker_totals(request_summaries),
        },
        "post_totals": {
            "body_bytes": sum(item["body_bytes"] for item in post_summaries),
            "body_tokens": sum(item["body_tokens"] for item in post_summaries),
            "skill_count": sum(item["skills"]["count"] for item in post_summaries),
            "tool_count": sum(item["tools"]["count"] for item in post_summaries),
            **_marker_totals(post_summaries),
        },
    }
    return summary


def summarize_run(run_dir: str | Path, parser_id: str | None = None) -> dict[str, Any]:
    """Load captured requests and return an in-memory analysis summary."""

    return build_run_summary(run_dir, parser_id=parser_id)
