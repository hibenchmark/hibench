from __future__ import annotations

import os
from pathlib import Path
import re


ENV_DOTENV_PATH = "HIBENCH_ENV_FILE"
DOTENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _nearest_dotenv_path() -> Path | None:
    for directory in (Path.cwd(), *Path.cwd().parents):
        path = directory / ".env"
        if path.exists():
            return path
    return None


def _dotenv_path(path: str | Path | None = None) -> Path | None:
    raw_path = str(path or os.environ.get(ENV_DOTENV_PATH, "")).strip()
    if raw_path:
        return Path(raw_path).expanduser()
    return _nearest_dotenv_path()


def _unescape_double_quoted_dotenv(value: str) -> str:
    replacements = {
        "\\n": "\n",
        "\\r": "\r",
        "\\t": "\t",
        "\\\\": "\\",
        '\\"': '"',
        "\\$": "$",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    return value


def _dotenv_value(raw: str) -> str:
    value = raw.strip()
    if not value:
        return ""
    if value.startswith("'"):
        end = value.find("'", 1)
        return value[1:end] if end >= 1 else value[1:]
    if value.startswith('"'):
        end = value.find('"', 1)
        quoted = value[1:end] if end >= 1 else value[1:]
        return _unescape_double_quoted_dotenv(quoted)
    return re.sub(r"\s+#.*$", "", value).strip()


def _parse_dotenv_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("export "):
        stripped = stripped[7:].lstrip()
    key, sep, value = stripped.partition("=")
    if not sep:
        return None
    key = key.strip()
    if not DOTENV_KEY_RE.match(key):
        return None
    return key, _dotenv_value(value)


def load_dotenv_file(
    path: str | Path | None = None, *, override: bool = False
) -> Path | None:
    dotenv = _dotenv_path(path)
    if dotenv is None or not dotenv.exists():
        return None
    for line in dotenv.read_text(encoding="utf-8").splitlines():
        parsed = _parse_dotenv_line(line)
        if parsed is None:
            continue
        key, value = parsed
        if override or key not in os.environ:
            os.environ[key] = value
    return dotenv