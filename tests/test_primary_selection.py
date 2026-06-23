import json
from pathlib import Path
import tempfile
import unittest

from hibench.analyze import summarize_run


def write_request(
    requests_dir: Path,
    index: int,
    path: str,
    body: dict[str, object],
    *,
    method: str = "POST",
) -> None:
    (requests_dir / f"{index:04d}.json").write_text(
        json.dumps(
            {
                "method": method,
                "path": path,
                "body_text": json.dumps(body),
                "json": body,
            }
        ),
        encoding="utf-8",
    )


class PrimaryRequestSelectionTests(unittest.TestCase):
    def test_summarize_run_prefers_generation_post_over_preflight_post(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "20260614T000000Z-hermes-hi"
            requests_dir = run_dir / "requests"
            requests_dir.mkdir(parents=True)
            preflight = {"name": "gpt-5"}
            body = {
                "model": "gpt-5",
                "messages": [
                    {"role": "developer", "content": "Hermes instructions."},
                    {"role": "user", "content": "Hi"},
                ],
            }
            write_request(requests_dir, 1, "/api/show", preflight)
            write_request(requests_dir, 2, "/v1/chat/completions", body)

            summary = summarize_run(run_dir, parser_id="hermes")

        self.assertEqual(summary["primary_request_index"], 2)
        self.assertEqual(summary["primary_request"]["path"], "/v1/chat/completions")
        self.assertEqual(summary["primary_request"]["model"], "gpt-5")

    def test_summarize_run_skips_grok_cli_session_title_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "20260614T000000Z-grok-cli-hi"
            requests_dir = run_dir / "requests"
            requests_dir.mkdir(parents=True)
            title_body = {
                "model": "grok-build",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are tasked with generating the session title.",
                    },
                    {"role": "user", "content": "<user_query>\nHi\n</user_query>"},
                ],
                "tools": [
                    {
                        "type": "function",
                        "function": {"name": "session_title", "parameters": {}},
                    }
                ],
            }
            body = {
                "model": "gpt-5",
                "messages": [
                    {"role": "system", "content": "Grok instructions."},
                    {"role": "user", "content": "Hi"},
                ],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "run_terminal_command",
                            "description": "Run a shell command.",
                            "parameters": {},
                        },
                    }
                ],
            }
            for index, request_body in enumerate((title_body, body), start=1):
                write_request(requests_dir, index, "/v1/chat/completions", request_body)

            summary = summarize_run(run_dir, parser_id="grok-cli")

        self.assertEqual(summary["primary_request_index"], 2)
        self.assertEqual(summary["primary_request"]["model"], "gpt-5")

    def test_summarize_run_skips_gemini_count_tokens_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "20260614T000000Z-gemini-cli-hi"
            requests_dir = run_dir / "requests"
            requests_dir.mkdir(parents=True)
            count_body = {
                "contents": [{"role": "user", "parts": [{"text": "Hi"}]}],
            }
            body = {
                "contents": [
                    {"role": "user", "parts": [{"text": "<session_context />"}]},
                    {"role": "user", "parts": [{"text": "Hi"}]},
                ],
                "systemInstruction": {
                    "role": "user",
                    "parts": [{"text": "You are Gemini CLI."}],
                },
            }
            write_request(
                requests_dir,
                1,
                "/v1beta/models/gemini-2.5-flash:countTokens",
                count_body,
            )
            write_request(
                requests_dir,
                2,
                "/v1beta/models/gemini-2.5-flash:streamGenerateContent?alt=sse",
                body,
            )

            summary = summarize_run(run_dir, parser_id="gemini-cli")

        self.assertEqual(summary["primary_request_index"], 2)
        self.assertEqual(summary["primary_request"]["model"], "gemini-2.5-flash")

    def test_summarize_run_does_not_fallback_to_grok_cli_session_title(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "20260614T000000Z-grok-cli-hi"
            requests_dir = run_dir / "requests"
            requests_dir.mkdir(parents=True)
            title_body = {
                "model": "grok-build",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are tasked with generating the session title.",
                    },
                    {"role": "user", "content": "<user_query>\nHi\n</user_query>"},
                ],
                "tools": [
                    {
                        "type": "function",
                        "function": {"name": "session_title", "parameters": {}},
                    }
                ],
            }
            write_request(requests_dir, 1, "/v1/chat/completions", title_body)

            summary = summarize_run(run_dir, parser_id="grok-cli")
            generic_summary = summarize_run(run_dir)

        self.assertIsNone(summary["primary_request_index"])
        self.assertIsNone(summary["primary_request"])
        self.assertEqual(summary["post_request_count"], 1)
        self.assertEqual(generic_summary["primary_request_index"], 1)
        self.assertEqual(generic_summary["primary_request"]["model"], "grok-build")
