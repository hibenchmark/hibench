from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from hibench.agents import load_agent
from hibench.runner import (
    build_image,
    purge_docker_image,
    resolve_run_timeout,
    run_agent,
    workspace_permission_cleanup_paths,
)


class RunnerTests(unittest.TestCase):
    def test_purge_docker_image_removes_specific_image_tag(self) -> None:
        with patch("hibench.runner.subprocess.run") as run:
            purge_docker_image("hibench/codex:0.1.0")

        run.assert_called_once_with(
            ["docker", "image", "rm", "--force", "hibench/codex:0.1.0"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )

    def test_build_image_uses_isolated_docker_config_by_default(self) -> None:
        spec = load_agent("codex", version="0.1.0")
        with patch.dict(os.environ, {}, clear=True):
            with patch("hibench.runner.subprocess.run") as run:
                build_image(spec, image="hibench/codex:test")

        command = run.call_args.args[0]
        kwargs = run.call_args.kwargs
        self.assertEqual(command[:2], ["docker", "build"])
        self.assertIn("DOCKER_CONFIG", kwargs["env"])
        self.assertTrue(kwargs["env"]["DOCKER_CONFIG"])
        self.assertNotIn("HIBENCH_DOCKER_USE_HOST_CONFIG", kwargs["env"])

    def test_openclaw_capture_config_extends_host_timeout(self) -> None:
        spec = load_agent("openclaw")
        self.assertEqual(resolve_run_timeout(spec, 30), 300)
        self.assertEqual(resolve_run_timeout(spec, 300), 300)
        self.assertEqual(
            workspace_permission_cleanup_paths(spec), ["/workspace/.openclaw"]
        )

    def test_run_agent_timeout_stops_named_container_and_restores_workspace(
        self,
    ) -> None:
        docker_rm_calls: list[list[str]] = []
        cleanup_calls: list[list[str]] = []
        agent_run_calls: list[tuple[list[str], dict[str, object]]] = []

        def fake_run(command, **kwargs):
            if command[:2] == ["git", "init"]:
                return subprocess.CompletedProcess(command, 0, "", "")
            if command[:3] == ["docker", "rm", "--force"]:
                docker_rm_calls.append(command)
                return subprocess.CompletedProcess(command, 0, "", "")
            if command[:2] == ["docker", "run"] and "--entrypoint" in command:
                cleanup_calls.append(command)
                return subprocess.CompletedProcess(command, 0, "", "")
            if command[:2] == ["docker", "run"]:
                agent_run_calls.append((command, kwargs))
                volume = next(part for part in command if part.endswith(":/workspace"))
                workspace = Path(volume.split(":", 1)[0])
                (workspace / ".openclaw").mkdir()
                raise subprocess.TimeoutExpired(
                    command, kwargs["timeout"], output="partial", stderr="slow"
                )
            raise AssertionError(f"unexpected subprocess command: {command}")

        with tempfile.TemporaryDirectory() as tmp:
            with patch("hibench.runner.subprocess.run", side_effect=fake_run):
                result = run_agent(
                    "openclaw",
                    prompt_path="prompts/hi.txt",
                    out_dir=tmp,
                    run_id="timeout-openclaw",
                )

            run_dir = Path(tmp) / "timeout-openclaw"
            self.assertEqual((run_dir / "stdout.txt").read_text(), "partial")
            self.assertEqual((run_dir / "stderr.txt").read_text(), "slow")

        self.assertEqual(len(agent_run_calls), 1)
        docker_command, run_kwargs = agent_run_calls[0]
        self.assertEqual(run_kwargs["timeout"], 300)
        self.assertIn("--name", docker_command)
        self.assertTrue(result.manifest["process"]["timed_out"])
        self.assertEqual(result.manifest["process"]["timeout_seconds"], 300)
        self.assertEqual(len(docker_rm_calls), 1)
        self.assertEqual(len(cleanup_calls), 1)
        self.assertIn("/workspace/.openclaw", cleanup_calls[0][-1])


if __name__ == "__main__":
    unittest.main()
