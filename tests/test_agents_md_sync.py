"""Cursor and OpenCode job-assist standing docs stay in lockstep."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ENGLISH_CANONICAL = ROOT / ".opencode" / "AGENTS.md"
ENGLISH_COPIES = (
    ROOT / ".opencode" / "agent" / "job-assist.md",
    ROOT / ".cursor" / "rules" / "job-assist.mdc",
)
CHINESE_CANONICAL = ROOT / ".opencode" / "AGENTS.zh.md"
CHINESE_COPIES = (ROOT / ".cursor" / "rules" / "job-assist.zh.md",)
ROOT_FORBIDDEN = (
    ROOT / "AGENTS.md",
    ROOT / "agent.md",
    ROOT / "AGENTS.zh.md",
    ROOT / "agent.zh.md",
    ROOT / "skills.md",
)


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    rest = text[3:]
    end = rest.find("\n---")
    if end < 0:
        return text
    body = rest[end + 4 :]
    return body.lstrip("\n")


class TestAgentsMdSync(unittest.TestCase):
    def test_english_bodies_match_opencode_agents_md(self) -> None:
        canonical = ENGLISH_CANONICAL.read_text(encoding="utf-8")
        self.assertTrue(ENGLISH_CANONICAL.is_file())
        for path in ENGLISH_COPIES:
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertTrue(path.is_file(), f"missing {path}")
                body = _strip_frontmatter(path.read_text(encoding="utf-8"))
                self.assertEqual(
                    body, canonical, f"{path} drifted from .opencode/AGENTS.md"
                )

    def test_chinese_bodies_match_opencode_agents_zh_md(self) -> None:
        canonical = CHINESE_CANONICAL.read_text(encoding="utf-8")
        self.assertTrue(CHINESE_CANONICAL.is_file())
        for path in CHINESE_COPIES:
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertTrue(path.is_file(), f"missing {path}")
                body = _strip_frontmatter(path.read_text(encoding="utf-8"))
                self.assertEqual(
                    body, canonical, f"{path} drifted from .opencode/AGENTS.zh.md"
                )

    def test_standing_text_requires_chinese_summary(self) -> None:
        en = ENGLISH_CANONICAL.read_text(encoding="utf-8")
        zh = CHINESE_CANONICAL.read_text(encoding="utf-8")
        self.assertIn("简体中文", en)
        self.assertIn("简体中文", zh)
        self.assertIn("分条", en)
        self.assertIn("分条", zh)
        self.assertIn("UTF-8", en)
        self.assertIn("UTF-8", zh)
        self.assertIn("\\uXXXX", en)
        self.assertIn("\\uXXXX", zh)

    def test_no_root_agents_md(self) -> None:
        for path in ROOT_FORBIDDEN:
            with self.subTest(path=path.name):
                self.assertFalse(
                    path.exists(),
                    f"{path.name} belongs under .opencode/ and .cursor/rules/, not repo root",
                )

    def test_no_chinese_agent_under_opencode_agent(self) -> None:
        agent_dir = ROOT / ".opencode" / "agent"
        zh = list(agent_dir.glob("*.zh.md")) if agent_dir.is_dir() else []
        self.assertEqual(zh, [], f"Chinese markdown must not live in {agent_dir}: {zh}")
