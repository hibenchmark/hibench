from __future__ import annotations

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import call, patch

from hibench.automation import (
    VersionBenchmarkResult,
    canonical_run_id,
    existing_run_dirs_for_agent_version,
    format_benchmark_batches_report,
    run_benchmark_batch,
    run_benchmark_batches,
    run_version_benchmark,
    run_version_benchmarks,
    select_agent_benchmark_versions,
)
from hibench.benchmark_export import export_benchmark_results
from hibench.runner import RunResult
from hibench.versioning import (
    PyPIPackageCatalog,
    VersionCatalog,
    fetch_agent_version_catalog,
    fetch_cursor_install_versions,
    fetch_npm_versions,
    fetch_pypi_package_catalog,
    is_benchmark_version,
    is_stable_main_release_version,
    is_stable_semver_version,
    load_version_catalog,
    select_versions,
    write_version_catalog,
)


def benchmark_summary(
    *,
    has_primary_request: bool = True,
    total_body_tokens: int = 10,
    tool_count: int = 1,
) -> dict:
    return {
        "benchmark": {
            "has_primary_request": has_primary_request,
            "request_count": 1 if has_primary_request else 0,
            "post_request_count": 1 if has_primary_request else 0,
            "total_body_tokens": total_body_tokens,
            "tool_count": tool_count,
        }
    }


class VersioningTests(unittest.TestCase):
    def test_fetch_npm_versions_parses_json_and_dedupes(self) -> None:
        completed = SimpleNamespace(
            returncode=0, stdout=json.dumps(["0.1.0", "0.1.0", "0.2.0"]), stderr=""
        )
        with patch("hibench.versioning.shutil.which", return_value="/usr/bin/npm"):
            with patch(
                "hibench.versioning.subprocess.run", return_value=completed
            ) as run:
                versions = fetch_npm_versions("@openai/codex")

        self.assertEqual(versions, ["0.1.0", "0.2.0"])
        run.assert_called_once()

    def test_fetch_pypi_package_catalog_parses_latest_and_sorts_versions(
        self,
    ) -> None:
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def read(self, *_args):
                return json.dumps(
                    {
                        "info": {"version": "0.10.0"},
                        "releases": {
                            "0.10.0": [],
                            "0.1.0": [],
                            "0.2.0": [],
                        },
                    }
                ).encode()

        with patch(
            "hibench.versioning.urllib.request.urlopen", return_value=FakeResponse()
        ) as urlopen:
            catalog = fetch_pypi_package_catalog("example-agent")

        self.assertEqual(catalog.versions, ["0.1.0", "0.2.0", "0.10.0"])
        self.assertEqual(catalog.dist_tags, {"latest": "0.10.0"})
        urlopen.assert_called_once()

    def test_fetch_agent_version_catalog_uses_agent_metadata_source(self) -> None:
        spec = SimpleNamespace(
            version_source={"type": "npm", "package": "@example/agent"},
            raw={"benchmark_exclusions": {"1.0.0": "known bad build"}},
        )
        with patch("hibench.versioning.load_agent", return_value=spec):
            with patch(
                "hibench.versioning.fetch_npm_versions", return_value=["1.0.0"]
            ) as versions:
                with patch(
                    "hibench.versioning.fetch_npm_dist_tags",
                    return_value={"latest": "1.0.0"},
                ) as dist_tags:
                    catalog = fetch_agent_version_catalog("example")

        versions.assert_called_once_with("@example/agent", timeout=60)
        dist_tags.assert_called_once_with("@example/agent", timeout=60)
        self.assertEqual(catalog.source, spec.version_source)
        self.assertEqual(catalog.versions, ["1.0.0"])
        self.assertEqual(catalog.benchmark_exclusions, {"1.0.0": "known bad build"})
        self.assertEqual(catalog.benchmark_version_policy_id, "stable_main_release")
        self.assertEqual(catalog.benchmark_versions, [])

    def test_fetch_agent_version_catalog_supports_pypi_source(self) -> None:
        spec = SimpleNamespace(
            version_source={"type": "pypi", "package": "example-agent"},
            raw={"benchmark_version_policy": "stable_semver"},
        )
        with patch("hibench.versioning.load_agent", return_value=spec):
            with patch(
                "hibench.versioning.fetch_pypi_package_catalog",
                return_value=PyPIPackageCatalog(
                    versions=["0.1.0", "0.1.1", "0.2.0a1"],
                    dist_tags={"latest": "0.1.1"},
                ),
            ) as package_catalog:
                catalog = fetch_agent_version_catalog("example")

        package_catalog.assert_called_once_with("example-agent", timeout=60)
        self.assertEqual(catalog.source, spec.version_source)
        self.assertEqual(catalog.latest, "0.1.1")
        self.assertEqual(catalog.benchmark_versions, ["0.1.0", "0.1.1"])

    def test_fetch_agent_version_catalog_supports_cursor_install_source(self) -> None:
        spec = SimpleNamespace(
            version_source={
                "type": "cursor-install",
                "url": "https://cursor.com/install",
                "package": "agent-cli-local-package.tar.gz",
            },
            raw={"benchmark_version_policy": "all_versions"},
        )
        with patch("hibench.versioning.load_agent", return_value=spec):
            with patch(
                "hibench.versioning.fetch_cursor_install_versions",
                return_value=["2026.06.12-19-59-36-f6aba9a"],
            ) as versions:
                catalog = fetch_agent_version_catalog("cursor-cli")

        versions.assert_called_once_with("https://cursor.com/install", timeout=60)
        self.assertEqual(catalog.source, spec.version_source)
        self.assertEqual(catalog.latest, "2026.06.12-19-59-36-f6aba9a")
        self.assertEqual(catalog.benchmark_versions, ["2026.06.12-19-59-36-f6aba9a"])

    def test_fetch_cursor_install_versions_parses_download_url(self) -> None:
        script = (
            'DOWNLOAD_URL="https://downloads.cursor.com/lab/'
            '2026.06.12-19-59-36-f6aba9a/${OS}/${ARCH}/agent-cli-package.tar.gz"'
        )
        with patch("hibench.versioning.fetch_text_url", return_value=script):
            versions = fetch_cursor_install_versions("https://cursor.com/install")

        self.assertEqual(versions, ["2026.06.12-19-59-36-f6aba9a"])

    def test_fetch_agent_version_catalog_applies_min_version_policy(self) -> None:
        spec = SimpleNamespace(
            version_source={"type": "npm", "package": "@example/agent"},
            raw={
                "benchmark_version_policy": "stable_semver",
                "benchmark_min_version": "1.0.8",
                "benchmark_min_version_reason": "requires BYOK/offline support",
            },
        )
        with patch("hibench.versioning.load_agent", return_value=spec):
            with patch(
                "hibench.versioning.fetch_npm_versions",
                return_value=["1.0.7", "1.0.8", "1.0.9"],
            ):
                with patch(
                    "hibench.versioning.fetch_npm_dist_tags",
                    return_value={"latest": "1.0.9"},
                ):
                    catalog = fetch_agent_version_catalog("example")

        self.assertEqual(catalog.benchmark_min_version, "1.0.8")
        self.assertEqual(
            catalog.benchmark_min_version_reason, "requires BYOK/offline support"
        )
        self.assertEqual(catalog.benchmark_versions, ["1.0.8", "1.0.9"])
        self.assertEqual(catalog.excluded_benchmark_versions, [])
        self.assertEqual(catalog.to_dict()["benchmark_min_version"], "1.0.8")

    def test_fetch_agent_version_catalog_merges_multiple_npm_packages(self) -> None:
        spec = SimpleNamespace(
            version_source={
                "type": "npm",
                "package": "@example/current",
                "packages": ["@example/legacy", "@example/current"],
            },
            raw={"benchmark_version_policy": "stable_semver"},
        )
        with patch("hibench.versioning.load_agent", return_value=spec):
            with patch(
                "hibench.versioning.fetch_npm_versions",
                side_effect=[["0.1.0", "0.2.0"], ["0.2.0", "0.3.0"]],
            ) as versions:
                with patch(
                    "hibench.versioning.fetch_npm_dist_tags",
                    side_effect=[{"latest": "0.2.0"}, {"latest": "0.3.0"}],
                ) as dist_tags:
                    catalog = fetch_agent_version_catalog("example")

        self.assertEqual(
            versions.call_args_list,
            [
                call("@example/legacy", timeout=60),
                call("@example/current", timeout=60),
            ],
        )
        self.assertEqual(
            dist_tags.call_args_list,
            [
                call("@example/legacy", timeout=60),
                call("@example/current", timeout=60),
            ],
        )
        self.assertEqual(catalog.versions, ["0.1.0", "0.2.0", "0.3.0"])
        self.assertEqual(catalog.latest, "0.3.0")
        self.assertEqual(catalog.benchmark_versions, ["0.1.0", "0.2.0", "0.3.0"])

    def test_write_load_and_select_version_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog = VersionCatalog(
                agent_id="codex",
                source={"type": "npm", "package": "@openai/codex"},
                fetched_at="2026-06-13T00:00:00Z",
                versions=[
                    "0.1.2505172116",
                    "0.1.0",
                    "0.2.0-alpha.1",
                    "0.2.0-alpha.1-linux-x64",
                    "0.2.0-linux-x64",
                    "0.2.0",
                    "0.2.1",
                ],
                dist_tags={"latest": "0.2.0"},
                benchmark_exclusions={"0.2.0": "known bad build"},
            )
            path = write_version_catalog(catalog, storage_dir=tmp)
            loaded = load_version_catalog("codex", storage_dir=tmp)

            self.assertEqual(path, Path(tmp) / "codex.json")
            self.assertEqual(loaded.latest, "0.2.0")
            self.assertEqual(loaded.benchmark_version_policy_id, "stable_main_release")
            self.assertEqual(loaded.benchmark_versions, ["0.1.0"])
            self.assertEqual(loaded.excluded_benchmark_versions, ["0.2.0"])
            self.assertEqual(
                select_versions(loaded.benchmark_versions, max_versions=1), ["0.1.0"]
            )
            self.assertEqual(
                select_versions(loaded.versions, requested_versions=["0.2.0"]),
                ["0.2.0"],
            )
            with self.assertRaises(ValueError):
                select_versions(loaded.versions, requested_versions=["9.9.9"])

    def test_write_and_load_version_catalog_preserves_min_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog = VersionCatalog(
                agent_id="example",
                source={"type": "npm", "package": "@example/agent"},
                fetched_at="2026-06-13T00:00:00Z",
                versions=["1.0.7", "1.0.8", "1.0.9"],
                benchmark_version_policy_id="stable_semver",
                benchmark_min_version="1.0.8",
                benchmark_min_version_reason="requires compatible provider flags",
            )

            write_version_catalog(catalog, storage_dir=tmp)
            loaded = load_version_catalog("example", storage_dir=tmp)

            self.assertEqual(loaded.benchmark_min_version, "1.0.8")
            self.assertEqual(
                loaded.benchmark_min_version_reason,
                "requires compatible provider flags",
            )
            self.assertEqual(loaded.benchmark_versions, ["1.0.8", "1.0.9"])

    def test_default_benchmark_versions_are_stable_main_releases(self) -> None:
        cases = {
            "0.139.0": True,
            "1.2.0": True,
            "0.140.0-alpha.17": False,
            "0.140.0-alpha.17-linux-x64": False,
            "0.139.0-linux-x64": False,
            "0.1.2505172116": False,
            "0.139.1": False,
            "not-a-version": False,
        }
        for version, expected in cases.items():
            with self.subTest(version=version):
                self.assertEqual(is_stable_main_release_version(version), expected)

    def test_stable_semver_policy_includes_patch_releases(self) -> None:
        catalog = VersionCatalog(
            agent_id="claude-code",
            source={"type": "npm", "package": "@anthropic-ai/claude-code"},
            fetched_at="2026-06-13T00:00:00Z",
            versions=[
                "2.1.153",
                "2.1.177",
                "2.1.178-next.0",
                "2.1.177-linux-x64",
                "2.2.0",
            ],
            dist_tags={"latest": "2.1.177"},
            benchmark_version_policy_id="stable_semver",
        )

        self.assertTrue(is_stable_semver_version("2.1.177"))
        self.assertFalse(is_stable_semver_version("2.1.178-next.0"))
        self.assertFalse(is_stable_semver_version("2.1.177-linux-x64"))
        self.assertTrue(is_benchmark_version("2.1.177", "stable_semver"))
        self.assertFalse(is_benchmark_version("2.1.177", "stable_main_release"))
        self.assertEqual(catalog.benchmark_versions, ["2.1.153", "2.1.177", "2.2.0"])
        self.assertEqual(
            catalog.to_dict()["benchmark_version_policy_id"], "stable_semver"
        )

    def test_all_versions_policy_includes_timestamp_releases(self) -> None:
        catalog = VersionCatalog(
            agent_id="cursor-cli",
            source={"type": "cursor-install", "url": "https://cursor.com/install"},
            fetched_at="2026-06-14T00:00:00Z",
            versions=["2026.06.12-19-59-36-f6aba9a"],
            dist_tags={"latest": "2026.06.12-19-59-36-f6aba9a"},
            benchmark_version_policy_id="all_versions",
        )

        self.assertTrue(
            is_benchmark_version("2026.06.12-19-59-36-f6aba9a", "all_versions")
        )
        self.assertEqual(catalog.benchmark_versions, ["2026.06.12-19-59-36-f6aba9a"])

    def test_new_agent_selection_starts_with_latest_100_versions(self) -> None:
        versions = [f"0.{index}.0" for index in range(105)]
        with tempfile.TemporaryDirectory() as tmp:
            selection = select_agent_benchmark_versions(
                versions, agent_id="codex", runs_dir=tmp
            )

        self.assertEqual(len(selection.versions), 100)
        self.assertEqual(selection.versions[0], "0.5.0")
        self.assertEqual(selection.versions[-1], "0.104.0")
        self.assertTrue(selection.initial_limit_applied)
        self.assertEqual(selection.existing_versions, [])

    def test_existing_agent_selection_stays_within_latest_100_versions(self) -> None:
        versions = [f"0.{index}.0" for index in range(105)]
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp)
            for version in ("0.0.0", "0.5.0", "0.6.0"):
                old_run = runs_dir / f"codex-{version}"
                old_run.mkdir()
                (old_run / "manifest.json").write_text(
                    json.dumps({"agent": {"id": "codex", "version": version}}),
                    encoding="utf-8",
                )

            selection = select_agent_benchmark_versions(
                versions,
                agent_id="codex",
                runs_dir=runs_dir,
                max_versions=3,
            )

        self.assertEqual(selection.versions, ["0.7.0", "0.8.0", "0.9.0"])
        self.assertEqual(selection.existing_versions, ["0.0.0", "0.5.0", "0.6.0"])
        self.assertEqual(selection.skipped_existing_versions, ["0.5.0", "0.6.0"])
        self.assertTrue(selection.initial_limit_applied)
        self.assertEqual(selection.candidate_version_count, 98)

    def test_existing_agent_selection_uses_missing_catalog_versions(self) -> None:
        versions = [f"0.{index}.0" for index in range(8)]
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp)
            for version in ("0.0.0", "0.1.0", "0.3.0"):
                old_run = runs_dir / f"codex-{version}"
                old_run.mkdir()
                (old_run / "manifest.json").write_text(
                    json.dumps({"agent": {"id": "codex", "version": version}}),
                    encoding="utf-8",
                )

            selection = select_agent_benchmark_versions(
                versions, agent_id="codex", runs_dir=runs_dir
            )

        self.assertEqual(
            selection.versions, ["0.2.0", "0.4.0", "0.5.0", "0.6.0", "0.7.0"]
        )
        self.assertEqual(selection.existing_versions, ["0.0.0", "0.1.0", "0.3.0"])
        self.assertEqual(
            selection.skipped_existing_versions, ["0.0.0", "0.1.0", "0.3.0"]
        )
        self.assertFalse(selection.initial_limit_applied)
        self.assertEqual(selection.candidate_version_count, 5)

    def test_existing_agent_selection_max_versions_uses_first_missing_version(
        self,
    ) -> None:
        versions = [f"0.{index}.0" for index in range(6)]
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp)
            for version in ("0.0.0", "0.1.0", "0.3.0"):
                old_run = runs_dir / f"codex-{version}"
                old_run.mkdir()
                (old_run / "manifest.json").write_text(
                    json.dumps({"agent": {"id": "codex", "version": version}}),
                    encoding="utf-8",
                )

            selection = select_agent_benchmark_versions(
                versions,
                agent_id="codex",
                runs_dir=runs_dir,
                max_versions=1,
            )

        self.assertEqual(selection.versions, ["0.2.0"])

    def test_existing_agent_selection_retries_explicit_no_primary_runs(self) -> None:
        versions = ["0.1.0", "0.2.0"]
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp)
            no_primary = runs_dir / "codex-no-primary"
            no_primary.mkdir()
            (no_primary / "benchmark_result.json").write_text(
                json.dumps(
                    {
                        "run": {
                            "agent_id": "codex",
                            "agent_version": "0.1.0",
                            "has_primary_request": False,
                        }
                    }
                ),
                encoding="utf-8",
            )
            valid = runs_dir / "codex-valid"
            valid.mkdir()
            (valid / "benchmark_result.json").write_text(
                json.dumps(
                    {
                        "run": {
                            "agent_id": "codex",
                            "agent_version": "0.2.0",
                            "has_primary_request": True,
                        }
                    }
                ),
                encoding="utf-8",
            )

            selection = select_agent_benchmark_versions(
                versions,
                agent_id="codex",
                runs_dir=runs_dir,
            )

        self.assertEqual(selection.versions, ["0.1.0"])
        self.assertEqual(selection.existing_versions, ["0.2.0"])
        self.assertEqual(selection.skipped_existing_versions, ["0.2.0"])

    def test_existing_agent_selection_can_include_existing_for_reruns(self) -> None:
        versions = [f"0.{index}.0" for index in range(4)]
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp)
            old_run = runs_dir / "codex-old"
            old_run.mkdir()
            (old_run / "manifest.json").write_text(
                json.dumps({"agent": {"id": "codex", "version": "0.0.0"}}),
                encoding="utf-8",
            )

            selection = select_agent_benchmark_versions(
                versions,
                agent_id="codex",
                runs_dir=runs_dir,
                max_versions=1,
                include_existing=True,
            )

        self.assertEqual(selection.versions, ["0.0.0"])
        self.assertEqual(selection.skipped_existing_versions, [])

    def test_version_benchmark_callback_runs_after_each_result(self) -> None:
        seen: list[str] = []

        def fake_run_version_benchmark(**kwargs):
            version = kwargs["version"]
            if version == "0.2.0":
                self.assertEqual(seen, ["0.1.0"])
            return VersionBenchmarkResult(
                agent_id=kwargs["agent_id"],
                version=version,
                status="created",
                run_id=canonical_run_id(
                    kwargs["agent_id"], version, kwargs["prompt_path"]
                ),
                run_dir=str(Path(kwargs["out_dir"]) / version),
                replaced_run_dirs=[],
            )

        def after_each(result: VersionBenchmarkResult) -> None:
            seen.append(result.version)

        with patch(
            "hibench.automation.run_version_benchmark",
            side_effect=fake_run_version_benchmark,
        ):
            results = run_version_benchmarks(
                agent_id="codex",
                versions=["0.1.0", "0.2.0"],
                prompt_path="prompts/hi.txt",
                out_dir="runs",
                after_each=after_each,
            )

        self.assertEqual([result.version for result in results], ["0.1.0", "0.2.0"])
        self.assertEqual(seen, ["0.1.0", "0.2.0"])

    def test_benchmark_batch_exports_aggregate_results_after_each_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            results_dir = Path(tmp) / "results"
            catalog = VersionCatalog(
                agent_id="codex",
                source={"type": "npm", "package": "@openai/codex"},
                fetched_at="2026-06-13T00:00:00Z",
                versions=["0.1.0", "0.2.0"],
                dist_tags={"latest": "0.2.0"},
            )
            run_results = [
                VersionBenchmarkResult(
                    agent_id="codex",
                    version="0.1.0",
                    status="created",
                    run_id="codex-0.1.0-hi",
                    run_dir=str(runs_dir / "codex-0.1.0-hi"),
                    replaced_run_dirs=[],
                    has_primary_request=True,
                    total_body_tokens=10,
                    tool_count=1,
                ),
                VersionBenchmarkResult(
                    agent_id="codex",
                    version="0.2.0",
                    status="created",
                    run_id="codex-0.2.0-hi",
                    run_dir=str(runs_dir / "codex-0.2.0-hi"),
                    replaced_run_dirs=[],
                    has_primary_request=True,
                    total_body_tokens=20,
                    tool_count=2,
                ),
            ]

            def fake_run_version_benchmarks(**kwargs):
                after_each = kwargs["after_each"]
                self.assertIsNotNone(after_each)
                for result in run_results:
                    after_each(result)
                return run_results

            with patch("hibench.automation.ensure_docker_available", return_value=True):
                with patch(
                    "hibench.automation.load_or_fetch_version_catalog",
                    return_value=(catalog, Path("agent_versions/codex.json")),
                ):
                    with patch(
                        "hibench.automation.run_version_benchmarks",
                        side_effect=fake_run_version_benchmarks,
                    ):
                        with patch(
                            "hibench.automation.export_benchmark_results",
                            return_value={
                                "run_count": 2,
                                "deduplicated_run_count": 0,
                            },
                        ) as export:
                            batch = run_benchmark_batch(
                                agent_id="codex",
                                prompt_path="prompts/hi.txt",
                                out_dir=runs_dir,
                                max_versions=2,
                                build=False,
                                results_out=results_dir,
                            )

            self.assertFalse(batch.has_errors)
            self.assertEqual(batch.aggregate_refresh_count, 2)
            export.assert_called()
            self.assertEqual(export.call_count, 2)
            self.assertTrue((runs_dir / "benchmark_batch.json").exists())

    def test_benchmark_batch_counts_anthropic_tokens_before_each_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            results_dir = Path(tmp) / "results"
            catalog = VersionCatalog(
                agent_id="codex",
                source={"type": "npm", "package": "@openai/codex"},
                fetched_at="2026-06-13T00:00:00Z",
                versions=["0.1.0", "0.2.0"],
                dist_tags={"latest": "0.2.0"},
            )
            run_results = [
                VersionBenchmarkResult(
                    agent_id="codex",
                    version="0.1.0",
                    status="created",
                    run_id="codex-0.1.0-hi",
                    run_dir=str(runs_dir / "codex-0.1.0-hi"),
                    replaced_run_dirs=[],
                    has_primary_request=True,
                ),
                VersionBenchmarkResult(
                    agent_id="codex",
                    version="0.2.0",
                    status="created",
                    run_id="codex-0.2.0-hi",
                    run_dir=str(runs_dir / "codex-0.2.0-hi"),
                    replaced_run_dirs=[],
                    has_primary_request=True,
                ),
            ]
            events: list[tuple[str, str]] = []

            class FakeCounter:
                def count_run(self, run_dir):
                    events.append(("count", Path(run_dir).name))
                    return SimpleNamespace(updated=True)

            def fake_run_version_benchmarks(**kwargs):
                after_each = kwargs["after_each"]
                self.assertIsNotNone(after_each)
                for result in run_results:
                    after_each(result)
                return run_results

            def fake_export(*_args, **_kwargs):
                events.append(("export", ""))
                return {"run_count": 2, "deduplicated_run_count": 0}

            settings = {
                "enabled": True,
                "api_key_env": "ANTHROPIC_API_KEY",
                "api_key_present": True,
                "base_url": "https://api.anthropic.com",
                "model": "claude-test",
                "rpm": 90.0,
                "disabled_reason": "",
            }

            with patch("hibench.automation.ensure_docker_available", return_value=True):
                with patch(
                    "hibench.automation.load_or_fetch_version_catalog",
                    return_value=(catalog, Path("agent_versions/codex.json")),
                ):
                    with patch(
                        "hibench.automation.run_version_benchmarks",
                        side_effect=fake_run_version_benchmarks,
                    ):
                        with patch(
                            "hibench.automation.anthropic_tokenizer_settings_from_env",
                            return_value=settings,
                        ):
                            with patch(
                                "hibench.automation.anthropic_token_counter_from_env",
                                return_value=FakeCounter(),
                            ):
                                with patch(
                                    "hibench.automation.export_benchmark_results",
                                    side_effect=fake_export,
                                ):
                                    batch = run_benchmark_batch(
                                        agent_id="codex",
                                        prompt_path="prompts/hi.txt",
                                        out_dir=runs_dir,
                                        max_versions=2,
                                        build=False,
                                        results_out=results_dir,
                                    )

            self.assertEqual(
                events,
                [
                    ("count", "codex-0.1.0-hi"),
                    ("export", ""),
                    ("count", "codex-0.2.0-hi"),
                    ("export", ""),
                ],
            )
            self.assertEqual(
                batch.manifest["anthropic_tokenizer"]["counted_run_count"], 2
            )
            self.assertEqual(batch.manifest["anthropic_tokenizer"]["error_count"], 0)

    def test_all_benchmark_batches_write_structured_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            catalogs = {
                "codex": VersionCatalog(
                    agent_id="codex",
                    source={"type": "npm", "package": "@openai/codex"},
                    fetched_at="2026-06-13T00:00:00Z",
                    versions=["0.1.0"],
                    dist_tags={"latest": "0.1.0"},
                ),
                "claude-code": VersionCatalog(
                    agent_id="claude-code",
                    source={"type": "npm", "package": "@anthropic-ai/claude-code"},
                    fetched_at="2026-06-13T00:00:00Z",
                    versions=["1.0.0"],
                    dist_tags={"latest": "1.0.0"},
                ),
            }

            def fake_load_or_fetch_version_catalog(agent_id, **_kwargs):
                return catalogs[agent_id], Path(f"agent_versions/{agent_id}.json")

            progress_events = []
            with patch(
                "hibench.automation.load_or_fetch_version_catalog",
                side_effect=fake_load_or_fetch_version_catalog,
            ):
                result = run_benchmark_batches(
                    agent_ids=["codex", "claude-code"],
                    prompt_path="prompts/hi.txt",
                    out_dir=runs_dir,
                    max_versions=1,
                    build=False,
                    dry_run=True,
                    use_local_versions=True,
                    on_agent_progress=progress_events.append,
                )

            self.assertFalse(result.has_errors)
            self.assertEqual(
                [
                    (
                        event.agent_id,
                        event.agent_index,
                        event.agent_count,
                        event.event,
                        event.batch is not None,
                    )
                    for event in progress_events
                ],
                [
                    ("codex", 1, 2, "started", False),
                    ("codex", 1, 2, "completed", True),
                    ("claude-code", 2, 2, "started", False),
                    ("claude-code", 2, 2, "completed", True),
                ],
            )
            self.assertEqual(
                [batch.agent_id for batch in result.batches],
                ["codex", "claude-code"],
            )
            self.assertEqual(result.manifest_path, runs_dir / "benchmark_batches.json")
            self.assertTrue(result.manifest_path.exists())
            self.assertTrue((runs_dir / "benchmark_batch-codex.json").exists())
            self.assertTrue((runs_dir / "benchmark_batch-claude-code.json").exists())
            self.assertFalse((runs_dir / "benchmark_batch.json").exists())

            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], "hibench.benchmark_batches.v1")
            self.assertEqual(manifest["agent_ids"], ["codex", "claude-code"])
            self.assertEqual(
                [entry["agent_id"] for entry in manifest["batches"]],
                ["codex", "claude-code"],
            )
            self.assertEqual(
                [entry["batch_manifest"] for entry in manifest["batches"]],
                [
                    str(runs_dir / "benchmark_batch-codex.json"),
                    str(runs_dir / "benchmark_batch-claude-code.json"),
                ],
            )

            report = format_benchmark_batches_report(result)
            self.assertIn("HiBench all-agent benchmark", report)
            self.assertIn("agents: 2", report)
            self.assertIn(f"all_batch_manifest: {result.manifest_path}", report)

    def test_version_benchmark_replaces_existing_agent_version_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            old_run = runs_dir / "old-codex"
            old_run.mkdir(parents=True)
            (old_run / "manifest.json").write_text(
                json.dumps({"agent": {"id": "codex", "version": "0.1.0"}}),
                encoding="utf-8",
            )

            def fake_run_agent(**kwargs):
                run_dir = Path(kwargs["out_dir"]) / kwargs["run_id"]
                requests_dir = run_dir / "requests"
                requests_dir.mkdir(parents=True)
                manifest = {
                    "run_id": kwargs["run_id"],
                    "agent": {
                        "id": kwargs["agent_id"],
                        "display_name": "OpenAI Codex CLI",
                        "version": kwargs["version"],
                        "image": f"hibench/codex:{kwargs['version']}",
                    },
                    "prompt_file": str(kwargs["prompt_path"]),
                    "process": {"exit_code": 1, "timed_out": False},
                }
                body = {
                    "model": "gpt-test",
                    "input": "Hi",
                    "tools": [{"type": "function", "name": "shell"}],
                }
                (run_dir / "manifest.json").write_text(
                    json.dumps(manifest), encoding="utf-8"
                )
                (requests_dir / "0001.json").write_text(
                    json.dumps(
                        {
                            "method": "POST",
                            "path": "/v1/responses",
                            "body_text": json.dumps(body),
                            "json": body,
                        }
                    ),
                    encoding="utf-8",
                )
                return RunResult(
                    run_dir=run_dir,
                    summary=benchmark_summary(tool_count=1),
                    manifest=manifest,
                )

            with patch("hibench.automation.run_agent", side_effect=fake_run_agent):
                result = run_version_benchmark(
                    agent_id="codex",
                    version="0.1.0",
                    prompt_path="prompts/hi.txt",
                    out_dir=runs_dir,
                    build=False,
                )

            target = runs_dir / canonical_run_id("codex", "0.1.0", "prompts/hi.txt")
            self.assertEqual(result.status, "replaced")
            self.assertFalse(old_run.exists())
            self.assertTrue(target.exists())
            self.assertEqual(
                existing_run_dirs_for_agent_version(runs_dir, "codex", "0.1.0"),
                [target],
            )
            self.assertTrue((target / "benchmark_result.json").exists())
            self.assertEqual(result.tool_count, 1)

    def test_version_benchmark_purges_built_image_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"

            def fake_run_agent(**kwargs):
                run_dir = Path(kwargs["out_dir"]) / kwargs["run_id"]
                run_dir.mkdir(parents=True)
                return RunResult(
                    run_dir=run_dir, summary=benchmark_summary(), manifest={}
                )

            with patch("hibench.automation.run_agent", side_effect=fake_run_agent):
                with patch(
                    "hibench.automation.write_run_artifacts",
                    return_value=benchmark_summary(),
                ):
                    with patch("hibench.automation.purge_docker_image") as purge:
                        result = run_version_benchmark(
                            agent_id="codex",
                            version="0.1.0",
                            prompt_path="prompts/hi.txt",
                            out_dir=runs_dir,
                            build=True,
                        )

        self.assertEqual(result.status, "created")
        purge.assert_called_once_with("hibench/codex:0.1.0")

    def test_version_benchmark_errors_when_no_primary_request_is_captured(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"

            def fake_run_agent(**kwargs):
                run_dir = Path(kwargs["out_dir"]) / kwargs["run_id"]
                run_dir.mkdir(parents=True)
                return RunResult(
                    run_dir=run_dir,
                    summary=benchmark_summary(
                        has_primary_request=False,
                        total_body_tokens=0,
                        tool_count=0,
                    ),
                    manifest={
                        "process": {"exit_code": None, "timed_out": True},
                    },
                )

            with patch("hibench.automation.run_agent", side_effect=fake_run_agent):
                with patch("hibench.automation.purge_docker_image") as purge:
                    with self.assertRaisesRegex(
                        RuntimeError, "no primary request captured"
                    ):
                        run_version_benchmark(
                            agent_id="codex",
                            version="0.1.0",
                            prompt_path="prompts/hi.txt",
                            out_dir=runs_dir,
                            build=True,
                        )

                    self.assertFalse(
                        (
                            runs_dir
                            / canonical_run_id("codex", "0.1.0", "prompts/hi.txt")
                        ).exists()
                    )

        purge.assert_called_once_with("hibench/codex:0.1.0")

    def test_export_skips_runs_without_primary_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs_dir = root / "runs"
            results_dir = root / "results"
            no_primary = runs_dir / "codex-0.1.0-hi"
            primary = runs_dir / "codex-0.2.0-hi"
            for run_dir, version, has_primary in (
                (no_primary, "0.1.0", False),
                (primary, "0.2.0", True),
            ):
                (run_dir / "requests").mkdir(parents=True)
                (run_dir / "benchmark_result.json").write_text(
                    json.dumps(
                        {
                            "run": {
                                "run_id": run_dir.name,
                                "agent_id": "codex",
                                "agent_version": version,
                                "has_primary_request": has_primary,
                            },
                            "tools": [],
                            "mcp": [],
                            "subagents": [],
                            "skills": [],
                            "text_fields": [],
                        }
                    ),
                    encoding="utf-8",
                )

            manifest = export_benchmark_results(runs_dir, results_dir)
            rows = (results_dir / "runs.csv").read_text(encoding="utf-8")

        self.assertEqual(manifest["source_run_count"], 2)
        self.assertEqual(manifest["skipped_no_primary_run_count"], 1)
        self.assertIn("0.2.0", rows)
        self.assertNotIn("0.1.0", rows)

    def test_version_benchmark_purges_built_image_when_run_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            with patch(
                "hibench.automation.run_agent", side_effect=RuntimeError("run failed")
            ):
                with patch("hibench.automation.purge_docker_image") as purge:
                    with self.assertRaises(RuntimeError):
                        run_version_benchmark(
                            agent_id="codex",
                            version="0.1.0",
                            prompt_path="prompts/hi.txt",
                            out_dir=runs_dir,
                            build=True,
                        )

        purge.assert_called_once_with("hibench/codex:0.1.0")

    def test_version_benchmark_keeps_existing_image_for_no_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"

            def fake_run_agent(**kwargs):
                run_dir = Path(kwargs["out_dir"]) / kwargs["run_id"]
                run_dir.mkdir(parents=True)
                return RunResult(
                    run_dir=run_dir, summary=benchmark_summary(), manifest={}
                )

            with patch("hibench.automation.run_agent", side_effect=fake_run_agent):
                with patch(
                    "hibench.automation.write_run_artifacts",
                    return_value=benchmark_summary(),
                ):
                    with patch("hibench.automation.purge_docker_image") as purge:
                        run_version_benchmark(
                            agent_id="codex",
                            version="0.1.0",
                            prompt_path="prompts/hi.txt",
                            out_dir=runs_dir,
                            build=False,
                        )

        purge.assert_not_called()

    def test_version_benchmark_skip_existing_ignores_invalid_canonical_dir(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            target = runs_dir / canonical_run_id("codex", "0.1.0", "prompts/hi.txt")
            target.mkdir(parents=True)
            (target / "stale.txt").write_text("invalid run", encoding="utf-8")

            def fake_run_agent(**kwargs):
                run_dir = Path(kwargs["out_dir"]) / kwargs["run_id"]
                run_dir.mkdir(parents=True)
                (run_dir / "fresh.txt").write_text("new run", encoding="utf-8")
                return RunResult(
                    run_dir=run_dir, summary=benchmark_summary(), manifest={}
                )

            with patch(
                "hibench.automation.run_agent", side_effect=fake_run_agent
            ) as run_agent:
                with patch(
                    "hibench.automation.write_run_artifacts",
                    return_value=benchmark_summary(),
                ):
                    result = run_version_benchmark(
                        agent_id="codex",
                        version="0.1.0",
                        prompt_path="prompts/hi.txt",
                        out_dir=runs_dir,
                        build=False,
                        skip_existing=True,
                    )

            self.assertEqual(result.status, "replaced")
            self.assertTrue(run_agent.called)
            self.assertFalse((target / "stale.txt").exists())
            self.assertEqual(
                (target / "fresh.txt").read_text(encoding="utf-8"), "new run"
            )

    def test_version_benchmark_skip_existing_retries_no_primary_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            target = runs_dir / canonical_run_id("codex", "0.1.0", "prompts/hi.txt")
            target.mkdir(parents=True)
            (target / "benchmark_result.json").write_text(
                json.dumps(
                    {
                        "run": {
                            "agent_id": "codex",
                            "agent_version": "0.1.0",
                            "has_primary_request": False,
                        }
                    }
                ),
                encoding="utf-8",
            )

            def fake_run_agent(**kwargs):
                run_dir = Path(kwargs["out_dir"]) / kwargs["run_id"]
                run_dir.mkdir(parents=True)
                (run_dir / "fresh.txt").write_text("new run", encoding="utf-8")
                return RunResult(
                    run_dir=run_dir, summary=benchmark_summary(), manifest={}
                )

            with patch(
                "hibench.automation.run_agent", side_effect=fake_run_agent
            ) as run_agent:
                with patch(
                    "hibench.automation.write_run_artifacts",
                    return_value=benchmark_summary(),
                ):
                    result = run_version_benchmark(
                        agent_id="codex",
                        version="0.1.0",
                        prompt_path="prompts/hi.txt",
                        out_dir=runs_dir,
                        build=False,
                        skip_existing=True,
                    )

            self.assertEqual(result.status, "replaced")
            self.assertTrue(run_agent.called)
            self.assertEqual(result.replaced_run_dirs, [str(target)])
            self.assertEqual(
                (target / "fresh.txt").read_text(encoding="utf-8"), "new run"
            )

    def test_version_benchmark_restores_canonical_run_when_artifact_write_fails(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            target = runs_dir / canonical_run_id("codex", "0.1.0", "prompts/hi.txt")
            target.mkdir(parents=True)
            sentinel = target / "sentinel.txt"
            sentinel.write_text("old canonical", encoding="utf-8")
            (target / "manifest.json").write_text(
                json.dumps({"agent": {"id": "codex", "version": "0.1.0"}}),
                encoding="utf-8",
            )

            def fake_run_agent(**kwargs):
                run_dir = Path(kwargs["out_dir"]) / kwargs["run_id"]
                (run_dir / "requests").mkdir(parents=True)
                (run_dir / "manifest.json").write_text(
                    json.dumps(
                        {"agent": {"id": kwargs["agent_id"], "version": "0.1.0"}}
                    ),
                    encoding="utf-8",
                )
                return RunResult(
                    run_dir=run_dir, summary=benchmark_summary(), manifest={}
                )

            with patch("hibench.automation.run_agent", side_effect=fake_run_agent):
                with patch(
                    "hibench.automation.write_run_artifacts",
                    side_effect=RuntimeError("artifact failure"),
                ):
                    with self.assertRaises(RuntimeError):
                        run_version_benchmark(
                            agent_id="codex",
                            version="0.1.0",
                            prompt_path="prompts/hi.txt",
                            out_dir=runs_dir,
                            build=False,
                        )

            self.assertTrue(target.exists())
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "old canonical")


if __name__ == "__main__":
    unittest.main()
