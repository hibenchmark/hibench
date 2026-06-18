from __future__ import annotations

import re

from .base import ChatRoleParser, SkillEntry


AVAILABLE_SKILLS_RE = re.compile(
    r"\bAvailable skills:\s*(?P<body>[^\n.]+)", re.IGNORECASE
)
SKILL_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]*")


class ClineParser(ChatRoleParser):
    parser_id = "cline"

    def skill_instruction_sections(
        self, path: tuple[str, ...], role: str, text: str
    ) -> list[str]:
        _ = role
        if not path or path[-1].lower() != "description":
            return []
        return [match.group(0).strip() for match in AVAILABLE_SKILLS_RE.finditer(text)]

    def parse_skill_entries(self, text: str) -> list[SkillEntry]:
        match = AVAILABLE_SKILLS_RE.search(text)
        if not match:
            return []
        entries: list[SkillEntry] = []
        seen: set[str] = set()
        for name_match in SKILL_NAME_RE.finditer(match.group("body")):
            name = name_match.group(0).strip()
            if not name or name.lower() in {"and", "or"} or name in seen:
                continue
            seen.add(name)
            entries.append(
                SkillEntry(
                    name=name,
                    description="",
                    file="",
                    text=name,
                )
            )
        return entries
