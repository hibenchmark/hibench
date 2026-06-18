from __future__ import annotations

import html
import re

from .base import SkillEntry


AVAILABLE_SKILLS_RE = re.compile(
    r"<available_skills\b[^>]*>.*?</available_skills>",
    re.IGNORECASE | re.DOTALL,
)
AVAILABLE_SKILLS_WITH_IMMEDIATE_SKILL_RE = re.compile(
    r"<available_skills\b[^>]*>\s*<skill\b.*?</available_skills>",
    re.IGNORECASE | re.DOTALL,
)
SKILL_RE = re.compile(
    r"<skill\b[^>]*>.*?</skill>",
    re.IGNORECASE | re.DOTALL,
)
TAG_RE = re.compile(
    r"<(?P<tag>name|description|location|path)\b[^>]*>(?P<value>.*?)</(?P=tag)>",
    re.IGNORECASE | re.DOTALL,
)


def available_skill_sections(
    text: str, *, require_immediate_skill: bool = False
) -> list[str]:
    pattern = (
        AVAILABLE_SKILLS_WITH_IMMEDIATE_SKILL_RE
        if require_immediate_skill
        else AVAILABLE_SKILLS_RE
    )
    return [match.group(0) for match in pattern.finditer(text)]


def available_skill_tag_values(text: str) -> dict[str, str]:
    return {
        match.group("tag").lower(): html.unescape(match.group("value").strip())
        for match in TAG_RE.finditer(text)
    }


def parse_available_skill_entries(text: str) -> list[SkillEntry]:
    entries: list[SkillEntry] = []
    for match in SKILL_RE.finditer(text):
        item = match.group(0).strip()
        tags = available_skill_tag_values(item)
        name = tags.get("name", "")
        description = tags.get("description", "")
        if not name or not description:
            continue
        entries.append(
            SkillEntry(
                name=name,
                description=description,
                file=tags.get("location") or tags.get("path", ""),
                text=item,
            )
        )
    return entries


class AvailableSkillsXmlMixin:
    require_immediate_skill = False

    def skill_instruction_sections(
        self, path: tuple[str, ...], role: str, text: str
    ) -> list[str]:
        _ = (path, role)
        return available_skill_sections(
            text, require_immediate_skill=self.require_immediate_skill
        )

    def parse_skill_entries(self, text: str) -> list[SkillEntry]:
        return parse_available_skill_entries(text)
