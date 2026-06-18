from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from urllib.request import Request, urlopen

from hibench.recorder import RequestRecorder


class RecorderTests(unittest.TestCase):
    def test_responses_stream_post_is_captured_and_returns_success_sse(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            with RequestRecorder(Path(temp_name)) as recorder:
                request = Request(
                    f"{recorder.host_base_url}/responses",
                    data=json.dumps(
                        {"model": "gpt-test", "stream": True, "input": "Hi"}
                    ).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": "Bearer secret",
                    },
                    method="POST",
                )

                with urlopen(request, timeout=5) as response:  # noqa: S310
                    body = response.read().decode("utf-8")
                    content_type = response.headers.get("Content-Type", "")

            self.assertEqual(response.status, 200)
            self.assertIn("text/event-stream", content_type)
            self.assertIn("response.completed", body)
            self.assertIn("HiBench capture complete.", body)
            record = json.loads(
                (Path(temp_name) / "requests" / "0001.json").read_text(encoding="utf-8")
            )
            self.assertEqual(record["path"], "/v1/responses")
            self.assertEqual(record["headers"]["Authorization"], "<redacted>")
            self.assertEqual(record["json"]["model"], "gpt-test")

    def test_chat_completion_post_is_captured_and_returns_success_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            with RequestRecorder(Path(temp_name)) as recorder:
                request = Request(
                    f"{recorder.host_base_url}/chat/completions",
                    data=json.dumps(
                        {
                            "model": "gpt-test",
                            "messages": [{"role": "user", "content": "Hi"}],
                        }
                    ).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )

                with urlopen(request, timeout=5) as response:  # noqa: S310
                    payload = json.loads(response.read().decode("utf-8"))

            self.assertEqual(response.status, 200)
            self.assertEqual(payload["object"], "chat.completion")
            self.assertEqual(
                payload["choices"][0]["message"]["content"], "HiBench capture complete."
            )
            record = json.loads(
                (Path(temp_name) / "requests" / "0001.json").read_text(encoding="utf-8")
            )
            self.assertEqual(record["path"], "/v1/chat/completions")
            self.assertEqual(record["json"]["model"], "gpt-test")

    def test_anthropic_message_post_is_captured_and_returns_success_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            with RequestRecorder(Path(temp_name)) as recorder:
                request = Request(
                    f"{recorder.host_base_url}/messages?beta=true",
                    data=json.dumps(
                        {
                            "model": "claude-sonnet-4-5",
                            "messages": [{"role": "user", "content": "Hi"}],
                        }
                    ).encode("utf-8"),
                    headers={"Content-Type": "application/json", "X-Api-Key": "secret"},
                    method="POST",
                )

                with urlopen(request, timeout=5) as response:  # noqa: S310
                    payload = json.loads(response.read().decode("utf-8"))

            self.assertEqual(response.status, 200)
            self.assertEqual(payload["type"], "message")
            self.assertEqual(payload["stop_reason"], "end_turn")
            self.assertEqual(payload["content"][0]["text"], "HiBench capture complete.")
            record = json.loads(
                (Path(temp_name) / "requests" / "0001.json").read_text(encoding="utf-8")
            )
            self.assertEqual(record["path"], "/v1/messages?beta=true")
            self.assertEqual(record["headers"]["X-Api-Key"], "<redacted>")
            self.assertEqual(record["json"]["model"], "claude-sonnet-4-5")

    def test_anthropic_stream_post_is_captured_and_returns_success_sse(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            with RequestRecorder(Path(temp_name)) as recorder:
                request = Request(
                    f"{recorder.host_base_url}/messages",
                    data=json.dumps(
                        {
                            "model": "claude-sonnet-4-5",
                            "stream": True,
                            "messages": [{"role": "user", "content": "Hi"}],
                        }
                    ).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )

                with urlopen(request, timeout=5) as response:  # noqa: S310
                    body = response.read().decode("utf-8")
                    content_type = response.headers.get("Content-Type", "")

            self.assertEqual(response.status, 200)
            self.assertIn("text/event-stream", content_type)
            self.assertIn("message_stop", body)
            self.assertIn("HiBench capture complete.", body)
            self.assertNotIn("[DONE]", body)


if __name__ == "__main__":
    unittest.main()
