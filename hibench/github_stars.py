from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .agents import load_agent
from .env_config import load_dotenv_file


SCHEMA_VERSION = "hibench.github_stars.v1"
DEFAULT_API_BASE_URL = "https://api.github.com"
ENV_ENABLED = "HIBENCH_GITHUB_STARS"
ENV_API_BASE_URL = "HIBENCH_GITHUB_API_BASE_URL"
TOKEN_ENV_NAMES = ("GITHUB_TOKEN", "GH_TOKEN")


@dataclass(frozen=True)
class AgentLinks:
    official_url: str = ""
    github_repo: str = ""

    @property
    def github_url(self) -> str:
        return f"https://github.com/{self.github_repo}" if self.github_repo else ""


@dataclass(frozen=True)
class GitHubStarsUpdateResult:
    agent_id: str
    status: str
    github_repo: str = ""
    github_url: str = ""
    github_stars: int | None = None
    updated_at: str = ""
    error: str = ""

    @property
    def updated(self) -> bool:
        return self.status == "updated"

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "status": self.status,
            "github_repo": self.github_repo,
            "github_url": self.github_url,
            "github_stars": self.github_stars,
            "updated_at": self.updated_at,
            "error": self.error,
        }


def _env_disabled(value: str) -> bool:
    return value.strip().lower() in {"0", "false", "no", "off", "disabled"}


def utc_now_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def agent_links(agent_id: str) -> AgentLinks:
    spec = load_agent(agent_id)
    links = spec.raw.get("links") if isinstance(spec.raw.get("links"), dict) else {}
    return AgentLinks(
        official_url=str(links.get("official_url") or ""),
        github_repo=str(links.get("github_repo") or ""),
    )


def eligible_agent_ids(agent_ids: list[str]) -> list[str]:
    return [agent_id for agent_id in agent_ids if agent_links(agent_id).github_repo]


def github_stars_settings_from_env() -> dict[str, Any]:
    dotenv = load_dotenv_file()
    disabled = _env_disabled(os.environ.get(ENV_ENABLED, ""))
    token_env = next((name for name in TOKEN_ENV_NAMES if os.environ.get(name)), "")
    return {
        "enabled": not disabled,
        "disabled_reason": (
            f"{ENV_ENABLED} disabled automatic fetching" if disabled else ""
        ),
        "api_base_url": os.environ.get(ENV_API_BASE_URL, DEFAULT_API_BASE_URL),
        "token_env": token_env,
        "token_present": bool(token_env),
        "dotenv_path": str(dotenv) if dotenv is not None else "",
    }


def _github_token_from_env() -> str:
    for name in TOKEN_ENV_NAMES:
        value = os.environ.get(name, "")
        if value:
            return value
    return ""


def _repo_api_url(api_base_url: str, repo: str) -> str:
    owner, sep, name = repo.strip().partition("/")
    if not sep or not owner or not name:
        raise ValueError(f"GitHub repo must be owner/name, got {repo!r}")
    return (
        api_base_url.rstrip("/")
        + "/repos/"
        + quote(owner, safe="")
        + "/"
        + quote(name, safe="")
    )


def fetch_github_stars(
    repo: str,
    *,
    api_base_url: str = DEFAULT_API_BASE_URL,
    token: str = "",
    timeout: int = 30,
) -> int:
    headers = {
        "accept": "application/vnd.github+json",
        "user-agent": "hibench-github-stars",
        "x-github-api-version": "2022-11-28",
    }
    if token:
        headers["authorization"] = f"Bearer {token}"
    request = Request(_repo_api_url(api_base_url, repo), headers=headers, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GitHub stars fetch failed for {repo} with HTTP {error.code}: {detail}"
        ) from error
    except URLError as error:
        raise RuntimeError(f"GitHub stars fetch failed for {repo}: {error}") from error
    stars = payload.get("stargazers_count") if isinstance(payload, dict) else None
    if not isinstance(stars, int):
        raise ValueError(f"GitHub response for {repo} missing stargazers_count")
    return stars


def load_github_stars(path: str | Path) -> dict[str, Any]:
    stars_path = Path(path)
    if not stars_path.exists():
        return {"schema_version": SCHEMA_VERSION, "updated_at": "", "agents": {}}
    data = json.loads(stars_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{stars_path} does not contain a JSON object")
    agents = data.get("agents")
    if not isinstance(agents, dict):
        data["agents"] = {}
    data["schema_version"] = str(data.get("schema_version") or SCHEMA_VERSION)
    data["updated_at"] = str(data.get("updated_at") or "")
    return data


def write_github_stars(path: str | Path, data: dict[str, Any]) -> None:
    stars_path = Path(path)
    stars_path.parent.mkdir(parents=True, exist_ok=True)
    ordered = {
        "schema_version": str(data.get("schema_version") or SCHEMA_VERSION),
        "updated_at": str(data.get("updated_at") or ""),
        "agents": data.get("agents") if isinstance(data.get("agents"), dict) else {},
    }
    temp_path = stars_path.with_suffix(stars_path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(ordered, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(stars_path)


class GitHubStarsUpdater:
    def __init__(
        self,
        *,
        out_dir: str | Path = "results",
        api_base_url: str = DEFAULT_API_BASE_URL,
        token: str = "",
        fetcher=fetch_github_stars,
    ) -> None:
        self.out_dir = Path(out_dir)
        self.api_base_url = api_base_url
        self.token = token
        self.fetcher = fetcher
        self._attempted_agent_ids: set[str] = set()

    @property
    def stars_path(self) -> Path:
        return self.out_dir / "github_stars.json"

    def update_agent(self, agent_id: str) -> GitHubStarsUpdateResult:
        links = agent_links(agent_id)
        if not links.github_repo:
            return GitHubStarsUpdateResult(agent_id=agent_id, status="not_eligible")
        if agent_id in self._attempted_agent_ids:
            return GitHubStarsUpdateResult(
                agent_id=agent_id,
                status="already_attempted",
                github_repo=links.github_repo,
                github_url=links.github_url,
            )
        self._attempted_agent_ids.add(agent_id)

        try:
            stars = int(
                self.fetcher(
                    links.github_repo,
                    api_base_url=self.api_base_url,
                    token=self.token,
                )
            )
            updated_at = utc_now_iso()
            data = load_github_stars(self.stars_path)
            agents = data.setdefault("agents", {})
            agents[agent_id] = {
                "github_repo": links.github_repo,
                "github_url": links.github_url,
                "github_stars": stars,
                "updated_at": updated_at,
            }
            data["schema_version"] = SCHEMA_VERSION
            data["updated_at"] = updated_at
            write_github_stars(self.stars_path, data)
            return GitHubStarsUpdateResult(
                agent_id=agent_id,
                status="updated",
                github_repo=links.github_repo,
                github_url=links.github_url,
                github_stars=stars,
                updated_at=updated_at,
            )
        except Exception as exc:
            return GitHubStarsUpdateResult(
                agent_id=agent_id,
                status="error",
                github_repo=links.github_repo,
                github_url=links.github_url,
                error=str(exc),
            )


def github_stars_updater_from_env(
    *, out_dir: str | Path = "results", fetcher=fetch_github_stars
) -> GitHubStarsUpdater | None:
    settings = github_stars_settings_from_env()
    if not settings["enabled"]:
        return None
    return GitHubStarsUpdater(
        out_dir=out_dir,
        api_base_url=str(settings["api_base_url"]),
        token=_github_token_from_env(),
        fetcher=fetcher,
    )
