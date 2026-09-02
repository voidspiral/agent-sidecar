"""LLM endpoint config: env + flags; API key env-only."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import unittest

from agent_sidecar.argv import AgentParseError, parse_agent_argv
from agent_sidecar.llm import LlmConfig, load_llm_config


class TestLlmConfig(unittest.TestCase):
    def test_loads_from_env(self) -> None:
        env = {
            "AGENT_LLM_BASE_URL": "https://api.example.com/v1",
            "AGENT_LLM_API_KEY": "secret-test",
            "AGENT_LLM_MODEL": "example-model",
        }
        cfg = load_llm_config(parse_agent_argv(["srun", "-n", "1", "true"]).options, env)
        self.assertEqual(cfg.base_url, "https://api.example.com/v1")
        self.assertEqual(cfg.api_key, "secret-test")
        self.assertEqual(cfg.model, "example-model")

    def test_flags_override_base_url_and_model(self) -> None:
        parsed = parse_agent_argv(
            [
                "srun",
                "--agent-llm-base-url",
                "https://override.example/v1",
                "--agent-llm-model",
                "flag-model",
                "-n",
                "1",
                "true",
            ]
        )
        cfg = load_llm_config(
            parsed.options,
            {
                "AGENT_LLM_BASE_URL": "https://api.example.com/v1",
                "AGENT_LLM_API_KEY": "secret-test",
                "AGENT_LLM_MODEL": "env-model",
            },
        )
        self.assertEqual(cfg.base_url, "https://override.example/v1")
        self.assertEqual(cfg.model, "flag-model")
        self.assertEqual(cfg.api_key, "secret-test")
        self.assertNotIn("--agent-llm-base-url", parsed.passthrough)
        self.assertNotIn("--agent-llm-model", parsed.passthrough)

    def test_no_api_key_flag(self) -> None:
        with self.assertRaises(AgentParseError):
            parse_agent_argv(
                ["srun", "--agent-llm-api-key", "nope", "-n", "1", "true"]
            )

    def test_missing_key_is_unconfigured(self) -> None:
        cfg = load_llm_config(
            parse_agent_argv(["srun", "-n", "1", "true"]).options,
            {"AGENT_LLM_BASE_URL": "https://api.example.com/v1", "AGENT_LLM_MODEL": "m"},
        )
        self.assertFalse(cfg.configured)
