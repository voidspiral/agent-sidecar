# Partial process metrics in the sidecar

## Context

mpi-monitor now writes a process sample when any one of CPU, RSS, read IO, or write IO is non-zero. A missing `/proc/<pid>/io` leaves `io_read_bps` and `io_write_bps` as JSON `null` and adds `unavailable: ["io"]`. Permission failure uses `io_permission`. This sidecar used to coerce a missing rate to `0`, which draws a flat IO line and reads as “no IO”.

## Goals

- Treat JSON `null` as absent, not zero, in the summary, live overlay, PNG writer, quiet report, and Chinese job note.
- When `unavailable` contains `io`, say the kernel did not provide `/proc/<pid>/io` (`CONFIG_TASK_IO_ACCOUNTING` is off). `io_permission` is a separate sentence.
- Skip a PNG for a metric that has no numeric points.
- `sample_valid` matches the collector: identity fields plus at least one non-zero metric.

## Non-Goals

- Reading `/proc` inside this repository.
- Substituting cgroup or Lustre counters for `io_*_bps`.
- Changing `reason_code`, eth-monitor, or the job-assist standing instruction files.
