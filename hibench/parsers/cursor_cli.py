from __future__ import annotations

import re

from .base import ChatRoleParser, MarkerEntry, TextClassification


SUBAGENT_ONE_OF_RE = re.compile(r"Must be one of:\s*(?P<names>[^.]+)\.", re.I)


class CursorCliParser(ChatRoleParser):
    parser_id = "cursor-cli"

    def classify_text(
        self, path: tuple[str, ...], role: str, text: str
    ) -> TextClassification:
        stripped = text.lstrip().lower()
        if stripped.startswith(("<user_info", "<git_status", "<agent_transcripts")):
            return TextClassification(
                category="environment_context", source="injected_user_context"
            )
        if stripped.startswith("<user_query"):
            return TextClassification(category="user_prompt", source="user_prompt")
        return super().classify_text(path, role, text)

    def parse_marker_entries(
        self, path: tuple[str, ...], text: str
    ) -> list[MarkerEntry]:
        if path[-4:] != (
            "parameters",
            "properties",
            "subagent_type",
            "description",
        ):
            return []
        match = SUBAGENT_ONE_OF_RE.search(text)
        if not match:
            return []
        names = [
            name.strip(" `\"'")
            for name in match.group("names").split(",")
            if name.strip(" `\"'")
        ]
        return [
            MarkerEntry(
                kind="subagent",
                name=name,
                description="Cursor CLI Task tool subagent type",
                text=name,
            )
            for name in names
        ]
