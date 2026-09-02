"""Fake OpenAI-compatible chat client; no network."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import json
import unittest

from agent_sidecar.llm import LlmConfig, LlmError, chat_complete


def _ok_body(text: str) -> bytes:
    return json.dumps(
        {"choices": [{"message": {"content": text}}]}
    ).encode("utf-8")


class TestLlmClient(unittest.TestCase):
    def test_prompt_is_telemetry_contract_not_jsonl(self) -> None:
        captured: dict[str, object] = {}

        def transport(url: str, headers: dict[str, str], body: bytes, timeout: float):
            captured["url"] = url
            captured["body"] = json.loads(body.decode("utf-8"))
            captured["timeout"] = timeout
            return 200, _ok_body("idle ranks with IO")

        series_line = (
            '{"ts":1,"host":"h1","pid":9,"cpu_pct":1.0,"rss_mb":2.0,'
            '"io_read_bps":3.0,"io_write_bps":4.0}'
        )
        telemetry = {
            "summary": {"cpu_avg": 1.0, "pid_count": 1, "io_write_bps_sum": 4.0},
            "anomalies": [{"reason_code": "cpu_idle"}],
            "reason_code": "cpu_idle",
            "evidence_paths": ["series/h1_pid9.jsonl"],
        }
        cfg = LlmConfig(
            base_url="https://api.example.com/v1",
            api_key="k",
            model="deepseek-v4-flash",
            timeout=5.0,
        )
        text, payload = chat_complete(cfg, telemetry, transport=transport)
        self.assertEqual(text, "idle ranks with IO")
        self.assertIn("/chat/completions", str(captured["url"]))
        user = payload["messages"][1]["content"]
        self.assertIn("cpu_idle", user)
        self.assertIn("cpu_avg", user)
        self.assertNotIn(series_line, user)
        self.assertNotIn('"ts": 1', user)
        self.assertNotIn('"pid": 9', user)
        self.assertEqual(payload["model"], "deepseek-v4-flash")
        self.assertEqual(payload["temperature"], 0)

    def test_http_error_code(self) -> None:
        cfg = LlmConfig(base_url="https://api.example.com/v1", api_key="k", model="m")

        def transport(_url, _headers, _body, _timeout):
            return 500, b"nope"

        with self.assertRaises(LlmError) as ctx:
            chat_complete(cfg, {"reason_code": "ok"}, transport=transport)
        self.assertEqual(ctx.exception.code, "llm_http")
