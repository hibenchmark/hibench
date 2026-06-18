from __future__ import annotations

import re

from .base import GenericParser, MarkerEntry, SkillEntry, TextClassification


SKILL_ENTRY_RE = re.compile(r"^- (?P<name>[A-Za-z0-9_.-]+): (?P<body>.*)$")
SUBAGENT_ENTRY_RE = re.compile(
    r"^-\s+(?:\*\*)?(?P<name>[A-Za-z0-9_.-]+)(?:\*\*)?:\s*(?P<body>.*)$"
)
SKILL_LIST_PREFIX = "the following skills are available for use with the skill tool:"
SUBAGENT_LIST_PREFIXES = (
    "available agent types and the tools they have access to:",
    "available agent types for the agent tool:",
)


class ClaudeCodeParser(GenericParser):
    parser_id = "claude-code"

    def classify_text(
        self, path: tuple[str, ...], role: str, text: str
    ) -> TextClassification:
        stripped = text.lstrip().lower()
        if SKILL_LIST_PREFIX in stripped:
            return TextClassification(
                category="system_prompt", source="skills_instructions"
            )
        if path and path[0] == "system":
            return TextClassification(
                category="system_prompt", source="main_instructions"
            )
        if stripped.startswith(("<system-reminder", "<environment_context")):
            return TextClassification(
                category="environment_context", source="injected_user_context"
            )
        if role == "system":
            return TextClassification(
                category="system_prompt",
                source=(
                    "skills_instructions"
                    if stripped.startswith(SKILL_LIST_PREFIX)
                    else "main_instructions"
                ),
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

    def parse_skill_entries(self, text: str) -> list[SkillEntry]:
        entries: list[SkillEntry] = []
        section = self._extract_skill_list_section(text)
        current_name = ""
        current_description_lines: list[str] = []
        current_lines: list[str] = []

        def flush() -> None:
            nonlocal current_name, current_description_lines, current_lines
            if current_name:
                entries.append(
                    SkillEntry(
                        name=current_name,
                        description=" ".join(current_description_lines).strip(),
                        file="",
                        text="\n".join(current_lines).strip(),
                    )
                )
            current_name = ""
            current_description_lines = []
            current_lines = []

        for line in section.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("</system-reminder"):
                break
            match = SKILL_ENTRY_RE.match(line.strip())
            if match:
                flush()
                current_name = match.group("name")
                current_description_lines = [match.group("body").strip()]
                current_lines = [stripped]
                continue

            if not current_name:
                continue
            current_lines.append(line.rstrip())
            if stripped:
                current_description_lines.append(stripped)

        flush()
        return entries

    def skill_instruction_sections(
        self, path: tuple[str, ...], role: str, text: str
    ) -> list[str]:
        classification = self.classify_text(path, role, text)
        if classification.source != "skills_instructions":
            return []
        return [text]

    @staticmethod
    def _extract_skill_list_section(text: str) -> str:
        start = text.lower().find(SKILL_LIST_PREFIX)
        if start < 0:
            return ""
        return text[start + len(SKILL_LIST_PREFIX) :]

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
                if any(lower.startswith(prefix) for prefix in SUBAGENT_LIST_PREFIXES):
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
