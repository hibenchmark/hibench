from __future__ import annotations

from .base import TextClassification
from .opencode import OpenCodeParser


class KiloParser(OpenCodeParser):
    parser_id = "kilo"

    def classify_text(
        self, path: tuple[str, ...], role: str, text: str
    ) -> TextClassification:
        stripped = text.lstrip().lower()
        if stripped.startswith("<environment_details"):
            return TextClassification(
                category="environment_context", source="injected_user_context"
            )
        return super().classify_text(path, role, text)
