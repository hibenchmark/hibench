from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hibench.anthropic_tokens import (
    RateLimiter,
    anthropic_token_counter_from_env,
    anthropic_tokenizer_settings_from_env,
    count_run_anthropic_tokens,
)


def write_minimal_benchmark_result(run_dir: Path) -> None:
    result = {
        "run": {
            "agent_id": "codex",
            "agent_version": "0.1.0",
            "run_id": run_dir.name,
            "has_primary_request": True,
            "primary_request_index": 1,
            "anthropic_tokenizer_model": "",
            "anthropic_total_body_tokens": 0,
        },
        "tools": [],
        "mcp": [],
        "subagents": [],
        "skills": [],
        "text_fields": [],
    }
    (run_dir / "benchmark_result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    (run_dir / "summary.json").write_text(
        json.dumps({"benchmark": {"has_primary_request": True}}) + "\n",
        encoding="utf-8",
    )


class AnthropicTokenTests(unittest.TestCase):
    def test_settings_load_api_key_and_config_from_dotenv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / ".env").write_text(
                "\n".join(
                    [
                        "ANTHROPIC_API_KEY=dotenv-key",
                        "HIBENCH_ANTHROPIC_TOKENIZER_MODEL=claude-dotenv",
                        "HIBENCH_ANTHROPIC_TOKENIZER_RPM=12",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            old_cwd = Path.cwd()
            try:
                os.chdir(path)
                with patch.dict(os.environ, {}, clear=True):
                    settings = anthropic_tokenizer_settings_from_env()
                    counter = anthropic_token_counter_from_env()
            finally:
                os.chdir(old_cwd)

        self.assertTrue(settings["enabled"])
        self.assertEqual(settings["api_key_present"], True)
        self.assertEqual(settings["model"], "claude-dotenv")
        self.assertEqual(settings["rpm"], 12.0)
        self.assertEqual(Path(settings["dotenv_path"]).name, ".env")
        self.assertIsNotNone(counter)
        assert counter is not None
        self.assertEqual(counter.api_key, "dotenv-key")

    def test_shell_env_wins_over_dotenv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / ".env").write_text(
                "ANTHROPIC_API_KEY=dotenv-key\n", encoding="utf-8"
            )
            old_cwd = Path.cwd()
            try:
                os.chdir(path)
                with patch.dict(
                    os.environ, {"ANTHROPIC_API_KEY": "shell-key"}, clear=True
                ):
                    counter = anthropic_token_counter_from_env()
            finally:
                os.chdir(old_cwd)

        self.assertIsNotNone(counter)
        assert counter is not None
        self.assertEqual(counter.api_key, "shell-key")

    def test_count_run_sends_exact_captured_body_text_and_updates_total(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "codex-0.1.0-hi"
            requests_dir = run_dir / "requests"
            requests_dir.mkdir(parents=True)
            body_text = '{"model":"gpt-5","input":"Hi"}'
            (requests_dir / "0001.json").write_text(
                json.dumps(
                    {
                        "method": "POST",
                        "path": "/v1/responses",
                        "body_text": body_text,
                        "json": {"model": "gpt-5", "input": "Hi"},
                    }
                ),
                encoding="utf-8",
            )
            write_minimal_benchmark_result(run_dir)

            with patch(
                "hibench.anthropic_tokens.anthropic_count_tokens", return_value=123
            ) as count_tokens:
                counted = count_run_anthropic_tokens(
                    run_dir,
                    api_key="test-key",
                    model="claude-test",
                    limiter=RateLimiter(0),
                )

            self.assertTrue(counted.updated)
            self.assertEqual(counted.total_tokens, 123)
            self.assertEqual(count_tokens.call_args.kwargs["body_text"], body_text)

            result = json.loads(
                (run_dir / "benchmark_result.json").read_text(encoding="utf-8")
            )
            self.assertEqual(result["run"]["anthropic_tokenizer_model"], "claude-test")
            self.assertEqual(result["run"]["anthropic_total_body_tokens"], 123)

            summary = json.loads(
                (run_dir / "summary.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                summary["benchmark"]["anthropic_tokenizer_model"], "claude-test"
            )
            self.assertEqual(summary["benchmark"]["anthropic_total_body_tokens"], 123)


if __name__ == "__main__":
    unittest.main()