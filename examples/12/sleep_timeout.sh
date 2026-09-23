#!/bin/bash
# 12 — TimeLimit fixture. Demo MUST use --time=00:00:10 (or AGENT_CASE_TIME).
# Sleeps longer than the limit so SLURM reports TIMEOUT.
set -u
echo "sleep_timeout start" >&2
exec sleep "${SLEEP_TIMEOUT_SECS:-3600}"
