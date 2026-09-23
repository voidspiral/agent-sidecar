#!/usr/bin/env python3
"""Assert telemetry.json reason_code (and optional pid_count / pack)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load_json(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit(f"missing {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"{path} is not a JSON object")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, help="sidecar run directory")
    parser.add_argument("--reason", required=True, help="expected reason_code")
    parser.add_argument("--pid-min", type=int, default=None, help="minimum summary.pid_count")
    parser.add_argument("--pack", default=None, help="expected assist/analysis.json pack")
    args = parser.parse_args(argv)

    run_dir = Path(args.run_dir)
    tel = _load_json(run_dir / "telemetry.json")
    got = str(tel.get("reason_code") or "")
    if got != args.reason:
        print(f"reason_code={got!r} expected {args.reason!r}", file=sys.stderr)
        return 1
    summary = tel.get("summary") if isinstance(tel.get("summary"), dict) else {}
    if args.pid_min is not None:
        pid_count = int(summary.get("pid_count") or 0)
        if pid_count < args.pid_min:
            print(
                f"pid_count={pid_count} expected >= {args.pid_min}",
                file=sys.stderr,
            )
            return 1
    if args.pack:
        analysis = _load_json(run_dir / "assist" / "analysis.json")
        pack = str(analysis.get("pack") or "")
        if pack != args.pack:
            print(f"pack={pack!r} expected {args.pack!r}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
