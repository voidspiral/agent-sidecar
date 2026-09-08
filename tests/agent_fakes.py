"""Test doubles for wrap-time OpenCode (no real binary)."""

from __future__ import annotations


def noop_opencode(argv, cwd, timeout, env=None):
    return 0, "ok", ""


class NoPlot:
    def start(self, run_dir) -> str:
        return ""

    def stop(self) -> None:
        return None


class RecPlot:
    def __init__(self) -> None:
        self.order: list[str] = []
        self.run_dir = None
        self.url = "http://127.0.0.1:8765"

    def start(self, run_dir) -> str:
        self.order.append("start")
        self.run_dir = run_dir
        return self.url

    def stop(self) -> None:
        self.order.append("stop")


class FailPlot:
    def start(self, run_dir) -> str:
        raise OSError("Address already in use")

    def stop(self) -> None:
        return None


class NoWatch:
    def start(self, run_dir) -> None:
        return None

    def tick(self) -> None:
        return None

    def stop(self) -> None:
        return None


class RecWatch:
    def __init__(self) -> None:
        self.order: list[str] = []
        self.run_dir = None

    def start(self, run_dir) -> None:
        self.order.append("start")
        self.run_dir = run_dir

    def tick(self) -> str:
        self.order.append("tick")
        return "snapshot"

    def stop(self) -> None:
        self.order.append("stop")
