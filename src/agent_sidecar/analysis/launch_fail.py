"""launch_fail pack skeleton."""

from __future__ import annotations

from typing import Any


def build_launch_fail_analysis(
    *,
    reason_code: str,
    summary: dict[str, Any],
) -> dict[str, Any]:
    return {
        "pack": "launch_fail",
        "reason_code": reason_code,
        "pid_count": summary.get("pid_count"),
        "exit_code": summary.get("exit_code"),
        "suggestions": [
            "二进制可能缺失或不在计算节点可见的共享路径上",
            "编译到 /shared/... 后用绝对路径启动",
        ],
        "code_hits": [],
    }


def chinese_summary(analysis: dict[str, Any]) -> str:
    return (
        "1. 结论：作业未启动（execution_error 且 pid_count=0），不是 MPI abort\n"
        "2. 采集：host_count/pid_count 均为 0 或未采样到用户进程\n"
        "3. 异常：可执行文件可能 ENOENT / 不在 NFS\n"
        "4. 建议：mpicc 编译到共享路径后执行，例如 "
        "`python3 -m agent_sidecar srun --agent-output-dir /shared/agent-runs "
        "-n3 -- /shared/agent-sidecar/examples/mpi_io_load 60 /shared/mpi-io`"
    )
