#!/bin/bash
# Job-assist OpenCode should diagnose a missing NFS binary and suggest a fix.
# Run on mn. No HTTP fallback.
set -u
SHARED="${AGENT_SHARED:-/shared}"
ROOT="${1:-$SHARED/agent-sidecar}"
OUT="${2:-$SHARED/agent-runs}"
MISSING="${AGENT_LAUNCH_FAIL_BIN:-$ROOT/examples/no-such-mpi}"
MPI_SRC="${AGENT_MPI_MONITOR_SRC:-$SHARED/mpi-monitor/src}"

export PYTHONPATH="${ROOT}/src:${MPI_SRC}${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUNBUFFERED=1
export AGENT_VERBOSE=1
mkdir -p "$OUT"

echo "======== 0. launch-fail fixture ========"
echo "host=$(hostname -s) missing=$MISSING"
if ! command -v opencode >/dev/null 2>&1; then
  echo "opencode is not on PATH; install it on mn or stop. No HTTP fallback." >&2
  exit 2
fi
if [[ -x "$MISSING" ]]; then
  echo "refusing to run: $MISSING exists (fixture must be missing)" >&2
  exit 2
fi

salloc -N3 -n3 -w cn1,cn2,cn3 -p test bash -lc "
set -u
export PYTHONPATH='$PYTHONPATH'
export PYTHONUNBUFFERED=1
export AGENT_VERBOSE=1
echo \"======== 1. agent srun missing binary ========\"
python3 -m agent_sidecar srun --agent-verbose --agent-profile=job-assist \\
  --agent-skills=proc-monitor,slurm-tap,mpi-scan,node-diag \\
  --agent-output-dir '$OUT' \\
  -n3 -l -- \\
  '$MISSING' || true
"

echo
echo "======== 2. latest run dir ========"
RUN=$(ls -1dt "$OUT"/* 2>/dev/null | head -1 || true)
echo "RUN=$RUN"
if [[ -n "${RUN}" ]]; then
  python3 -m agent_sidecar report --run-dir "$RUN" || true
  echo "---- assist/job.json ----"
  cat "$RUN/assist/job.json" 2>/dev/null || echo "(no note)"
  echo "---- files ----"
  find "$RUN" -type f | sort
fi
echo "======== done ========"
