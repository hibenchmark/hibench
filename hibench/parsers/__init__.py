from __future__ import annotations

from .base import GenericParser, RequestParser
from .claude_code import ClaudeCodeParser
from .cline import ClineParser
from .codex import CodexParser
from .cursor_cli import CursorCliParser
from .devin import DevinParser
from .droid import DroidParser
from .gemini_cli import GeminiCliParser
from .github_cli import GitHubCliParser
from .grok_cli import GrokCliParser
from .hermes import HermesParser
from .kilo import KiloParser
from .mistral_vibe import MistralVibeParser
from .openclaw import OpenClawParser
from .opencode import OpenCodeParser
from .openhands import OpenHandsParser
from .pi import PiParser

DEFAULT_PARSER_ID = "generic"

_PARSERS: dict[str, RequestParser] = {
    "generic": GenericParser(),
    "claude-code": ClaudeCodeParser(),
    "cline": ClineParser(),
    "codex": CodexParser(),
    "cursor-cli": CursorCliParser(),
    "devin": DevinParser(),
    "droid": DroidParser(),
    "gemini-cli": GeminiCliParser(),
    "github-cli": GitHubCliParser(),
    "grok-cli": GrokCliParser(),
    "hermes": HermesParser(),
    "kilo": KiloParser(),
    "mistral-vibe": MistralVibeParser(),
    "openclaw": OpenClawParser(),
    "opencode": OpenCodeParser(),
    "openhands": OpenHandsParser(),
    "pi": PiParser(),
}
_AGENT_PARSER_IDS: dict[str, str] = {
    "claude-code": "claude-code",
    "cline": "cline",
    "codex": "codex",
    "cursor-cli": "cursor-cli",
    "devin": "devin",
    "droid": "droid",
    "gemini-cli": "gemini-cli",
    "github-cli": "github-cli",
    "grok-cli": "grok-cli",
    "hermes": "hermes",
    "kilo": "kilo",
    "mistral-vibe": "mistral-vibe",
    "openclaw": "openclaw",
    "opencode": "opencode",
    "openhands": "openhands",
    "pi": "pi",
}


def get_parser(parser_id: str | None = None) -> RequestParser:
    if parser_id is None:
        return _PARSERS[DEFAULT_PARSER_ID]
    if parser_id not in _PARSERS:
        raise ValueError(f"unknown request parser {parser_id!r}")
    return _PARSERS[parser_id]


def parser_id_for_agent(agent_id: str | None) -> str | None:
    if not agent_id:
        return None
    return _AGENT_PARSER_IDS.get(agent_id)


__all__ = ["DEFAULT_PARSER_ID", "RequestParser", "get_parser", "parser_id_for_agent"]
