from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = ROOT / "agents"


@dataclass(frozen=True)
class AgentSpec:
    id: str
    display_name: str
    version: str
    image: str
    parser_id: str
    version_source: dict[str, Any] | None
    version_build_arg: str
    dockerfile: Path
    command: list[str]
    env: dict[str, str]
    raw: dict[str, Any]


def image_for_version(
    agent_id: str, image: str, default_version: str, version: str
) -> str:
    if "{version}" in image:
        return image.replace("{version}", version)
    if default_version and image.endswith(f":{default_version}"):
        return image[: -len(default_version)] + version
    return f"hibench/{agent_id}:{version}"


def default_version_build_arg(agent_id: str) -> str:
    return f"{agent_id.upper().replace('-', '_')}_VERSION"


def list_agent_ids() -> list[str]:
    if not AGENTS_DIR.exists():
        return []
    return sorted(
        path.name for path in AGENTS_DIR.iterdir() if (path / "agent.json").exists()
    )


def load_agent(agent_id: str, version: str | None = None) -> AgentSpec:
    path = AGENTS_DIR / agent_id / "agent.json"
    if not path.exists():
        known = ", ".join(list_agent_ids()) or "<none>"
        raise ValueError(f"unknown agent {agent_id!r}; known agents: {known}")

    raw = json.loads(path.read_text(encoding="utf-8"))
    required = [
        "id",
        "display_name",
        "version",
        "image",
        "dockerfile",
        "command",
        "env",
    ]
    missing = [key for key in required if key not in raw]
    if missing:
        raise ValueError(f"{path} is missing required keys: {', '.join(missing)}")

    default_version = str(raw["version"])
    effective_version = str(version or default_version)
    image = image_for_version(
        agent_id, str(raw["image"]), default_version, effective_version
    )

    return AgentSpec(
        id=str(raw["id"]),
        display_name=str(raw["display_name"]),
        version=effective_version,
        image=image,
        parser_id=str(raw.get("parser_id") or "generic"),
        version_source=(
            {str(key): value for key, value in raw["version_source"].items()}
            if isinstance(raw.get("version_source"), dict)
            else None
        ),
        version_build_arg=str(
            raw.get("version_build_arg") or default_version_build_arg(agent_id)
        ),
        dockerfile=ROOT / str(raw["dockerfile"]),
        command=[str(part) for part in raw["command"]],
        env={str(key): str(value) for key, value in raw["env"].items()},
        raw=raw,
    )
