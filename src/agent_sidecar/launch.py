"""Plan SLURM sidecar injection without breaking the user PMI step."""

from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_SIDECAR_MEM = "256M"


class OverlapRejected(Exception):
    """Site rejected overlapping job steps."""


@dataclass
class LaunchPlan:
    mode: str
    sidecar_argv: list[str]
    user_argv: list[str]
    fallback_used: bool = False
    extra: dict[str, str] = field(default_factory=dict)


def _is_forbidden_user_step(user_argv: list[str]) -> bool:
    joined = " ".join(user_argv)
    return "bash -c" in joined and "& exec" in joined


def plan_overlap(
    passthrough: list[str],
    supervisor_argv: list[str],
    *,
    srun: str = "srun",
    mem: str = DEFAULT_SIDECAR_MEM,
) -> LaunchPlan:
    sidecar = [
        srun,
        "--overlap",
        "--ntasks-per-node=1",
        "--exact",
        f"--mem={mem}",
        *supervisor_argv,
    ]
    user = [srun, *passthrough]
    if _is_forbidden_user_step(user):
        raise ValueError("per-rank bash wrapper is forbidden")
    return LaunchPlan(mode="overlap", sidecar_argv=sidecar, user_argv=user)


def plan_exec_wrapper(
    passthrough: list[str],
    wrap_argv: list[str],
    *,
    srun: str = "srun",
) -> LaunchPlan:
    """User srun stays PMI; wrap_argv forks collector then execs the binary.

    wrap_argv is inserted immediately after `--` (or at the end) so it is the
    task binary, not a `bash -c` wrapper.
    """
    args = list(passthrough)
    if "--" in args:
        i = args.index("--")
        user = [srun, *args[: i + 1], *wrap_argv, *args[i + 1 :]]
    else:
        user = [srun, *wrap_argv, *args]
    if _is_forbidden_user_step(user):
        raise ValueError("per-rank bash wrapper is forbidden")
    return LaunchPlan(
        mode="exec-wrapper",
        sidecar_argv=[],
        user_argv=user,
        fallback_used=True,
    )


def execute_launch(
    plan: LaunchPlan,
    *,
    run_sidecar,
    run_user,
    overlap_ok: bool = True,
    passthrough: list[str] | None = None,
    wrap_argv: list[str] | None = None,
    srun: str = "srun",
) -> tuple[int, LaunchPlan]:
    """Run sidecar then user step. On overlap reject before user start, fallback once."""
    current = plan
    if current.mode == "overlap" and current.sidecar_argv:
        if not overlap_ok:
            if wrap_argv is None:
                raise OverlapRejected("overlap disabled")
            current = plan_exec_wrapper(passthrough or [], wrap_argv, srun=srun)
        else:
            sidecar_rc = run_sidecar(current.sidecar_argv)
            if sidecar_rc != 0:
                if wrap_argv is None:
                    raise OverlapRejected(f"overlap sidecar exited {sidecar_rc}")
                current = plan_exec_wrapper(passthrough or [], wrap_argv, srun=srun)
    code = run_user(current.user_argv)
    return code, current
