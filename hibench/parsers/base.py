from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class TextClassification:
    category: str
    source: str


@dataclass(frozen=True)
class SkillEntry:
    name: str
    description: str
    file: str
    text: str


@dataclass(frozen=True)
class MarkerEntry:
    kind: str
    name: str
    description: str
    text: str
    source_type: str = "declaration"


class RequestParser(Protocol):
    parser_id: str

    def normalize_body(self, record: dict[str, Any], body: Any) -> Any: ...

    def classify_text(
        self, path: tuple[str, ...], role: str, text: str
    ) -> TextClassification: ...

    def skill_instruction_sections(
        self, path: tuple[str, ...], role: str, text: str
    ) -> list[str]: ...

    def parse_skill_entries(self, text: str) -> list[SkillEntry]: ...

    def parse_marker_entries(
        self, path: tuple[str, ...], text: str
    ) -> list[MarkerEntry]: ...

    def is_auxiliary_request(self, summary: dict[str, Any]) -> bool: ...


class GenericParser:
    parser_id = "generic"

    def normalize_body(self, record: dict[str, Any], body: Any) -> Any:
        _ = record
        return body

    def classify_text(
        self, path: tuple[str, ...], role: str, text: str
    ) -> TextClassification:
        _ = text
        key = path[-1].lower() if path else ""
        if path == ("instructions",):
            source = "main_instructions"
        elif role == "developer":
            source = "developer_instructions"
        elif role == "system":
            source = "system_message"
        elif role == "user":
            source = "user_prompt"
        elif role == "assistant":
            source = "assistant_context"
        elif role == "tool":
            source = "tool_context"
        else:
            source = "other_text"

        if path == ("input",):
            category = "user_prompt"
        elif key in {"developer", "instructions", "system"} or role in {
            "developer",
            "system",
        }:
            category = "system_prompt"
        elif role == "user":
            category = "user_prompt"
        elif role == "assistant":
            category = "assistant_context"
        elif role == "tool":
            category = "tool_context"
        else:
            category = "other_text"

        return TextClassification(category=category, source=source)

    def parse_skill_entries(self, text: str) -> list[SkillEntry]:
        _ = text
        return []

    def skill_instruction_sections(
        self, path: tuple[str, ...], role: str, text: str
    ) -> list[str]:
        _ = (path, role, text)
        return []

    def parse_marker_entries(
        self, path: tuple[str, ...], text: str
    ) -> list[MarkerEntry]:
        _ = (path, text)
        return []

    def is_auxiliary_request(self, summary: dict[str, Any]) -> bool:
        _ = summary
        return False


class ChatRoleParser(GenericParser):
    """Parser for chat payloads where roles map directly to benchmark sources."""

    def classify_text(
        self, path: tuple[str, ...], role: str, text: str
    ) -> TextClassification:
        _ = (path, text)
        if role in {"system", "developer"}:
            return TextClassification(
                category="system_prompt", source="main_instructions"
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
