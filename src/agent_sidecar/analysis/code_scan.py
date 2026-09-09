"""Optional read-only source scan for --code."""

from __future__ import annotations

from pathlib import Path
from typing import Any

MAX_FILES = 50
MAX_BYTES = 2 * 1024 * 1024
TEXT_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".f", ".f90", ".py", ".cu"}


def scan_code_root(
    code_root: Path,
    *,
    needles: tuple[str, ...] = ("MPI_Abort",),
) -> list[dict[str, Any]]:
    root = Path(code_root)
    if not root.is_dir():
        return []
    hits: list[dict[str, Any]] = []
    total = 0
    files = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.suffix != "":
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        total += len(data)
        if total > MAX_BYTES or files >= MAX_FILES:
            break
        files += 1
        try:
            text = data.decode("utf-8", errors="replace")
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            if any(n in line for n in needles):
                hits.append(
                    {
                        "path": str(path),
                        "lineno": i,
                        "line": line[:240],
                    }
                )
                if len(hits) >= 20:
                    return hits
    return hits
