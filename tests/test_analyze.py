import csv
import json
from pathlib import Path
import tempfile
import unittest

import tiktoken

from hibench.analyze import count_tokens, summarize_request, summarize_run
from hibench.benchmark import (
    export_benchmark_results,
    format_benchmark_report,
    write_run_artifacts,
)


class AnalyzeTests(unittest.TestCase):
    def test_count_tokens_uses_tiktoken(self) -> None:
        expected = len(
            tiktoken.get_encoding("o200k_base").encode(
                "hello world", disallowed_special=()
            )
        )
        self.assertEqual(count_tokens("hello world"), expected)

    def test_summarize_request_extracts_tools_and_markers(self) -> None:
        record = {
            "method": "POST",
            "path": "/v1/responses",
            "body_text": "{}",
            "json": {
                "instructions": "You are a coding agent.",
                "input": [{"role": "user", "content": "Hi"}],
                "tools": [
                    {"type": "function", "name": "shell"},
                    {"type": "mcp", "name": "mcp_browser"},
                ],
                "sub_agents": [{"name": "reviewer"}],
            },
        }
        summary = summarize_request(record)
        self.assertEqual(summary["tools"]["count"], 2)
        self.assertEqual(summary["mcp"]["count"], 1)
        self.assertEqual(summary["subagents"]["count"], 1)
        self.assertTrue(summary["mcp"]["items"][0]["is_counted"])
        self.assertTrue(summary["subagents"]["items"][0]["is_counted"])
        self.assertEqual(
            summary["tools"]["items"][0]["tokens"],
            count_tokens(
                json.dumps(
                    record["json"]["tools"][0],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            ),
        )
        self.assertEqual(
            summary["text_fields"]["tokens"],
            count_tokens("You are a coding agent.") + count_tokens("Hi"),
        )
        self.assertEqual(
            summary["text_fields"]["by_category"]["system_prompt"]["tokens"],
            count_tokens("You are a coding agent."),
        )
        self.assertEqual(
            summary["text_fields"]["by_category"]["user_prompt"]["tokens"],
            count_tokens("Hi"),
        )
        self.assertEqual(
            summary["text_fields"]["by_source"]["main_instructions"]["tokens"],
            count_tokens("You are a coding agent."),
        )
        self.assertEqual(summary["tokenizer"]["encoding"], "o200k_base")
        self.assertEqual(summary["skills"]["count"], 0)
        self.assertEqual(summary.get("anthropic_total_body_tokens", 0), 0)

    def test_summarize_request_uses_fixed_benchmark_tokenizer(self) -> None:
        record = {
            "method": "POST",
            "path": "/v1/responses",
            "body_text": '{"model":"gpt-3.5-turbo","input":"hello world"}',
            "json": {"model": "gpt-3.5-turbo", "input": "hello world"},
        }
        summary = summarize_request(record)
        self.assertEqual(summary["tokenizer"]["source"], "benchmark_default")
        self.assertEqual(summary["tokenizer"]["encoding"], "o200k_base")
        self.assertEqual(summary["body_tokens"], count_tokens(record["body_text"]))
        self.assertEqual(
            summary["text_fields"]["by_category"]["user_prompt"]["tokens"],
            count_tokens("hello world"),
        )

    def test_schema_allows_blank_tokenizer_encoding_for_no_primary_runs(self) -> None:
        schema = json.loads(
            Path("schemas/benchmark_result.schema.json").read_text(encoding="utf-8")
        )
        tokenizer_schema = schema["properties"]["run"]["properties"][
            "tokenizer_encoding"
        ]
        self.assertIn("", tokenizer_schema["enum"])
        self.assertIn("o200k_base", tokenizer_schema["enum"])
        run_properties = schema["properties"]["run"]["properties"]
        self.assertIn("anthropic_total_body_tokens", run_properties)
        self.assertIn("anthropic_tokenizer_model", run_properties)

    def test_summarize_run_is_pure_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "20260613T000000Z-codex-hi"
            requests_dir = run_dir / "requests"
            requests_dir.mkdir(parents=True)
            body = {"model": "gpt-test", "input": "Hi"}
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

            summary = summarize_run(run_dir)

            self.assertEqual(summary["request_count"], 1)
            self.assertNotIn("benchmark", summary)
            self.assertFalse((run_dir / "summary.json").exists())
            self.assertFalse((run_dir / "benchmark_result.json").exists())

    def test_write_run_artifacts_writes_power_bi_friendly_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "20260613T000000Z-codex-hi"
            requests_dir = run_dir / "requests"
            requests_dir.mkdir(parents=True)
            manifest = {
                "run_id": run_dir.name,
                "agent": {
                    "id": "codex",
                    "display_name": "OpenAI Codex CLI",
                    "version": "0.139.0",
                    "image": "hibench/codex:0.139.0",
                },
                "prompt_file": "prompts/hi.txt",
                "started_at": "2026-06-13T00:00:00Z",
                "ended_at": "2026-06-13T00:00:01Z",
                "subject_workspace": "generated empty Git repository",
                "real_api_call": False,
                "process": {"exit_code": 1, "timed_out": False},
            }
            body = {
                "model": "gpt-test",
                "instructions": "System setup.",
                "input": [{"role": "user", "content": "Hi"}],
                "tools": [
                    {
                        "type": "function",
                        "name": "mcp_browser",
                        "description": "MCP browser tool",
                    }
                ],
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

            summary = write_run_artifacts(run_dir)
            result = json.loads(
                (run_dir / "benchmark_result.json").read_text(encoding="utf-8")
            )

            self.assertEqual(summary["benchmark"]["agent_id"], "codex")
            self.assertEqual(result["run"]["agent_version"], "0.139.0")
            self.assertEqual(result["run"]["anthropic_tokenizer_model"], "")
            self.assertEqual(result["run"]["anthropic_total_body_tokens"], 0)
            self.assertEqual(result["run"]["tool_count"], 1)
            self.assertEqual(
                result["run"]["system_prompt_tokens"], count_tokens("System setup.")
            )
            self.assertEqual(result["run"]["user_prompt_tokens"], count_tokens("Hi"))
            self.assertEqual(
                result["run"]["main_instructions_tokens"], count_tokens("System setup.")
            )
            self.assertEqual(result["run"]["skills_count"], 0)
            self.assertEqual(result["run"]["mcp_count"], 1)
            self.assertEqual(result["tools"][0]["tool_name"], "mcp_browser")
            self.assertGreater(result["tools"][0]["definition_tokens"], 0)
            self.assertTrue((run_dir / "benchmark_tables" / "run.csv").exists())
            self.assertTrue((run_dir / "benchmark_tables" / "tools.csv").exists())
            self.assertTrue((run_dir / "benchmark_tables" / "skills.csv").exists())

            report = format_benchmark_report(run_dir, summary)
            self.assertIn("HiBench benchmark report", report)
            self.assertIn("total_body_tokens", report)
            self.assertIn("system_prompt_tokens", report)
            self.assertIn("Instruction sources", report)
            self.assertIn("Skills", report)
            self.assertIn("mcp_browser", report)
            self.assertIn("Diagnostic totals across captured requests/retries", report)
            self.assertIn("benchmark_result_json", report)

            summary_sentinel = '{"sentinel":true}\n'
            (run_dir / "summary.json").write_text(summary_sentinel, encoding="utf-8")
            benchmark_before = (run_dir / "benchmark_result.json").read_text(
                encoding="utf-8"
            )
            export = export_benchmark_results(run_dir.parent, Path(tmp) / "results")
            self.assertEqual(export["run_count"], 1)
            self.assertTrue((Path(tmp) / "results" / "runs.csv").exists())
            self.assertEqual(
                (run_dir / "summary.json").read_text(encoding="utf-8"), summary_sentinel
            )
            self.assertEqual(
                (run_dir / "benchmark_result.json").read_text(encoding="utf-8"),
                benchmark_before,
            )

    def test_benchmark_report_handles_no_primary_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "no-primary-codex-hi"
            (run_dir / "requests").mkdir(parents=True)
            (run_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "run_id": run_dir.name,
                        "agent": {
                            "id": "codex",
                            "display_name": "OpenAI Codex CLI",
                            "version": "0.139.0",
                        },
                        "process": {"exit_code": 1, "timed_out": False},
                    }
                ),
                encoding="utf-8",
            )

            summary = write_run_artifacts(run_dir)
            report = format_benchmark_report(run_dir, summary)

        self.assertIn("No primary POST request was captured", report)
        self.assertIn("tokenizer:", report)
        self.assertIn("Diagnostic totals across captured requests/retries", report)

    def test_export_builds_missing_result_without_writing_source_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "20260613T000001Z-codex-hi"
            requests_dir = run_dir / "requests"
            requests_dir.mkdir(parents=True)
            manifest = {
                "run_id": run_dir.name,
                "agent": {
                    "id": "codex",
                    "display_name": "OpenAI Codex CLI",
                    "version": "0.139.0",
                },
                "prompt_file": "prompts/hi.txt",
            }
            body = {"model": "gpt-test", "input": "Hi"}
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

            export = export_benchmark_results(run_dir.parent, Path(tmp) / "results")

            self.assertEqual(export["run_count"], 1)
            self.assertFalse((run_dir / "summary.json").exists())
            self.assertFalse((run_dir / "benchmark_result.json").exists())
            self.assertIn(
                run_dir.name,
                (Path(tmp) / "results" / "runs.csv").read_text(encoding="utf-8"),
            )

    def test_export_keeps_one_result_per_agent_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            old_run = runs_dir / "20260613T000000Z-codex-hi"
            new_run = runs_dir / "codex-0.139.0-hi"
            for run_dir, run_id, ended_at, tool_name in (
                (
                    old_run,
                    "20260613T000000Z-codex-hi",
                    "2026-06-13T00:00:00Z",
                    "old_tool",
                ),
                (new_run, "codex-0.139.0-hi", "2026-06-13T01:00:00Z", "new_tool"),
            ):
                (run_dir / "requests").mkdir(parents=True)
                result = {
                    "schema_version": "hibench.benchmark.v1",
                    "run": {
                        "run_id": run_id,
                        "run_dir": str(run_dir),
                        "agent_id": "codex",
                        "agent_version": "0.139.0",
                        "ended_at": ended_at,
                        "has_primary_request": True,
                    },
                    "tools": [
                        {
                            "run_id": run_id,
                            "agent_id": "codex",
                            "agent_version": "0.139.0",
                            "tool_name": tool_name,
                        }
                    ],
                    "mcp": [],
                    "subagents": [],
                    "skills": [],
                    "text_fields": [],
                }
                (run_dir / "benchmark_result.json").write_text(
                    json.dumps(result), encoding="utf-8"
                )

            export = export_benchmark_results(runs_dir, Path(tmp) / "results")

            self.assertEqual(export["source_run_count"], 2)
            self.assertEqual(export["run_count"], 1)
            self.assertEqual(export["deduplicated_run_count"], 1)
            with (Path(tmp) / "results" / "runs.csv").open(
                encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["run_id"] for row in rows], ["codex-0.139.0-hi"])
            self.assertEqual(rows[0]["agent_id"], "codex")
            self.assertEqual(rows[0]["agent_version"], "0.139.0")
            tools_csv = (Path(tmp) / "results" / "tools.csv").read_text(
                encoding="utf-8"
            )
            self.assertIn("new_tool", tools_csv)
            self.assertNotIn("old_tool", tools_csv)
