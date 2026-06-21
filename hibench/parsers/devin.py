from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

from .base import GenericParser, MarkerEntry, SkillEntry, TextClassification


GET_CHAT_MESSAGE_PATH = "/exa.api_server_pb.ApiServerService/GetChatMessage"
AVAILABLE_SKILLS_RE = re.compile(
    r"<available_skills\b[^>]*>.*?</available_skills>",
    re.IGNORECASE | re.DOTALL,
)
DEVIN_SKILL_RE = re.compile(r"^-\s+\*\*(?P<name>[^*]+)\*\*:\s*(?P<body>.+)$")
SOURCE_SUFFIX_RE = re.compile(r"\s+\(source:\s*(?P<source>[^)]+)\)\s*$")
TOOL_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,40}$")
UUIDISH_RE = re.compile(r"^\$?[0-9a-f]{8}-[0-9a-f-]{27,}$", re.IGNORECASE)
LONG_HEX_RE = re.compile(r"^[0-9a-f]{64,}$", re.IGNORECASE)
SUBAGENT_PROFILE_ENTRY_RE = re.compile(
    r"^-\s+`(?P<name>subagent_[^`]+)`:\s*(?P<body>.*)$"
)
AUXILIARY_PATH_FRAGMENTS = (
    "ProductAnalyticsService/",
    "SeatManagementService/",
    "ApiServerService/GetCliModelConfigs",
    "/telemetry/",
    "/v3/self",
)


def _is_printable_text_char(char: str) -> bool:
    return (
        char in "\n\r\t"
        or char != "\ufffd"
        and char.isprintable()
        and not unicodedata.category(char).startswith("C")
    )


def _extract_printable_sequences(text: str) -> list[str]:
    sequences: list[str] = []
    current: list[str] = []
    for char in text:
        if _is_printable_text_char(char):
            current.append(char)
            continue
        if current:
            item = "".join(current).strip()
            if item:
                sequences.append(item)
            current = []
    if current:
        item = "".join(current).strip()
        if item:
            sequences.append(item)
    return sequences


def _sequence_index(sequences: list[str], needle: str) -> int | None:
    for index, text in enumerate(sequences):
        if needle in text:
            return index
    return None


def _first_sequence_with(sequences: list[str], needle: str) -> str:
    index = _sequence_index(sequences, needle)
    return "" if index is None else sequences[index]


def _clean_tool_name(text: str) -> str:
    candidate = text.strip().splitlines()[-1].strip()
    candidate = re.sub(r"^[^A-Za-z_]+", "", candidate)
    candidate = re.sub(r"[^A-Za-z0-9_]+$", "", candidate)
    return candidate


def _is_tool_name(text: str) -> bool:
    return bool(TOOL_NAME_RE.fullmatch(text)) and text not in {
        "chisel",
        "linux",
    }


def _clean_description(text: str) -> str:
    description = text.strip()
    if (
        len(description) > 1
        and description[0] in {"H", "N", "R", "<", ">"}
        and description[1].isupper()
    ):
        description = description[1:]
    return description.strip()


def _extract_available_skills(body: str, sequences: list[str]) -> str:
    match = AVAILABLE_SKILLS_RE.search(body)
    if match:
        return match.group(0).strip()
    return _first_sequence_with(sequences, "<available_skills>")


def _schema_value(text: str) -> Any:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return text.strip()
    payload = text[start : end + 1]
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return payload


def _extract_tools(sequences: list[str], start_index: int) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    seen: set[str] = set()
    index = start_index
    while index < len(sequences) - 2:
        name = _clean_tool_name(sequences[index])
        description = _clean_description(sequences[index + 1])
        schema_text = sequences[index + 2]
        if (
            _is_tool_name(name)
            and name not in seen
            and len(description) > 20
            and "{" in schema_text
        ):
            seen.add(name)
            tools.append(
                {
                    "type": "function",
                    "name": name,
                    "description": description,
                    "parameters": _schema_value(schema_text),
                }
            )
            index += 3
            continue
        index += 1
    return tools


def _extract_user_prompt(sequences: list[str], env_index: int | None) -> str:
    start = 0 if env_index is None else env_index + 1
    skills_index = _sequence_index(sequences, "<available_skills>")
    end = len(sequences) if skills_index is None else skills_index
    for text in sequences[start:end]:
        candidate = text.strip()
        if not candidate or UUIDISH_RE.fullmatch(candidate) or LONG_HEX_RE.fullmatch(
            candidate
        ):
            continue
        if "$" in candidate and re.search(r"[0-9a-f]{8}-[0-9a-f-]{27,}", candidate):
            continue
        if 0 < len(candidate) <= 200 and any(char.isalpha() for char in candidate):
            return "Hi" if candidate == "Hi8" else candidate
    return ""


def _extract_model(sequences: list[str]) -> str | None:
    for text in reversed(sequences):
        candidate = text.strip()
        if candidate.startswith("swe-"):
            return candidate
    return None


class DevinParser(GenericParser):
    parser_id = "devin"

    def normalize_body(self, record: dict[str, Any], body: Any) -> Any:
        if not isinstance(body, str):
            return body
        path = str(record.get("path") or "")
        if GET_CHAT_MESSAGE_PATH not in path:
            return body

        sequences = _extract_printable_sequences(body)
        instructions = _first_sequence_with(sequences, "You are Devin,")
        if not instructions:
            instructions = _first_sequence_with(
                sequences, "You are a session title generator."
            )
        env_index = _sequence_index(sequences, "<system_info>")
        skills_index = _sequence_index(sequences, "<available_skills>")
        tool_start_index = 0 if skills_index is None else skills_index + 1

        messages = []
        user_prompt = _extract_user_prompt(sequences, env_index)
        if user_prompt:
            messages.append({"role": "user", "content": user_prompt})

        normalized: dict[str, Any] = {
            "model": _extract_model(sequences),
            "instructions": instructions,
            "messages": messages,
            "environment_context": {
                "role": "system",
                "content": _first_sequence_with(sequences, "<system_info>"),
            },
            "skills": {
                "role": "system",
                "content": _extract_available_skills(body, sequences),
            },
            "tools": _extract_tools(sequences, tool_start_index),
        }
        return normalized

    def classify_text(
        self, path: tuple[str, ...], role: str, text: str
    ) -> TextClassification:
        _ = text
        if path == ("instructions",):
            return TextClassification(
                category="system_prompt", source="main_instructions"
            )
        if path[:1] == ("environment_context",):
            return TextClassification(
                category="environment_context", source="injected_user_context"
            )
        if path[:1] == ("skills",):
            return TextClassification(
                category="system_prompt", source="skills_instructions"
            )
        if role == "user":
            return TextClassification(category="user_prompt", source="user_prompt")
        if role == "assistant":
            return TextClassification(
                category="assistant_context", source="assistant_context"
            )
        return TextClassification(category="other_text", source="other_text")

    def skill_instruction_sections(
        self, path: tuple[str, ...], role: str, text: str
    ) -> list[str]:
        _ = (path, role)
        return [match.group(0) for match in AVAILABLE_SKILLS_RE.finditer(text)]

    def parse_skill_entries(self, text: str) -> list[SkillEntry]:
        entries: list[SkillEntry] = []
        for line in text.splitlines():
            match = DEVIN_SKILL_RE.match(line.strip())
            if not match:
                continue
            body = match.group("body").strip()
            source = ""
            source_match = SOURCE_SUFFIX_RE.search(body)
            if source_match:
                source = source_match.group("source").strip()
                body = SOURCE_SUFFIX_RE.sub("", body).strip()
            entries.append(
                SkillEntry(
                    name=match.group("name").strip(),
                    description=body,
                    file=source,
                    text=line.strip(),
                )
            )
        return entries

    def parse_marker_entries(
        self, path: tuple[str, ...], text: str
    ) -> list[MarkerEntry]:
        _ = path
        entries: list[MarkerEntry] = []
        for line in text.splitlines():
            match = SUBAGENT_PROFILE_ENTRY_RE.match(line.strip())
            if not match:
                continue
            entries.append(
                MarkerEntry(
                    kind="subagent",
                    name=match.group("name"),
                    description=match.group("body").strip(),
                    text=line.strip(),
                    source_type="declaration",
                )
            )
        return entries

    def is_auxiliary_request(self, summary: dict[str, Any]) -> bool:
        path = str(summary.get("path") or "")
        if any(fragment in path for fragment in AUXILIARY_PATH_FRAGMENTS):
            return True
        if GET_CHAT_MESSAGE_PATH not in path:
            return False
        fields = summary.get("text_fields", {}).get("fields", [])
        return any(
            "session title generator" in str(field.get("preview") or "").lower()
            for field in fields
        )