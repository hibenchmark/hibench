from __future__ import annotations

from .base import TextClassification
from .opencode import OpenCodeParser


class OpenHandsParser(OpenCodeParser):
    parser_id = "openhands"

    def classify_text(
        self, path: tuple[str, ...], role: str, text: str
    ) -> TextClassification:
        if path == ("instructions",):
            return TextClassification(
                category="system_prompt", source="main_instructions"
            )
        return super().classify_text(path, role, text)