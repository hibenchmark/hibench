from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from .available_skills import AvailableSkillsXmlMixin
from .base import ChatRoleParser, TextClassification


OPENCLAW_TIMESTAMP_PROMPT_RE = re.compile(
    r"^\[(?P<context>[A-Z][a-z]{2}\s+\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\s+UTC)\]\s+"
    r"(?P<prompt>\S.*)$"
)
OPENCLAW_TIMESTAMP_CONTEXT_RE = re.compile(
    r"^\[[A-Z][a-z]{2}\s+\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\s+UTC\]$"
)


def _split_timestamp_prompt(text: str) -> tuple[str, str] | None:
    match = OPENCLAW_TIMESTAMP_PROMPT_RE.match(text.strip())
    if not match:
        return None
    return f"[{match.group('context')}]", match.group("prompt")


class OpenClawParser(AvailableSkillsXmlMixin, ChatRoleParser):
    parser_id = "openclaw"
    require_immediate_skill = True

    def normalize_body(self, record: dict[str, Any], body: Any) -> Any:
        _ = record
        if not isinstance(body, dict):
            return body

        normalized = deepcopy(body)
        input_items = normalized.get("input")
        if not isinstance(input_items, list):
            return normalized

        for message in input_items:
            if (
                not isinstance(message, dict)
                or str(message.get("role") or "").lower() != "user"
            ):
                continue

            content = message.get("content")
            if not isinstance(content, list):
                continue

            normalized_content: list[Any] = []
            changed = False
            for item in content:
                if (
                    isinstance(item, dict)
                    and isinstance(item.get("text"), str)
                    and (parts := _split_timestamp_prompt(item["text"]))
                ):
                    context, prompt = parts
                    normalized_content.append({**item, "text": context})
                    normalized_content.append({**item, "text": prompt})
                    changed = True
                    continue
                normalized_content.append(item)

            if changed:
                message["content"] = normalized_content

        return normalized

    def classify_text(
        self, path: tuple[str, ...], role: str, text: str
    ) -> TextClassification:
        if role == "user" and OPENCLAW_TIMESTAMP_CONTEXT_RE.match(text.strip()):
            return TextClassification(
                category="environment_context", source="injected_user_context"
            )
        return super().classify_text(path, role, text)

    def count_marker_tool_declaration(
        self, kind: str, path: tuple[str, ...], node: dict[str, Any]
    ) -> bool:
        _ = (path, node)
        return kind != "subagent"
