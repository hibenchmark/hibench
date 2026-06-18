from __future__ import annotations

import re
from typing import Any

from .base import ChatRoleParser, SkillEntry, TextClassification


SKILL_ENTRY_RE = re.compile(r"^- (?P<name>[A-Za-z0-9_.-]+): (?P<body>.*)$")
SKILL_FILE_RE = re.compile(r"^Absolute path:\s*(?P<file>.+)$")


class GrokCliParser(ChatRoleParser):
    parser_id = "grok-cli"

    def classify_text(
        self, path: tuple[str, ...], role: str, text: str
    ) -> TextClassification:
        stripped = text.lstrip().lower()
        if stripped.startswith("<user_info"):
            return TextClassification(
                category="environment_context", source="injected_user_context"
            )
        if stripped.startswith("<system-reminder"):
            if "the following skills are available" in stripped:
                return TextClassification(
                    category="system_prompt", source="skills_instructions"
                )
            return TextClassification(
                category="environment_context", source="injected_user_context"
            )
        return super().classify_text(path, role, text)

    def skill_instruction_sections(
        self, path: tuple[str, ...], role: str, text: str
    ) -> list[str]:
        classification = self.classify_text(path, role, text)
        if classification.source != "skills_instructions":
            return []
        return [text]

    def parse_skill_entries(self, text: str) -> list[SkillEntry]:
        entries: list[SkillEntry] = []
        current_name = ""
        current_description = ""
        current_file = ""
        current_lines: list[str] = []

        def flush() -> None:
            nonlocal current_name, current_description, current_file, current_lines
            if current_name:
                entries.append(
                    SkillEntry(
                        name=current_name,
                        description=current_description,
                        file=current_file,
                        text="\n".join(current_lines).strip(),
                    )
                )
            current_name = ""
            current_description = ""
            current_file = ""
            current_lines = []

        for line in text.splitlines():
            stripped = line.strip()
            match = SKILL_ENTRY_RE.match(stripped)
            if match:
                flush()
                current_name = match.group("name")
                current_description = match.group("body").strip()
                current_lines = [stripped]
                continue

            if not current_name:
                continue

            current_lines.append(line.rstrip())
            file_match = SKILL_FILE_RE.match(stripped)
            if file_match:
                current_file = file_match.group("file").strip()

        flush()
        return entries

    def is_auxiliary_request(self, summary: dict[str, Any]) -> bool:
        tools = summary.get("tools") if isinstance(summary.get("tools"), dict) else {}
        tool_names = set(tools.get("names") or [])
        return tool_names == {"session_title"}
