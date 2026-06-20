from __future__ import annotations

import re

from .base import ChatRoleParser, SkillEntry, TextClassification


SKILL_ENTRY_RE = re.compile(r"^(?P<name>[A-Za-z0-9_.-]+):\s*(?P<body>.*)$")


class DroidParser(ChatRoleParser):
    parser_id = "droid"

    def classify_text(
        self, path: tuple[str, ...], role: str, text: str
    ) -> TextClassification:
        if path == ("instructions",):
            return TextClassification(
                category="system_prompt", source="main_instructions"
            )

        stripped = text.lstrip()
        lower = stripped.lower()
        if stripped.startswith("<system-reminder"):
            if (
                "available skills for the skill tool" in lower
                or "\navailable skills:" in lower
            ):
                return TextClassification(
                    category="system_prompt", source="skills_instructions"
                )
            if (
                "deferred tools:" in lower
                or "todowrite was not called yet" in lower
            ):
                return TextClassification(
                    category="system_prompt", source="developer_instructions"
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
        in_skills = False
        current_name = ""
        current_description = ""
        current_lines: list[str] = []
        saw_blank_after_entry = False

        def flush() -> None:
            nonlocal current_name, current_description, current_lines
            if current_name:
                entries.append(
                    SkillEntry(
                        name=current_name,
                        description=current_description.strip(),
                        file="",
                        text="\n".join(current_lines).strip(),
                    )
                )
            current_name = ""
            current_description = ""
            current_lines = []

        for line in text.splitlines():
            stripped = line.strip()
            if stripped == "Available skills:":
                in_skills = True
                continue
            if not in_skills:
                continue
            if stripped.startswith("</system-reminder>"):
                break

            if current_name and not stripped:
                saw_blank_after_entry = True
                continue

            match = SKILL_ENTRY_RE.match(stripped)
            if match:
                flush()
                current_name = match.group("name")
                current_description = match.group("body").strip()
                current_lines = [stripped]
                saw_blank_after_entry = False
                continue

            if current_name and stripped:
                if saw_blank_after_entry:
                    break
                current_description = f"{current_description} {stripped}".strip()
                current_lines.append(stripped)

        flush()
        return entries