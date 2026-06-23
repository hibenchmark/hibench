from __future__ import annotations

from copy import deepcopy
import html
import re
from typing import Any

from .available_skills import AvailableSkillsXmlMixin
from .base import GenericParser, MarkerEntry, TextClassification


MODEL_PATH_RE = re.compile(
    r"/models/(?P<model>[^/:?]+):(?:generateContent|streamGenerateContent|countTokens)"
)
AVAILABLE_SUBAGENTS_RE = re.compile(
    r"<available_subagents\b[^>]*>.*?</available_subagents>",
    re.IGNORECASE | re.DOTALL,
)
SUBAGENT_RE = re.compile(
    r"<subagent\b[^>]*>.*?</subagent>",
    re.IGNORECASE | re.DOTALL,
)
SUBAGENT_TAG_RE = re.compile(
    r"<(?P<tag>name|description)\b[^>]*>(?P<value>.*?)</(?P=tag)>",
    re.IGNORECASE | re.DOTALL,
)
LEGACY_SESSION_PREFIX = "This is the Gemini CLI. We are setting up the context for our chat."


def _model_from_path(path: str) -> str:
    match = MODEL_PATH_RE.search(path.split("?", 1)[0])
    return match.group("model") if match else ""


def _subagent_tag_values(text: str) -> dict[str, str]:
    return {
        match.group("tag").lower(): html.unescape(match.group("value").strip())
        for match in SUBAGENT_TAG_RE.finditer(text)
    }


class GeminiCliParser(AvailableSkillsXmlMixin, GenericParser):
    parser_id = "gemini-cli"

    def normalize_body(self, record: dict[str, Any], body: Any) -> Any:
        if not isinstance(body, dict):
            return body

        normalized = deepcopy(body)
        model = _model_from_path(str(record.get("path") or ""))
        if model and not normalized.get("model"):
            normalized["model"] = model

        function_declarations: list[dict[str, Any]] = []
        raw_tools = body.get("tools")
        if isinstance(raw_tools, list):
            for tool in raw_tools:
                if not isinstance(tool, dict):
                    continue
                declarations = tool.get("functionDeclarations")
                if not isinstance(declarations, list):
                    continue
                for declaration in declarations:
                    if not isinstance(declaration, dict):
                        continue
                    function_declarations.append(
                        {"type": "function", **deepcopy(declaration)}
                    )
        if function_declarations:
            normalized["tools"] = function_declarations

        return normalized

    def classify_text(
        self, path: tuple[str, ...], role: str, text: str
    ) -> TextClassification:
        if path and path[0] == "systemInstruction":
            return TextClassification(
                category="system_prompt", source="main_instructions"
            )
        stripped = text.lstrip()
        if stripped.startswith("<session_context>") or stripped.startswith(
            LEGACY_SESSION_PREFIX
        ):
            return TextClassification(
                category="environment_context", source="injected_user_context"
            )
        if role == "user":
            return TextClassification(category="user_prompt", source="user_prompt")
        if role == "model":
            return TextClassification(
                category="assistant_context", source="assistant_context"
            )
        return super().classify_text(path, role, text)

    def parse_marker_entries(
        self, path: tuple[str, ...], text: str
    ) -> list[MarkerEntry]:
        _ = path
        entries: list[MarkerEntry] = []
        for section_match in AVAILABLE_SUBAGENTS_RE.finditer(text):
            section = section_match.group(0)
            for subagent_match in SUBAGENT_RE.finditer(section):
                item = subagent_match.group(0).strip()
                tags = _subagent_tag_values(item)
                name = tags.get("name", "")
                description = tags.get("description", "")
                if not name or not description:
                    continue
                entries.append(
                    MarkerEntry(
                        kind="subagent",
                        name=name,
                        description=description,
                        text=item,
                        source_type="declaration",
                    )
                )
        return entries

    def is_auxiliary_request(self, summary: dict[str, Any]) -> bool:
        path = str(summary.get("path") or "").split("?", 1)[0]
        return path.endswith(":countTokens")