from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .analyze import compact_json
from .benchmark_io import write_benchmark_result


ANTHROPIC_COUNT_PATH = "/v1/messages/count_tokens"
DEFAULT_API_KEY_ENV = "ANTHROPIC_API_KEY"
DEFAULT_BASE_URL = "https://api.anthropic.com"
DEFAULT_MODEL = "claude-opus-4-8"
DEFAULT_RPM = 90.0
ENV_DOTENV_PATH = "HIBENCH_ENV_FILE"
ENV_BASE_URL = "HIBENCH_ANTHROPIC_TOKENIZER_BASE_URL"
ENV_ENABLED = "HIBENCH_ANTHROPIC_TOKENIZER"
ENV_MODEL = "HIBENCH_ANTHROPIC_TOKENIZER_MODEL"
ENV_RPM = "HIBENCH_ANTHROPIC_TOKENIZER_RPM"
DOTENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class AnthropicRunTokenResult:
    run_path: Path
    status: str
    model: str = ""
    total_tokens: int = 0
    updated: bool = False
    error: str = ""


class RateLimiter:
    def __init__(self, rpm: float) -> None:
        self.interval = 60.0 / rpm if rpm > 0 else 0.0
        self.next_at = 0.0

    def wait(self) -> None:
        if self.interval <= 0:
            return
        now = time.monotonic()
        if self.next_at > now:
            time.sleep(self.next_at - now)
        self.next_at = max(now, self.next_at) + self.interval


class AnthropicTokenCounter:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        rpm: float = DEFAULT_RPM,
        limiter: RateLimiter | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.rpm = rpm
        self.limiter = limiter or RateLimiter(rpm)

    def count_run(
        self, run_path: str | Path, *, force: bool = False
    ) -> AnthropicRunTokenResult:
        return count_run_anthropic_tokens(
            run_path,
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model,
            limiter=self.limiter,
            force=force,
        )


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} does not contain a JSON object")
    return data


def _nearest_dotenv_path() -> Path | None:
    for directory in (Path.cwd(), *Path.cwd().parents):
        path = directory / ".env"
        if path.exists():
            return path
    return None


def _dotenv_path(path: str | Path | None = None) -> Path | None:
    raw_path = str(path or os.environ.get(ENV_DOTENV_PATH, "")).strip()
    if raw_path:
        return Path(raw_path).expanduser()
    return _nearest_dotenv_path()


def _unescape_double_quoted_dotenv(value: str) -> str:
    replacements = {
        "\\n": "\n",
        "\\r": "\r",
        "\\t": "\t",
        "\\\\": "\\",
        '\\"': '"',
        "\\$": "$",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    return value


def _dotenv_value(raw: str) -> str:
    value = raw.strip()
    if not value:
        return ""
    if value.startswith("'"):
        end = value.find("'", 1)
        return value[1:end] if end >= 1 else value[1:]
    if value.startswith('"'):
        end = value.find('"', 1)
        quoted = value[1:end] if end >= 1 else value[1:]
        return _unescape_double_quoted_dotenv(quoted)
    return re.sub(r"\s+#.*$", "", value).strip()


def _parse_dotenv_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("export "):
        stripped = stripped[7:].lstrip()
    key, sep, value = stripped.partition("=")
    if not sep:
        return None
    key = key.strip()
    if not DOTENV_KEY_RE.match(key):
        return None
    return key, _dotenv_value(value)


def load_dotenv_file(
    path: str | Path | None = None, *, override: bool = False
) -> Path | None:
    dotenv = _dotenv_path(path)
    if dotenv is None or not dotenv.exists():
        return None
    for line in dotenv.read_text(encoding="utf-8").splitlines():
        parsed = _parse_dotenv_line(line)
        if parsed is None:
            continue
        key, value = parsed
        if override or key not in os.environ:
            os.environ[key] = value
    return dotenv


def primary_request_record(run_path: Path, result: dict[str, Any]) -> dict[str, Any]:
    run = result.get("run") if isinstance(result.get("run"), dict) else {}
    primary_index = int(run.get("primary_request_index") or 0)
    if primary_index <= 0:
        raise ValueError(f"{run_path}: missing primary_request_index")
    request_paths = sorted((run_path / "requests").glob("*.json"))
    try:
        request_path = request_paths[primary_index - 1]
    except IndexError as exc:
        raise ValueError(f"{run_path}: primary request file is missing") from exc
    return read_json(request_path)


def captured_body_text(record: dict[str, Any]) -> str:
    body_text = record.get("body_text")
    if isinstance(body_text, str) and body_text:
        return body_text
    body = record.get("json")
    if isinstance(body, str):
        return body
    return compact_json(body)


def count_tokens_payload(body_text: str, model: str) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": body_text,
            }
        ],
    }


def retry_after_seconds(error: HTTPError) -> float | None:
    header = error.headers.get("retry-after")
    if not header:
        return None
    try:
        return max(0.0, float(header))
    except ValueError:
        return None


def anthropic_count_tokens(
    *,
    api_key: str,
    base_url: str,
    model: str,
    body_text: str,
    limiter: RateLimiter,
    max_retries: int = 5,
) -> int:
    url = base_url.rstrip("/") + ANTHROPIC_COUNT_PATH
    data = json.dumps(
        count_tokens_payload(body_text, model), ensure_ascii=False
    ).encode("utf-8")
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    for attempt in range(max_retries + 1):
        limiter.wait()
        request = Request(url, data=data, headers=headers, method="POST")
        try:
            with urlopen(request, timeout=120) as response:
                result = json.loads(response.read().decode("utf-8"))
            tokens = result.get("input_tokens")
            if not isinstance(tokens, int):
                raise ValueError(f"Anthropic response missing input_tokens: {result}")
            return tokens
        except HTTPError as error:
            retryable = error.code == 429 or 500 <= error.code < 600
            if not retryable or attempt >= max_retries:
                detail = error.read().decode("utf-8", errors="replace")
                raise RuntimeError(
                    f"Anthropic token count failed with HTTP {error.code}: {detail}"
                ) from error
            delay = retry_after_seconds(error) or min(60.0, 2.0**attempt)
            time.sleep(delay)
        except URLError as error:
            if attempt >= max_retries:
                raise RuntimeError(f"Anthropic token count failed: {error}") from error
            time.sleep(min(60.0, 2.0**attempt))

    raise RuntimeError("unreachable Anthropic retry state")


def _sync_summary(run_path: Path, run: dict[str, Any]) -> None:
    summary_path = run_path / "summary.json"
    if not summary_path.exists():
        return
    try:
        summary = read_json(summary_path)
    except (OSError, json.JSONDecodeError, ValueError):
        return
    benchmark = (
        summary.get("benchmark") if isinstance(summary.get("benchmark"), dict) else {}
    )
    if not benchmark:
        return
    benchmark["anthropic_tokenizer_model"] = run.get("anthropic_tokenizer_model", "")
    benchmark["anthropic_total_body_tokens"] = run.get(
        "anthropic_total_body_tokens", 0
    )
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def count_run_anthropic_tokens(
    run_path: str | Path,
    *,
    api_key: str,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    limiter: RateLimiter | None = None,
    force: bool = False,
) -> AnthropicRunTokenResult:
    run_dir = Path(run_path)
    result_path = run_dir / "benchmark_result.json"
    if not result_path.exists():
        return AnthropicRunTokenResult(run_path=run_dir, status="missing_result")

    result = read_json(result_path)
    run = result.get("run") if isinstance(result.get("run"), dict) else {}
    if not run.get("has_primary_request"):
        return AnthropicRunTokenResult(run_path=run_dir, status="no_primary_request")

    existing = int(run.get("anthropic_total_body_tokens") or 0)
    if existing > 0 and not force:
        return AnthropicRunTokenResult(
            run_path=run_dir,
            status="existing",
            model=str(run.get("anthropic_tokenizer_model") or ""),
            total_tokens=existing,
        )

    record = primary_request_record(run_dir, result)
    body_text = captured_body_text(record)
    tokens = anthropic_count_tokens(
        api_key=api_key,
        base_url=base_url,
        model=model,
        body_text=body_text,
        limiter=limiter or RateLimiter(DEFAULT_RPM),
    )
    run["anthropic_tokenizer_model"] = model
    run["anthropic_total_body_tokens"] = tokens
    write_benchmark_result(run_dir, result)
    _sync_summary(run_dir, run)
    return AnthropicRunTokenResult(
        run_path=run_dir,
        status="counted",
        model=model,
        total_tokens=tokens,
        updated=True,
    )


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name, "")
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc


def _env_disabled(value: str) -> bool:
    return value.strip().lower() in {"0", "false", "no", "off", "disabled"}


def anthropic_tokenizer_settings_from_env(
    *, api_key_env: str = DEFAULT_API_KEY_ENV
) -> dict[str, Any]:
    dotenv = load_dotenv_file()
    disabled = _env_disabled(os.environ.get(ENV_ENABLED, ""))
    api_key_present = bool(os.environ.get(api_key_env, ""))
    disabled_reason = ""
    if disabled:
        disabled_reason = f"{ENV_ENABLED} disabled automatic counting"
    elif not api_key_present:
        disabled_reason = f"{api_key_env} is not set"
    return {
        "enabled": api_key_present and not disabled,
        "api_key_env": api_key_env,
        "api_key_present": api_key_present,
        "base_url": os.environ.get(ENV_BASE_URL, DEFAULT_BASE_URL),
        "model": os.environ.get(ENV_MODEL, DEFAULT_MODEL),
        "rpm": _float_env(ENV_RPM, DEFAULT_RPM),
        "dotenv_path": str(dotenv) if dotenv is not None else "",
        "disabled_reason": disabled_reason,
    }


def anthropic_token_counter_from_env(
    *, api_key_env: str = DEFAULT_API_KEY_ENV
) -> AnthropicTokenCounter | None:
    settings = anthropic_tokenizer_settings_from_env(api_key_env=api_key_env)
    if not settings["enabled"]:
        return None
    return AnthropicTokenCounter(
        api_key=os.environ[api_key_env],
        base_url=str(settings["base_url"]),
        model=str(settings["model"]),
        rpm=float(settings["rpm"]),
    )