from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
import shlex
import subprocess
import tempfile
import time
from typing import Any
import uuid

from .agents import ROOT, AgentSpec, load_agent
from .benchmark_artifacts import write_run_artifacts
from .recorder import RequestRecorder


MAX_OUTPUT_CHARS = 2_000_000
DEFAULT_RUN_TIMEOUT_SECONDS = 30
WORKSPACE_PERMISSION_RESTORE_TIMEOUT_SECONDS = 30
DOCKER_CLEANUP_TIMEOUT_SECONDS = 30
DOCKER_NAME_SAFE_RE = re.compile(r"[^a-z0-9_.-]+")


@dataclass(frozen=True)
class RunResult:
    run_dir: Path
    summary: dict[str, Any]
    manifest: dict[str, Any]


def utc_stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def read_prompt(prompt_path: str | Path) -> str:
    return Path(prompt_path).read_text(encoding="utf-8").rstrip("\n")


def build_image(spec: AgentSpec, image: str | None = None) -> None:
    target = image or spec.image
    command = [
        "docker",
        "build",
        "-f",
        str(spec.dockerfile),
        "--build-arg",
        f"{spec.version_build_arg}={spec.version}",
        "-t",
        target,
        str(ROOT),
    ]
    env = os.environ.copy()
    if env.get("HIBENCH_DOCKER_USE_HOST_CONFIG") != "1":
        with tempfile.TemporaryDirectory(prefix="hibench-docker-config-") as config_dir:
            env["DOCKER_CONFIG"] = config_dir
            subprocess.run(command, check=True, env=env)
        return
    subprocess.run(command, check=True, env=env)


def purge_docker_image(image: str) -> None:
    try:
        subprocess.run(
            ["docker", "image", "rm", "--force", image],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=DOCKER_CLEANUP_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return


def docker_container_name(run_id: str) -> str:
    safe_run_id = DOCKER_NAME_SAFE_RE.sub("-", run_id.lower()).strip("._-")
    safe_run_id = safe_run_id[:80] or "run"
    return f"hibench-{safe_run_id}-{uuid.uuid4().hex[:12]}"


def remove_docker_container(container_name: str) -> None:
    try:
        subprocess.run(
            ["docker", "rm", "--force", container_name],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=DOCKER_CLEANUP_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return


def capture_config(spec: AgentSpec) -> dict[str, Any]:
    raw_capture = spec.raw.get("capture") if isinstance(spec.raw, dict) else None
    return raw_capture if isinstance(raw_capture, dict) else {}


def positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def resolve_run_timeout(spec: AgentSpec, requested_timeout: int | None) -> int:
    base_timeout = positive_int(requested_timeout) or DEFAULT_RUN_TIMEOUT_SECONDS
    configured_timeout = positive_int(capture_config(spec).get("host_timeout_seconds"))
    if configured_timeout is None:
        return base_timeout
    return max(base_timeout, configured_timeout)


def workspace_permission_cleanup_paths(spec: AgentSpec) -> list[str]:
    raw_paths = capture_config(spec).get("workspace_permission_cleanup_paths") or []
    if not isinstance(raw_paths, list):
        return []
    return [str(path) for path in raw_paths if str(path).strip()]


def restore_workspace_permissions(
    docker_image: str, subject_workspace: Path, container_paths: list[str]
) -> None:
    if not container_paths:
        return
    quoted_paths = " ".join(shlex.quote(path) for path in container_paths)
    script = (
        f"for path in {quoted_paths}; do "
        'chmod -R a+rwX "$path" 2>/dev/null || true; '
        "done"
    )
    try:
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{subject_workspace}:/workspace",
                "--entrypoint",
                "/bin/sh",
                docker_image,
                "-c",
                script,
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=WORKSPACE_PERMISSION_RESTORE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return


def base_url_root(base_url: str) -> str:
    return base_url.removesuffix("/v1")


def render_command(parts: list[str], prompt: str, base_url: str) -> list[str]:
    return [
        part.replace("{prompt}", prompt)
        .replace("{base_url_root}", base_url_root(base_url))
        .replace("{base_url}", base_url)
        for part in parts
    ]


def render_env(env: dict[str, str], base_url: str) -> dict[str, str]:
    return {
        key: value.replace("{base_url_root}", base_url_root(base_url)).replace(
            "{base_url}", base_url
        )
        for key, value in env.items()
    }


def create_empty_git_workspace(parent: Path) -> Path:
    workspace = parent / "workspace"
    workspace.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
    return workspace


def trim_output(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + "\n<hibench: output truncated>\n"


def run_agent(
    agent_id: str,
    prompt_path: str | Path,
    out_dir: str | Path = "runs",
    timeout: int | None = DEFAULT_RUN_TIMEOUT_SECONDS,
    image: str | None = None,
    build: bool = False,
    version: str | None = None,
    run_id: str | None = None,
    replace: bool = False,
) -> RunResult:
    spec = load_agent(agent_id, version=version)
    if build:
        build_image(spec, image=image)
    effective_timeout = resolve_run_timeout(spec, timeout)

    prompt = read_prompt(prompt_path)
    prompt_name = Path(prompt_path).stem.replace(" ", "-")
    run_id = run_id or f"{utc_stamp()}-{spec.id}-{prompt_name}"
    run_dir = Path(out_dir) / run_id
    if run_dir.exists() and replace:
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "prompt.txt").write_text(prompt + "\n", encoding="utf-8")

    temp_path = Path(tempfile.mkdtemp(prefix="hibench-subject-"))
    subject_workspace: Path | None = None
    recorder_host_base_url = ""
    docker_command: list[str] = []
    try:
        subject_workspace = create_empty_git_workspace(temp_path)
        with RequestRecorder(run_dir) as recorder:
            recorder_host_base_url = recorder.host_base_url
            env = render_env(spec.env, recorder.docker_base_url)
            command_args = render_command(
                spec.command, prompt, recorder.docker_base_url
            )
            docker_image = image or spec.image
            container_name = docker_container_name(run_id)
            docker_command = [
                "docker",
                "run",
                "--rm",
                "--name",
                container_name,
                "--add-host=host.docker.internal:host-gateway",
                "-v",
                f"{subject_workspace}:/workspace",
                "-w",
                "/workspace",
            ]
            for key, value in sorted(env.items()):
                docker_command.extend(["-e", f"{key}={value}"])
            docker_command.extend([docker_image, *command_args])

            started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            timed_out = False
            try:
                try:
                    completed = subprocess.run(
                        docker_command,
                        text=True,
                        capture_output=True,
                        timeout=effective_timeout,
                        check=False,
                    )
                    exit_code = completed.returncode
                    stdout = completed.stdout
                    stderr = completed.stderr
                except subprocess.TimeoutExpired as exc:
                    timed_out = True
                    exit_code = None
                    stdout = exc.stdout or ""
                    stderr = exc.stderr or ""
                    remove_docker_container(container_name)
            finally:
                restore_workspace_permissions(
                    docker_image,
                    subject_workspace,
                    workspace_permission_cleanup_paths(spec),
                )
            ended_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    finally:
        shutil.rmtree(temp_path, ignore_errors=True)

    stdout_text = trim_output(
        stdout if isinstance(stdout, str) else stdout.decode("utf-8", errors="replace")
    )
    stderr_text = trim_output(
        stderr if isinstance(stderr, str) else stderr.decode("utf-8", errors="replace")
    )
    (run_dir / "stdout.txt").write_text(stdout_text, encoding="utf-8")
    (run_dir / "stderr.txt").write_text(stderr_text, encoding="utf-8")

    manifest = {
        "run_id": run_id,
        "agent": {
            "id": spec.id,
            "display_name": spec.display_name,
            "version": spec.version,
            "image": image or spec.image,
            "parser_id": spec.parser_id,
        },
        "prompt_file": str(prompt_path),
        "started_at": started_at,
        "ended_at": ended_at,
        "subject_workspace": "generated empty Git repository",
        "real_api_call": False,
        "recorder_base_url_host": recorder_host_base_url,
        "docker_command": docker_command,
        "process": {
            "exit_code": exit_code,
            "timed_out": timed_out,
            "timeout_seconds": effective_timeout,
            "requested_timeout_seconds": timeout,
        },
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    summary = write_run_artifacts(run_dir)
    return RunResult(run_dir=run_dir, summary=summary, manifest=manifest)


def ensure_docker_available() -> bool:
    return shutil.which("docker") is not None
