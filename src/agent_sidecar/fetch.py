"""Copy node-local artifacts to the launch run directory."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

CopyFn = Callable[[Path, Path], None]


class FetchTimeout(Exception):
    pass


def fetch_host_artifacts(
    host: str,
    remote_dir: Path,
    local_run_dir: Path,
    *,
    copy: CopyFn | None = None,
    timeout: float = 5.0,
    timed_out: bool = False,
) -> dict[str, str]:
    """Copy remote_dir into local_run_dir. Bounded; per-host errors recorded.

    `timed_out` is a test hook; production callers pass a copy() that enforces
    timeout itself.
    """
    errors: dict[str, str] = {}
    dest = local_run_dir
    dest.mkdir(parents=True, exist_ok=True)
    if timed_out:
        errors[host] = f"fetch timeout after {timeout}s"
        return errors
    if copy is not None:
        try:
            copy(remote_dir, dest)
        except Exception as exc:  # noqa: BLE001 — record and continue
            errors[host] = str(exc)
        return errors
    if not remote_dir.is_dir():
        errors[host] = f"missing remote dir {remote_dir}"
        return errors
    for path in remote_dir.rglob("*"):
        if path.is_file():
            rel = path.relative_to(remote_dir)
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
    return errors
