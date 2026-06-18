from __future__ import annotations

import re

from .available_skills import AvailableSkillsXmlMixin
from .base import GenericParser, MarkerEntry


SUBAGENT_LIST_PREFIX = "available agent types:"
SUBAGENT_ENTRY_RE = re.compile(
    r"^-\s+(?:\*\*)?(?P<name>[A-Za-z0-9_.-]+)(?:\*\*)?:\s*(?P<body>.*)$"
)


class GitHubCliParser(AvailableSkillsXmlMixin, GenericParser):
    parser_id = "github-cli"

    def parse_marker_entries(
        self, path: tuple[str, ...], text: str
    ) -> list[MarkerEntry]:
        _ = path
        entries: list[MarkerEntry] = []
        in_section = False

        for line in text.splitlines():
            stripped = line.strip()
            lower = stripped.lower().lstrip("#").strip()
            if not in_section:
                if lower.startswith(SUBAGENT_LIST_PREFIX):
                    in_section = True
                continue

            if not stripped:
                continue

            match = SUBAGENT_ENTRY_RE.match(stripped)
            if not match:
                break

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
