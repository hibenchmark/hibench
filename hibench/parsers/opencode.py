from __future__ import annotations

import re

from .available_skills import AvailableSkillsXmlMixin
from .base import GenericParser, MarkerEntry, TextClassification


SUBAGENT_LIST_PREFIX = "available agent types and the tools they have access to:"
SUBAGENT_ENTRY_RE = re.compile(
    r"^-\s+(?:\*\*)?(?P<name>[A-Za-z0-9_.-]+)(?:\*\*)?:\s*(?P<body>.*)$"
)


class OpenCodeParser(AvailableSkillsXmlMixin, GenericParser):
    parser_id = "opencode"

    def classify_text(
        self, path: tuple[str, ...], role: str, text: str
    ) -> TextClassification:
        stripped = text.lstrip().lower()
        if stripped.startswith("<system-reminder"):
            return TextClassification(
                category="environment_context", source="injected_user_context"
            )
        if role == "system":
            return TextClassification(
                category="system_prompt", source="main_instructions"
            )
        if role == "user":
            return TextClassification(category="user_prompt", source="user_prompt")
        if role == "assistant":
            return TextClassification(
                category="assistant_context", source="assistant_context"
            )
        if role == "tool":
            return TextClassification(category="tool_context", source="tool_context")
        return TextClassification(category="other_text", source="other_text")

    def parse_marker_entries(
        self, path: tuple[str, ...], text: str
    ) -> list[MarkerEntry]:
        _ = path
        entries: list[MarkerEntry] = []
        in_section = False
        saw_entry = False

        for line in text.splitlines():
            stripped = line.strip()
            lower = stripped.lower().lstrip("#").strip()
            if not in_section:
                if lower.startswith(SUBAGENT_LIST_PREFIX):
                    in_section = True
                continue

            if not stripped:
                if saw_entry:
                    break
                continue

            match = SUBAGENT_ENTRY_RE.match(stripped)
            if not match:
                break

            saw_entry = True
            entries.append(
                MarkerEntry(
                    kind="subagent",
                    name=match.group("name"),
                    description=match.group("body").strip(),
                    text=stripped,
                    source_type="declaration",
                )
            )

        return entries
