"""Local node diagnostics (OOM / cgroup / fs hang). Independent of other control planes."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from agent_sidecar.spi import Event, JobContext

OOM_RE = re.compile(r"Killed process (\d+)|Out of memory", re.IGNORECASE)
OOM_PID_RE = re.compile(
    r"Killed process (\d+)|oom-kill:[^\n]*\bpid=(\d+)",
    re.IGNORECASE,
)
OOM_KILL_LINE_RE = re.compile(r"(?m)^oom_kill(?:_count)?\s+(\d+)\s*$")
KMSG_PREFIX_RE = re.compile(r"^\d+,\d+,\d+,[^;]*;(.*)$")
FS_HANG_RE = re.compile(
    r"blocked for more than|hung task|nfs:\s+server\s+\S+\s+not responding|not responding, still trying",
    re.IGNORECASE,
)
CGROUP_REL_RE = re.compile(r"^(?:\d+):[^:]*:(.*)$")

CollectFn = Callable[[JobContext], "NodeSnapshot"]


@dataclass
class NodeSnapshot:
    dmesg_text: str = ""
    cgroup_procs: str = ""
    oom_kill: int | None = None
    fs_hang_lines: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    cgroup_path: str | None = None


def parse_oom_trace(text: str) -> list[int]:
    pids: list[int] = []
    seen: set[int] = set()
    for m in OOM_PID_RE.finditer(text or ""):
        raw = m.group(1) or m.group(2)
        if not raw:
            continue
        pid = int(raw)
        if pid not in seen:
            seen.add(pid)
            pids.append(pid)
    return pids


def parse_cgroup_procs(text: str) -> list[int]:
    pids: list[int] = []
    for line in (text or "").splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))
    return pids


def parse_oom_kill(text: str) -> int | None:
    found: int | None = None
    for m in OOM_KILL_LINE_RE.finditer(text or ""):
        found = int(m.group(1))
    return found


def parse_kmsg(text: str) -> str:
    lines: list[str] = []
    for line in (text or "").splitlines():
        m = KMSG_PREFIX_RE.match(line)
        lines.append(m.group(1) if m else line)
    return "\n".join(lines)


def parse_fs_hang(text: str) -> list[str]:
    return [ln for ln in (text or "").splitlines() if FS_HANG_RE.search(ln)]


def parse_proc_cgroup(text: str) -> list[str]:
    out: list[str] = []
    for line in (text or "").splitlines():
        m = CGROUP_REL_RE.match(line.strip())
        if m and m.group(1):
            out.append(m.group(1))
    return out


def _is_cgroup_dir(path: Path) -> bool:
    return (
        (path / "cgroup.procs").is_file()
        or (path / "memory.events").is_file()
        or (path / "memory.oom_control").is_file()
    )


def _resolve_cgroup(rel: str, sys_root: Path) -> Path | None:
    rel = rel.lstrip("/")
    for candidate in (sys_root / rel, sys_root / "memory" / rel):
        if candidate.is_dir() and _is_cgroup_dir(candidate):
            return candidate
        if candidate.is_dir():
            return candidate
    return None


def _prefer_job_dir(start: Path | None, job_id: str) -> Path | None:
    if start is None:
        return None
    needles = {f"job_{job_id}", f"job-{job_id}"}
    cur = start
    best = start if _is_cgroup_dir(start) else None
    while True:
        if cur.name in needles and (cur.is_dir()):
            return cur
        if best is None and _is_cgroup_dir(cur):
            best = cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return best


def find_job_cgroup(
    job_id: str,
    *,
    proc_cgroup: str,
    sys_root: Path,
    uid: int | None = None,
) -> Path | None:
    jid = str(job_id)
    for rel in parse_proc_cgroup(proc_cgroup):
        found = _prefer_job_dir(_resolve_cgroup(rel, sys_root), jid)
        if found is not None:
            return found
    if uid is not None:
        for cand in (
            sys_root / "memory" / "slurm" / f"uid_{uid}" / f"job_{jid}",
            sys_root / "slurm" / f"uid_{uid}" / f"job_{jid}",
            sys_root / "system.slice" / "slurmstepd.scope" / f"job_{jid}",
        ):
            if cand.is_dir():
                return cand
    for slurm in (sys_root / "memory" / "slurm", sys_root / "slurm"):
        if not slurm.is_dir():
            continue
        try:
            uid_dirs = list(slurm.glob("uid_*"))
        except OSError:
            uid_dirs = []
        for uid_dir in uid_dirs:
            cand = uid_dir / f"job_{jid}"
            if cand.is_dir():
                return cand
    return None


def _run_cmd(argv: list[str], timeout: float = 3.0) -> str:
    if shutil.which(argv[0]) is None:
        return ""
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return proc.stdout or ""


def _read_text(path: Path, max_bytes: int = 256_000) -> str:
    try:
        with path.open("rb") as fh:
            data = fh.read(max_bytes)
    except OSError:
        return ""
    return data.decode("utf-8", errors="replace")


def _read_kmsg(path: Path, max_bytes: int = 256_000) -> str:
    if not path.exists():
        return ""
    if path.is_file() and path.name != "kmsg":
        return parse_kmsg(_read_text(path, max_bytes))
    try:
        fd = os.open(str(path), os.O_RDONLY | os.O_NONBLOCK)
    except OSError:
        return parse_kmsg(_read_text(path, max_bytes))
    chunks: list[bytes] = []
    total = 0
    try:
        while total < max_bytes:
            try:
                buf = os.read(fd, 4096)
            except BlockingIOError:
                break
            if not buf:
                break
            chunks.append(buf)
            total += len(buf)
    except OSError:
        pass
    finally:
        os.close(fd)
    return parse_kmsg(b"".join(chunks).decode("utf-8", errors="replace"))


def default_node_collect(
    ctx: JobContext,
    *,
    dmesg_runner: Callable[[list[str]], str] | None = None,
    kmsg_path: Path = Path("/dev/kmsg"),
    proc_cgroup_path: Path = Path("/proc/self/cgroup"),
    sys_cgroup_root: Path = Path("/sys/fs/cgroup"),
    uid: int | None = None,
) -> NodeSnapshot:
    runner = dmesg_runner or (lambda argv: _run_cmd(argv))
    dmesg = runner(["dmesg", "--time-format=iso"]) or runner(["dmesg"])
    if not dmesg:
        dmesg = _read_kmsg(kmsg_path)
    else:
        dmesg = dmesg[-256_000:]
    hang = tuple(parse_fs_hang(dmesg))
    proc_text = _read_text(proc_cgroup_path)
    if uid is None:
        try:
            uid = os.getuid()
        except OSError:
            uid = None
    job_dir = find_job_cgroup(
        ctx.job_id,
        proc_cgroup=proc_text,
        sys_root=sys_cgroup_root,
        uid=uid,
    )
    cgroup_procs = ""
    oom_kill = None
    cgroup_path = None
    if job_dir is not None:
        cgroup_path = str(job_dir)
        cgroup_procs = _read_text(job_dir / "cgroup.procs")
        oom_text = _read_text(job_dir / "memory.events")
        if not oom_text:
            oom_text = _read_text(job_dir / "memory.oom_control")
        oom_kill = parse_oom_kill(oom_text)
    return NodeSnapshot(
        dmesg_text=dmesg,
        cgroup_procs=cgroup_procs,
        oom_kill=oom_kill,
        fs_hang_lines=hang,
        cgroup_path=cgroup_path,
    )


def _relevant_oom_pids(oom_pids: list[int], cgroup_pids: list[int], *, injected: bool) -> list[int]:
    if injected:
        return list(oom_pids)
    if not cgroup_pids:
        return []
    allow = set(cgroup_pids)
    return [pid for pid in oom_pids if pid in allow]


def _format_snapshot(
    snap: NodeSnapshot,
    *,
    oom_pids: list[int],
    cgroup_pids: list[int],
) -> str:
    hang = snap.fs_hang_lines or tuple(parse_fs_hang(snap.dmesg_text))
    oom_kill = snap.oom_kill if snap.oom_kill is not None else 0
    lines = [
        f"oom_pids={oom_pids}",
        f"cgroup_pids={cgroup_pids}",
        f"oom_kill={oom_kill}",
        f"fs_hang_lines={len(hang)}",
    ]
    if snap.cgroup_path:
        lines.append(f"cgroup={snap.cgroup_path}")
    excerpt = []
    for pid in oom_pids:
        excerpt.append(f"Killed process {pid}")
    excerpt.extend(hang[:8])
    if excerpt:
        lines.append("excerpt:")
        lines.extend(excerpt)
    return "\n".join(lines) + "\n"


class NodeDiag:
    name = "node-diag"

    def __init__(
        self,
        dmesg_text: str | None = None,
        cgroup_procs: str | None = None,
        collect: CollectFn | None = None,
    ) -> None:
        self._dmesg = dmesg_text
        self._cgroup = cgroup_procs
        self._collect = collect or default_node_collect
        self._injected = dmesg_text is not None or cgroup_procs is not None
        self._events: list[Event] = []
        self._artifacts: list[Path] = []
        self._ctx: JobContext | None = None
        self._baseline_oom_kill: int | None = None

    def start(self, ctx: JobContext) -> None:
        self._ctx = ctx
        self._baseline_oom_kill = None
        self._apply(ctx, self._snapshot(ctx), baseline=True)

    def _snapshot(self, ctx: JobContext) -> NodeSnapshot:
        if self._injected:
            return NodeSnapshot(
                dmesg_text=self._dmesg or "",
                cgroup_procs=self._cgroup or "",
                fs_hang_lines=tuple(parse_fs_hang(self._dmesg or "")),
            )
        try:
            return self._collect(ctx)
        except Exception as exc:
            return NodeSnapshot(errors=(str(exc),))

    def _apply(self, ctx: JobContext, snap: NodeSnapshot, *, baseline: bool) -> None:
        events_dir = ctx.output_dir / "events"
        events_dir.mkdir(parents=True, exist_ok=True)
        if snap.errors and not self._injected:
            err = events_dir / "node_diag.err"
            err.write_text("\n".join(snap.errors) + "\n", encoding="utf-8")
        oom_raw = parse_oom_trace(snap.dmesg_text)
        cgroup_pids = parse_cgroup_procs(snap.cgroup_procs)
        oom_pids = _relevant_oom_pids(oom_raw, cgroup_pids, injected=self._injected)
        hang = snap.fs_hang_lines or tuple(parse_fs_hang(snap.dmesg_text))
        if baseline and not self._injected:
            self._baseline_oom_kill = snap.oom_kill if snap.oom_kill is not None else 0
        text = _format_snapshot(snap, oom_pids=oom_pids, cgroup_pids=cgroup_pids)
        dest = events_dir / "node-diag.txt"
        dest.write_text(text, encoding="utf-8")
        self._artifacts = [dest]
        emit = False
        if self._injected:
            emit = bool(oom_pids) or bool(OOM_RE.search(snap.dmesg_text)) or bool(hang)
        else:
            oom_kill = snap.oom_kill if snap.oom_kill is not None else 0
            grew = (
                self._baseline_oom_kill is not None
                and oom_kill > self._baseline_oom_kill
            )
            dmesg_lines = [ln for ln in snap.dmesg_text.splitlines() if ln.strip()]
            hang_only = bool(hang) and bool(dmesg_lines) and all(
                FS_HANG_RE.search(ln) for ln in dmesg_lines
            )
            emit = bool(oom_pids) or grew or hang_only
        if emit:
            self._events = [
                Event(
                    reason_code="node_local",
                    message=f"oom pids={oom_pids}",
                    evidence_path=str(dest),
                    host=ctx.host,
                )
            ]
        else:
            self._events = []

    def events(self) -> list[Event]:
        return list(self._events)

    def stop(self) -> None:
        if self._ctx is None or self._injected:
            return
        self._apply(self._ctx, self._snapshot(self._ctx), baseline=False)

    def artifacts(self) -> list[Path]:
        return list(self._artifacts)
