from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import ANY, MagicMock, patch

from hibench.__main__ import cmd_benchmark


class CliTests(unittest.TestCase):
    def benchmark_args(self, **overrides) -> SimpleNamespace:
        values = dict(
            agent="codex",
            prompt="prompts/hi.txt",
            out="runs",
            timeout=30,
            versions_dir="agent_versions",
            versions_timeout=60,
            use_local_versions=True,
            requested_versions=None,
            max_versions=2,
            initial_version_limit=0,
            include_platform_versions=False,
            no_build=True,
            dry_run=False,
            skip_existing=False,
            rerun_existing=False,
            stop_on_error=False,
            results_out="results",
            no_export=False,
        )
        values.update(overrides)
        return SimpleNamespace(**values)

    def expected_benchmark_kwargs(self, **overrides) -> dict:
        values = dict(
            prompt_path="prompts/hi.txt",
            out_dir="runs",
            timeout=30,
            versions_dir="agent_versions",
            versions_timeout=60,
            use_local_versions=True,
            requested_versions=None,
            max_versions=2,
            initial_version_limit=None,
            include_platform_versions=False,
            build=False,
            dry_run=False,
            skip_existing=False,
            rerun_existing=False,
            stop_on_error=False,
            results_out="results",
            export_results=True,
        )
        values.update(overrides)
        return values

    def test_benchmark_command_delegates_batch_workflow_to_automation(self) -> None:
        args = self.benchmark_args()
        batch = SimpleNamespace(has_errors=False)

        with patch(
            "hibench.__main__.run_benchmark_batch", return_value=batch
        ) as run_batch:
            with patch("hibench.__main__.print_benchmark_batch_report") as print_report:
                exit_code = cmd_benchmark(args)

        self.assertEqual(exit_code, 0)
        run_batch.assert_called_once_with(
            agent_id="codex",
            **self.expected_benchmark_kwargs(),
        )
        print_report.assert_called_once_with(batch, console=ANY)

    def test_benchmark_all_delegates_all_agent_workflow_to_automation(self) -> None:
        args = self.benchmark_args(agent="all", max_versions=1)
        batches = SimpleNamespace(has_errors=True)
        progress = MagicMock()
        progress.__enter__.return_value = progress
        progress.__exit__.return_value = None

        with patch(
            "hibench.__main__.run_benchmark_batches", return_value=batches
        ) as run_batches:
            with patch(
                "hibench.__main__.BenchmarkAllProgress", return_value=progress
            ) as progress_cls:
                with patch(
                    "hibench.__main__.print_benchmark_batches_report"
                ) as print_report:
                    exit_code = cmd_benchmark(args)

        self.assertEqual(exit_code, 1)
        run_batches.assert_called_once_with(
            **self.expected_benchmark_kwargs(max_versions=1),
            on_agent_progress=progress,
        )
        progress_cls.assert_called_once_with(console=ANY)
        print_report.assert_called_once_with(batches, console=ANY)

    def test_benchmark_all_rejects_requested_versions(self) -> None:
        args = self.benchmark_args(agent="all", requested_versions=["0.1.0"])

        with patch("hibench.__main__.run_benchmark_batches") as run_batches:
            with patch("hibench.__main__.Console") as console:
                exit_code = cmd_benchmark(args)

        self.assertEqual(exit_code, 2)
        run_batches.assert_not_called()
        self.assertTrue(console.return_value.print.called)
        self.assertIn(
            "does not support --version",
            console.return_value.print.call_args.args[0],
        )


if __name__ == "__main__":
    unittest.main()
