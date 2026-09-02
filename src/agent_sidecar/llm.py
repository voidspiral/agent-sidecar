"""OpenAI-compatible chat client for submit-host job-assist."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from agent_sidecar.argv import AgentOptions

DEFAULT_TIMEOUT = 30.0
CHAT_PATH = "/chat/completions"

Transport = Callable[[str, dict[str, str], bytes, float], tuple[int, bytes]]


class LlmError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message or code


@dataclass
class LlmConfig:
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    timeout: float = DEFAULT_TIMEOUT

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)


def load_llm_config(options: AgentOptions, env: dict[str, str]) -> LlmConfig:
    timeout_raw = env.get("AGENT_LLM_TIMEOUT") or ""
    try:
        timeout = float(timeout_raw) if timeout_raw else DEFAULT_TIMEOUT
    except ValueError:
        timeout = DEFAULT_TIMEOUT
    return LlmConfig(
        base_url=(options.llm_base_url or env.get("AGENT_LLM_BASE_URL") or "").rstrip("/"),
        api_key=env.get("AGENT_LLM_API_KEY") or "",
        model=options.llm_model or env.get("AGENT_LLM_MODEL") or "",
        timeout=timeout,
    )


def build_chat_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return base + CHAT_PATH


def build_prompt(telemetry: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary": telemetry.get("summary") or {},
        "anomalies": telemetry.get("anomalies") or [],
        "reason_code": telemetry.get("reason_code"),
        "evidence_paths": telemetry.get("evidence_paths") or [],
    }


def parse_chat_content(body: bytes) -> str:
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LlmError("llm_parse", str(exc)) from exc
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmError("llm_parse", "missing choices[0].message.content") from exc
    if not isinstance(content, str) or not content.strip():
        raise LlmError("llm_parse", "empty model content")
    return content


def _default_transport(
    url: str, headers: dict[str, str], body: bytes, timeout: float
) -> tuple[int, bytes]:
    req = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=timeout) as resp:
            return int(getattr(resp, "status", 200)), resp.read()
    except HTTPError as exc:
        return int(exc.code), exc.read() if exc.fp else b""
    except TimeoutError as exc:
        raise LlmError("llm_timeout", str(exc)) from exc
    except URLError as exc:
        reason = str(exc.reason) if exc.reason else str(exc)
        if "timed out" in reason.lower():
            raise LlmError("llm_timeout", reason) from exc
        raise LlmError("llm_http", reason) from exc


def chat_complete(
    cfg: LlmConfig,
    telemetry: dict[str, Any],
    *,
    transport: Transport | None = None,
) -> tuple[str, dict[str, Any]]:
    """Return (model text, request payload). Does not hit the network when transport is injected."""
    if not cfg.configured:
        raise LlmError("llm_unconfigured", "AGENT_LLM_API_KEY or endpoint missing")
    payload = {
        "model": cfg.model,
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Interpret this HPC job telemetry. Do not change reason_code. "
                    "Do not suggest scancel or scontrol."
                ),
            },
            {"role": "user", "content": json.dumps(build_prompt(telemetry), sort_keys=True)},
        ],
    }
    body = json.dumps(payload).encode("utf-8")
    url = build_chat_url(cfg.base_url)
    headers = {
        "Authorization": f"Bearer {cfg.api_key}",
        "Content-Type": "application/json",
    }
    send = transport or _default_transport
    status, raw = send(url, headers, body, cfg.timeout)
    if status < 200 or status >= 300:
        raise LlmError("llm_http", f"HTTP {status}")
    return parse_chat_content(raw), payload
