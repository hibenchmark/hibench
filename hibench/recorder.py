from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
from typing import Any


REDACTED_HEADERS = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "x-goog-api-key",
    "openai-api-key",
}
SYNTHETIC_ASSISTANT_TEXT = "HiBench capture complete."


class RequestRecorder:
    def __init__(
        self, output_dir: str | Path, host: str = "0.0.0.0", port: int = 0
    ) -> None:
        self.output_dir = Path(output_dir)
        self.requests_dir = self.output_dir / "requests"
        self.requests_dir.mkdir(parents=True, exist_ok=True)
        self.host = host
        self._lock = threading.Lock()
        self._records: list[dict[str, Any]] = []
        self.first_post = threading.Event()

        recorder = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                recorder.record(self.command, self.path, dict(self.headers), b"")
                self._send_json(200, {"object": "list", "data": []})

            def do_HEAD(self) -> None:  # noqa: N802
                recorder.record(self.command, self.path, dict(self.headers), b"")
                self.send_response(200)
                self.end_headers()

            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length", "0") or "0")
                body = self.rfile.read(length)
                record = recorder.record(
                    self.command, self.path, dict(self.headers), body
                )
                request_json = (
                    record.get("json") if isinstance(record.get("json"), dict) else {}
                )
                if recorder.is_anthropic_count_tokens_path(self.path):
                    self._send_json(200, recorder.anthropic_count_tokens_response())
                    return
                if recorder.is_anthropic_messages_path(self.path):
                    if request_json.get("stream") is True:
                        self._send_sse(
                            recorder.anthropic_stream_events(request_json),
                            include_done=False,
                        )
                    else:
                        self._send_json(
                            200, recorder.anthropic_message_response(request_json)
                        )
                    return
                if recorder.is_responses_path(self.path):
                    if request_json.get("stream") is True:
                        self._send_sse(recorder.responses_stream_events(request_json))
                    else:
                        self._send_json(200, recorder.responses_response(request_json))
                    return
                if recorder.is_chat_completions_path(self.path):
                    if request_json.get("stream") is True:
                        self._send_sse(recorder.chat_stream_events(request_json))
                    else:
                        self._send_json(
                            200, recorder.chat_completion_response(request_json)
                        )
                    return
                if recorder.is_gemini_count_tokens_path(self.path):
                    self._send_json(200, recorder.gemini_count_tokens_response())
                    return
                if recorder.is_gemini_generate_content_path(self.path):
                    if recorder.is_gemini_stream_generate_content_path(self.path):
                        self._send_data_sse(
                            recorder.gemini_generate_content_events(request_json)
                        )
                    else:
                        self._send_json(
                            200, recorder.gemini_generate_content_response(request_json)
                        )
                    return
                self._send_json(200, recorder.generic_capture_response())

            def do_OPTIONS(self) -> None:  # noqa: N802
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Headers", "*")
                self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
                self.end_headers()

            def log_message(self, format: str, *args: Any) -> None:
                return

            def _send_json(self, status: int, payload: dict[str, Any]) -> None:
                data = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _send_sse(
                self, events: list[dict[str, Any]], include_done: bool = True
            ) -> None:
                chunks: list[str] = []
                for event in events:
                    event_type = str(event.get("type") or "message")
                    chunks.append(f"event: {event_type}\n")
                    chunks.append(f"data: {json.dumps(event, ensure_ascii=False)}\n\n")
                if include_done:
                    chunks.append("data: [DONE]\n\n")
                data = "".join(chunks).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                self.wfile.flush()

            def _send_data_sse(self, events: list[dict[str, Any]]) -> None:
                data = "".join(
                    f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                    for event in events
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                self.wfile.flush()

        self.server = ThreadingHTTPServer((host, port), Handler)
        self.port = int(self.server.server_address[1])
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> "RequestRecorder":
        self.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.stop()

    @property
    def host_base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    @property
    def localhost_base_url(self) -> str:
        return f"http://localhost:{self.port}/v1"

    @property
    def docker_base_url(self) -> str:
        return f"http://host.docker.internal:{self.port}/v1"

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self._thread.join(timeout=5)

    def wait_for_post(self, timeout: float) -> bool:
        return self.first_post.wait(timeout)

    def record(
        self, method: str, path: str, headers: dict[str, str], body: bytes
    ) -> dict[str, Any]:
        try:
            body_text = body.decode("utf-8")
        except UnicodeDecodeError:
            body_text = body.decode("utf-8", errors="replace")

        parsed_json = None
        if body_text:
            try:
                parsed_json = json.loads(body_text)
            except json.JSONDecodeError:
                parsed_json = None

        safe_headers = {
            key: ("<redacted>" if key.lower() in REDACTED_HEADERS else value)
            for key, value in sorted(headers.items(), key=lambda item: item[0].lower())
        }

        with self._lock:
            index = len(self._records) + 1
            record = {
                "index": index,
                "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "method": method,
                "path": path,
                "headers": safe_headers,
                "body_text": body_text,
                "json": parsed_json,
            }
            self._records.append(record)
            request_path = self.requests_dir / f"{index:04d}.json"
            request_path.write_text(
                json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

        if method.upper() == "POST":
            self.first_post.set()

        return record

    @staticmethod
    def path_without_query(path: str) -> str:
        return path.split("?", 1)[0].rstrip("/")

    @staticmethod
    def is_responses_path(path: str) -> bool:
        return RequestRecorder.path_without_query(path).endswith("/responses")

    @staticmethod
    def is_chat_completions_path(path: str) -> bool:
        return RequestRecorder.path_without_query(path).endswith("/chat/completions")

    @staticmethod
    def is_anthropic_count_tokens_path(path: str) -> bool:
        return RequestRecorder.path_without_query(path).endswith(
            "/messages/count_tokens"
        )

    @staticmethod
    def is_anthropic_messages_path(path: str) -> bool:
        return RequestRecorder.path_without_query(path).endswith("/messages")

    @staticmethod
    def is_gemini_count_tokens_path(path: str) -> bool:
        return RequestRecorder.path_without_query(path).endswith(":countTokens")

    @staticmethod
    def is_gemini_generate_content_path(path: str) -> bool:
        normalized = RequestRecorder.path_without_query(path)
        return normalized.endswith(
            (":generateContent", ":streamGenerateContent")
        )

    @staticmethod
    def is_gemini_stream_generate_content_path(path: str) -> bool:
        return RequestRecorder.path_without_query(path).endswith(
            ":streamGenerateContent"
        )

    @staticmethod
    def _model(request_json: dict[str, Any]) -> str:
        model = request_json.get("model")
        return str(model) if model else "hibench-capture-model"

    @staticmethod
    def _created() -> int:
        return int(time.time())

    def generic_capture_response(self) -> dict[str, Any]:
        return {
            "object": "hibench.capture",
            "status": "completed",
            "message": "hibench captured this request; no upstream model call was made",
        }

    def responses_message(self) -> dict[str, Any]:
        return {
            "id": "msg_hibench_capture",
            "type": "message",
            "status": "completed",
            "role": "assistant",
            "content": [
                {
                    "type": "output_text",
                    "text": SYNTHETIC_ASSISTANT_TEXT,
                    "annotations": [],
                }
            ],
        }

    def responses_response(
        self, request_json: dict[str, Any], *, status: str = "completed"
    ) -> dict[str, Any]:
        output = [] if status != "completed" else [self.responses_message()]
        return {
            "id": "resp_hibench_capture",
            "object": "response",
            "created_at": self._created(),
            "status": status,
            "model": self._model(request_json),
            "output": output,
            "parallel_tool_calls": request_json.get("parallel_tool_calls", True),
            "tool_choice": request_json.get("tool_choice", "auto"),
            "tools": request_json.get("tools", []),
            "usage": {
                "input_tokens": 0,
                "input_tokens_details": {"cached_tokens": 0},
                "output_tokens": 1,
                "output_tokens_details": {"reasoning_tokens": 0},
                "total_tokens": 1,
            },
        }

    def responses_stream_events(
        self, request_json: dict[str, Any]
    ) -> list[dict[str, Any]]:
        in_progress = self.responses_response(request_json, status="in_progress")
        completed = self.responses_response(request_json, status="completed")
        message = self.responses_message()
        content_part = message["content"][0]
        return [
            {"type": "response.created", "sequence_number": 0, "response": in_progress},
            {
                "type": "response.in_progress",
                "sequence_number": 1,
                "response": in_progress,
            },
            {
                "type": "response.output_item.added",
                "sequence_number": 2,
                "output_index": 0,
                "item": {**message, "status": "in_progress", "content": []},
            },
            {
                "type": "response.content_part.added",
                "sequence_number": 3,
                "item_id": message["id"],
                "output_index": 0,
                "content_index": 0,
                "part": {**content_part, "text": ""},
            },
            {
                "type": "response.output_text.delta",
                "sequence_number": 4,
                "item_id": message["id"],
                "output_index": 0,
                "content_index": 0,
                "delta": SYNTHETIC_ASSISTANT_TEXT,
            },
            {
                "type": "response.output_text.done",
                "sequence_number": 5,
                "item_id": message["id"],
                "output_index": 0,
                "content_index": 0,
                "text": SYNTHETIC_ASSISTANT_TEXT,
            },
            {
                "type": "response.content_part.done",
                "sequence_number": 6,
                "item_id": message["id"],
                "output_index": 0,
                "content_index": 0,
                "part": content_part,
            },
            {
                "type": "response.output_item.done",
                "sequence_number": 7,
                "output_index": 0,
                "item": message,
            },
            {"type": "response.completed", "sequence_number": 8, "response": completed},
        ]

    def chat_completion_response(self, request_json: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": "chatcmpl-hibench-capture",
            "object": "chat.completion",
            "created": self._created(),
            "model": self._model(request_json),
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": SYNTHETIC_ASSISTANT_TEXT,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 1, "total_tokens": 1},
        }

    def chat_stream_events(self, request_json: dict[str, Any]) -> list[dict[str, Any]]:
        base = {
            "id": "chatcmpl-hibench-capture",
            "object": "chat.completion.chunk",
            "created": self._created(),
            "model": self._model(request_json),
        }
        return [
            {
                **base,
                "type": "chat.completion.chunk",
                "choices": [{"index": 0, "delta": {"role": "assistant"}}],
            },
            {
                **base,
                "type": "chat.completion.chunk",
                "choices": [
                    {"index": 0, "delta": {"content": SYNTHETIC_ASSISTANT_TEXT}}
                ],
            },
            {
                **base,
                "type": "chat.completion.chunk",
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            },
        ]

    def anthropic_count_tokens_response(self) -> dict[str, Any]:
        return {"input_tokens": 0}

    def anthropic_message_response(
        self, request_json: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "id": "msg_hibench_capture",
            "type": "message",
            "role": "assistant",
            "model": self._model(request_json),
            "content": [{"type": "text", "text": SYNTHETIC_ASSISTANT_TEXT}],
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 1},
        }

    def anthropic_stream_events(
        self, request_json: dict[str, Any]
    ) -> list[dict[str, Any]]:
        message = {
            "id": "msg_hibench_capture",
            "type": "message",
            "role": "assistant",
            "model": self._model(request_json),
            "content": [],
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }
        content_block = {"type": "text", "text": ""}
        return [
            {"type": "message_start", "message": message},
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": content_block,
            },
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": SYNTHETIC_ASSISTANT_TEXT},
            },
            {"type": "content_block_stop", "index": 0},
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                "usage": {"output_tokens": 1},
            },
            {"type": "message_stop"},
        ]

    def gemini_count_tokens_response(self) -> dict[str, Any]:
        return {"totalTokens": 0}

    def gemini_generate_content_response(
        self, request_json: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": SYNTHETIC_ASSISTANT_TEXT}],
                        "role": "model",
                    },
                    "finishReason": "STOP",
                    "index": 0,
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 0,
                "candidatesTokenCount": 1,
                "totalTokenCount": 1,
            },
            "modelVersion": self._model(request_json),
            "responseId": "gemini-hibench-capture",
        }

    def gemini_generate_content_events(
        self, request_json: dict[str, Any]
    ) -> list[dict[str, Any]]:
        return [self.gemini_generate_content_response(request_json)]
