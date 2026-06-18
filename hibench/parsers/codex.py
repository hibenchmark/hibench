from __future__ import annotations

import re

from .base import GenericParser, MarkerEntry, SkillEntry, TextClassification


SKILL_ENTRY_RE = re.compile(
    r"^- (?P<name>[A-Za-z0-9_.-]+): (?P<body>.*?)(?: \(file: (?P<file>[^)]+)\))?$"
)


class CodexParser(GenericParser):
    parser_id = "codex"

    def classify_text(
        self, path: tuple[str, ...], role: str, text: str
    ) -> TextClassification:
        return TextClassification(
            category=self._classify_text_category(path, role, text),
            source=self._classify_text_source(path, role, text),
        )

    def parse_skill_entries(self, text: str) -> list[SkillEntry]:
        entries: list[SkillEntry] = []
        section = self._extract_available_skills_section(text)
        for line in section.splitlines():
            stripped = line.strip()
            match = SKILL_ENTRY_RE.match(stripped)
            if not match:
                continue
            entries.append(
                SkillEntry(
                    name=match.group("name"),
                    description=match.group("body").strip(),
                    file=match.group("file") or "",
                    text=stripped,
                )
            )
        return entries

    def skill_instruction_sections(
        self, path: tuple[str, ...], role: str, text: str
    ) -> list[str]:
        classification = self.classify_text(path, role, text)
        if classification.source != "skills_instructions":
            return []
        return [text]

    def parse_marker_entries(
        self, path: tuple[str, ...], text: str
    ) -> list[MarkerEntry]:
        _ = (path, text)
        return []

    @staticmethod
    def _classify_text_source(path: tuple[str, ...], role: str, text: str) -> str:
        stripped = text.lstrip().lower()
        if path == ("instructions",):
            return "main_instructions"
        if stripped.startswith("<environment_context"):
            return "injected_user_context"
        if role == "developer":
            if stripped.startswith("<permissions instructions>"):
                return "permissions_instructions"
            if stripped.startswith("<skills_instructions>"):
                return "skills_instructions"
            return "developer_instructions"
        if role == "system":
            return "system_message"
        if role == "user":
            return "user_prompt"
        if role == "assistant":
            return "assistant_context"
        if role == "tool":
            return "tool_context"
        return "other_text"

    @staticmethod
    def _classify_text_category(path: tuple[str, ...], role: str, text: str) -> str:
        key = path[-1].lower() if path else ""
        if text.lstrip().lower().startswith("<environment_context"):
            return "environment_context"
        if path == ("input",):
            return "user_prompt"
        if key in {"developer", "instructions", "system"} or role in {
            "developer",
            "system",
        }:
            return "system_prompt"
        if role == "user":
            return "user_prompt"
        if role == "assistant":
            return "assistant_context"
        if role == "tool":
            return "tool_context"
        return "other_text"

    @staticmethod
    def _extract_available_skills_section(text: str) -> str:
        start = text.find("### Available skills")
        if start < 0:
            return text
        end = text.find("### How to use skills", start)
        return text[start:] if end < 0 else text[start:end]
