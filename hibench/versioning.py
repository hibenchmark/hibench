from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any
import urllib.parse
import urllib.request

from packaging.version import InvalidVersion, Version

from .agents import ROOT, load_agent


VERSION_CATALOG_SCHEMA = "hibench.agent_versions.v1"
VERSION_CATALOG_DIR = ROOT / "agent_versions"
PLATFORM_SUFFIX_RE = re.compile(r"-(?:linux|darwin|win32)-(?:x64|arm64)$")
STABLE_SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)$"
)
BENCHMARK_VERSION_POLICY = (
    "stable_main_release: plain X.Y.0 versions only; excludes prerelease, "
    "platform/system variants, and timestamp/internal builds"
)
DEFAULT_BENCHMARK_VERSION_POLICY_ID = "stable_main_release"
BENCHMARK_VERSION_POLICIES = {
    DEFAULT_BENCHMARK_VERSION_POLICY_ID: BENCHMARK_VERSION_POLICY,
    "stable_semver": (
        "stable_semver: plain X.Y.Z versions only; excludes prerelease, "
        "platform/system variants, and timestamp/internal builds"
    ),
    "all_versions": (
        "all_versions: every fetched source version is benchmarkable unless "
        "explicitly excluded"
    ),
}
CURSOR_INSTALL_VERSION_RE = re.compile(
    r"https://downloads\.cursor\.com/lab/(?P<version>[^/\"']+)/"
)


def is_platform_version(version: str) -> bool:
    return bool(PLATFORM_SUFFIX_RE.search(version))


def is_stable_main_release_version(version: str) -> bool:
    """Return true for default benchmark targets.

    Package catalogs can contain alpha prereleases, platform-specific package variants,
    and timestamp/internal builds. The default benchmark series should stay on comparable
    public release lines, represented here as plain X.Y.0 versions.
    """

    if is_platform_version(version):
        return False
    match = STABLE_SEMVER_RE.fullmatch(version)
    if not match:
        return False
    return int(match.group("patch")) == 0


def is_stable_semver_version(version: str) -> bool:
    if is_platform_version(version):
        return False
    return bool(STABLE_SEMVER_RE.fullmatch(version))


def benchmark_version_policy_description(policy_id: str) -> str:
    if policy_id not in BENCHMARK_VERSION_POLICIES:
        raise ValueError(f"unknown benchmark version policy {policy_id!r}")
    return BENCHMARK_VERSION_POLICIES[policy_id]


def is_benchmark_version(version: str, policy_id: str) -> bool:
    if policy_id == "stable_main_release":
        return is_stable_main_release_version(version)
    if policy_id == "stable_semver":
        return is_stable_semver_version(version)
    if policy_id == "all_versions":
        return bool(version)
    raise ValueError(f"unknown benchmark version policy {policy_id!r}")


@dataclass(frozen=True)
class VersionCatalog:
    agent_id: str
    source: dict[str, Any]
    fetched_at: str
    versions: list[str]
    dist_tags: dict[str, str] | None = None
    benchmark_exclusions: dict[str, str] | None = None
    benchmark_version_policy_id: str = DEFAULT_BENCHMARK_VERSION_POLICY_ID
    benchmark_min_version: str | None = None
    benchmark_min_version_reason: str | None = None

    @property
    def latest(self) -> str:
        if self.dist_tags and self.dist_tags.get("latest"):
            return self.dist_tags["latest"]
        return self.versions[-1] if self.versions else ""

    @property
    def excluded_benchmark_versions(self) -> list[str]:
        excluded = set(self.benchmark_exclusions or {})
        return [
            version
            for version in self.versions
            if version in excluded
            and is_benchmark_version(version, self.benchmark_version_policy_id)
            and meets_min_version(version, self.benchmark_min_version)
        ]

    @property
    def benchmark_versions(self) -> list[str]:
        excluded = set(self.benchmark_exclusions or {})
        return [
            version
            for version in self.versions
            if is_benchmark_version(version, self.benchmark_version_policy_id)
            and meets_min_version(version, self.benchmark_min_version)
            and version not in excluded
        ]

    @property
    def benchmark_version_policy(self) -> str:
        return benchmark_version_policy_description(self.benchmark_version_policy_id)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "schema_version": VERSION_CATALOG_SCHEMA,
            "agent_id": self.agent_id,
            "source": self.source,
            "fetched_at": self.fetched_at,
            "version_count": len(self.versions),
            "benchmark_version_policy_id": self.benchmark_version_policy_id,
            "benchmark_version_policy": self.benchmark_version_policy,
        }
        if self.benchmark_min_version:
            data["benchmark_min_version"] = self.benchmark_min_version
            data["benchmark_min_version_reason"] = (
                self.benchmark_min_version_reason or ""
            )
        data.update(
            {
                "benchmark_version_count": len(self.benchmark_versions),
                "benchmark_exclusion_count": len(self.excluded_benchmark_versions),
                "benchmark_exclusions": self.benchmark_exclusions or {},
                "excluded_benchmark_versions": self.excluded_benchmark_versions,
                "latest": self.latest,
                "dist_tags": self.dist_tags or {},
                "versions": self.versions,
                "benchmark_versions": self.benchmark_versions,
            }
        )
        return data


@dataclass(frozen=True)
class PyPIPackageCatalog:
    versions: list[str]
    dist_tags: dict[str, str]


def version_catalog_path(
    agent_id: str, storage_dir: str | Path = VERSION_CATALOG_DIR
) -> Path:
    return Path(storage_dir) / f"{agent_id}.json"


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def unique_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def normalize_benchmark_exclusions(value: Any) -> dict[str, str]:
    if not value:
        return {}
    if isinstance(value, dict):
        return {str(version): str(reason) for version, reason in value.items()}
    if isinstance(value, list):
        return {str(version): "" for version in value}
    raise ValueError(
        "benchmark_exclusions must be a mapping of version to reason or a list"
    )


def normalize_benchmark_version_policy(value: Any) -> str:
    policy_id = str(value or DEFAULT_BENCHMARK_VERSION_POLICY_ID)
    benchmark_version_policy_description(policy_id)
    return policy_id


def normalize_benchmark_min_version(value: Any) -> str | None:
    if not value:
        return None
    version = str(value)
    try:
        Version(version)
    except InvalidVersion as error:
        raise ValueError(f"benchmark_min_version must be valid: {version!r}") from error
    return version


def normalize_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


def meets_min_version(version: str, minimum: str | None) -> bool:
    if not minimum:
        return True
    try:
        return Version(version) >= Version(minimum)
    except InvalidVersion:
        return False


def fetch_npm_versions(package_name: str, timeout: int = 60) -> list[str]:
    if shutil.which("npm") is None:
        raise RuntimeError(
            "npm executable not found; install Node/npm or use a stored version catalog"
        )

    completed = subprocess.run(
        ["npm", "view", package_name, "versions", "--json"],
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise RuntimeError(
            f"npm view failed for {package_name}: {stderr or completed.returncode}"
        )

    payload = json.loads(completed.stdout)
    if isinstance(payload, str):
        versions = [payload]
    elif isinstance(payload, list):
        versions = [str(item) for item in payload]
    else:
        raise ValueError(
            f"unexpected npm versions payload for {package_name}: {type(payload).__name__}"
        )
    return unique_preserve_order(versions)


def fetch_npm_dist_tags(package_name: str, timeout: int = 60) -> dict[str, str]:
    if shutil.which("npm") is None:
        raise RuntimeError(
            "npm executable not found; install Node/npm or use a stored version catalog"
        )

    completed = subprocess.run(
        ["npm", "view", package_name, "dist-tags", "--json"],
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise RuntimeError(
            f"npm dist-tags failed for {package_name}: {stderr or completed.returncode}"
        )

    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict):
        raise ValueError(
            f"unexpected npm dist-tags payload for {package_name}: {type(payload).__name__}"
        )
    return {str(key): str(value) for key, value in payload.items()}


def npm_packages_from_source(source: dict[str, Any]) -> list[str]:
    if source.get("type") != "npm":
        raise ValueError(f"unsupported version source type: {source.get('type')}")
    return packages_from_source(source)


def packages_from_source(source: dict[str, Any]) -> list[str]:
    if "packages" in source:
        packages = source["packages"]
        if not isinstance(packages, list) or not packages:
            raise ValueError("version source packages must be a non-empty list")
        return [str(package) for package in packages]
    package = source.get("package")
    if not package:
        raise ValueError("version source must define package or packages")
    return [str(package)]


def fetch_pypi_metadata(package_name: str, timeout: int = 60) -> dict[str, Any]:
    quoted = urllib.parse.quote(package_name, safe="")
    request = urllib.request.Request(
        f"https://pypi.org/pypi/{quoted}/json",
        headers={"Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError(
            f"unexpected PyPI metadata payload for {package_name}: "
            f"{type(payload).__name__}"
        )
    return payload


def pypi_version_sort_key(version: str) -> tuple[int, Version | str]:
    try:
        return (0, Version(version))
    except InvalidVersion:
        return (1, version)


def sort_pypi_versions(versions: list[str]) -> list[str]:
    return sorted(unique_preserve_order(versions), key=pypi_version_sort_key)


def parse_pypi_package_catalog(
    package_name: str, payload: dict[str, Any]
) -> PyPIPackageCatalog:
    releases = payload.get("releases")
    if not isinstance(releases, dict):
        raise ValueError(
            f"unexpected PyPI releases payload for {package_name}: "
            f"{type(releases).__name__}"
        )
    info = payload.get("info")
    latest = info.get("version") if isinstance(info, dict) else None
    return PyPIPackageCatalog(
        versions=sort_pypi_versions([str(version) for version in releases]),
        dist_tags={"latest": str(latest)} if latest else {},
    )


def fetch_pypi_package_catalog(
    package_name: str, timeout: int = 60
) -> PyPIPackageCatalog:
    payload = fetch_pypi_metadata(package_name, timeout=timeout)
    return parse_pypi_package_catalog(package_name, payload)


def fetch_pypi_versions(package_name: str, timeout: int = 60) -> list[str]:
    return fetch_pypi_package_catalog(package_name, timeout=timeout).versions


def fetch_text_url(url: str, timeout: int = 60) -> str:
    request = urllib.request.Request(url, headers={"Accept": "text/plain,*/*"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def parse_cursor_install_versions(script: str) -> list[str]:
    return unique_preserve_order(
        [match.group("version") for match in CURSOR_INSTALL_VERSION_RE.finditer(script)]
    )


def fetch_cursor_install_versions(url: str, timeout: int = 60) -> list[str]:
    versions = parse_cursor_install_versions(fetch_text_url(url, timeout=timeout))
    if not versions:
        raise ValueError(f"could not find Cursor CLI release version in {url}")
    return versions


def fetch_agent_version_catalog(agent_id: str, timeout: int = 60) -> VersionCatalog:
    spec = load_agent(agent_id)
    source = spec.version_source
    if not source:
        raise ValueError(f"no version source configured for agent {agent_id!r}")

    versions: list[str] = []
    dist_tags: dict[str, str] = {}
    source_type = source.get("type")
    if source_type == "npm":
        for package_name in packages_from_source(source):
            versions.extend(fetch_npm_versions(package_name, timeout=timeout))
            dist_tags.update(fetch_npm_dist_tags(package_name, timeout=timeout))
    elif source_type == "pypi":
        for package_name in packages_from_source(source):
            package_catalog = fetch_pypi_package_catalog(package_name, timeout=timeout)
            versions.extend(package_catalog.versions)
            dist_tags.update(package_catalog.dist_tags)
        versions = sort_pypi_versions(versions)
    elif source_type == "cursor-install":
        source_url = str(source.get("url") or "https://cursor.com/install")
        versions = fetch_cursor_install_versions(source_url, timeout=timeout)
        dist_tags["latest"] = versions[-1]
    else:
        raise ValueError(f"unsupported version source for {agent_id!r}: {source_type}")
    if source_type != "pypi":
        versions = unique_preserve_order(versions)
    raw_metadata = getattr(spec, "raw", {}) if spec is not None else {}
    benchmark_exclusions = normalize_benchmark_exclusions(
        raw_metadata.get("benchmark_exclusions")
        if isinstance(raw_metadata, dict)
        else None
    )
    benchmark_version_policy_id = normalize_benchmark_version_policy(
        raw_metadata.get("benchmark_version_policy")
        if isinstance(raw_metadata, dict)
        else None
    )
    benchmark_min_version = normalize_benchmark_min_version(
        raw_metadata.get("benchmark_min_version")
        if isinstance(raw_metadata, dict)
        else None
    )
    benchmark_min_version_reason = normalize_optional_string(
        raw_metadata.get("benchmark_min_version_reason")
        if isinstance(raw_metadata, dict)
        else None
    )
    return VersionCatalog(
        agent_id=agent_id,
        source=source,
        fetched_at=utc_now(),
        versions=versions,
        dist_tags=dist_tags,
        benchmark_exclusions=benchmark_exclusions,
        benchmark_version_policy_id=benchmark_version_policy_id,
        benchmark_min_version=benchmark_min_version,
        benchmark_min_version_reason=benchmark_min_version_reason,
    )


def write_version_catalog(
    catalog: VersionCatalog, storage_dir: str | Path = VERSION_CATALOG_DIR
) -> Path:
    path = version_catalog_path(catalog.agent_id, storage_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(catalog.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def load_version_catalog(
    agent_id: str, storage_dir: str | Path = VERSION_CATALOG_DIR
) -> VersionCatalog:
    path = version_catalog_path(agent_id, storage_dir)
    data = json.loads(path.read_text(encoding="utf-8"))
    return VersionCatalog(
        agent_id=str(data["agent_id"]),
        source={
            str(key): value for key, value in dict(data.get("source") or {}).items()
        },
        fetched_at=str(data.get("fetched_at") or ""),
        versions=[str(item) for item in data.get("versions") or []],
        dist_tags={
            str(key): str(value)
            for key, value in dict(data.get("dist_tags") or {}).items()
        },
        benchmark_exclusions=normalize_benchmark_exclusions(
            data.get("benchmark_exclusions")
        ),
        benchmark_version_policy_id=normalize_benchmark_version_policy(
            data.get("benchmark_version_policy_id")
        ),
        benchmark_min_version=normalize_benchmark_min_version(
            data.get("benchmark_min_version")
        ),
        benchmark_min_version_reason=normalize_optional_string(
            data.get("benchmark_min_version_reason")
        ),
    )


def fetch_and_store_agent_versions(
    agent_id: str,
    storage_dir: str | Path = VERSION_CATALOG_DIR,
    timeout: int = 60,
) -> tuple[VersionCatalog, Path]:
    catalog = fetch_agent_version_catalog(agent_id, timeout=timeout)
    path = write_version_catalog(catalog, storage_dir=storage_dir)
    return catalog, path


def select_versions(
    available_versions: list[str],
    requested_versions: list[str] | None = None,
    max_versions: int | None = None,
) -> list[str]:
    versions = list(requested_versions or available_versions)
    if requested_versions:
        available = set(available_versions)
        missing = [
            version for version in requested_versions if version not in available
        ]
        if missing:
            raise ValueError(
                f"requested version(s) not found in catalog: {', '.join(missing)}"
            )
    if max_versions is not None:
        versions = versions[:max_versions]
    return versions
