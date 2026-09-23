#!/bin/bash
# Submit-host demo: MPI abort fault + agent analysis. Run on mn.
# Expect: reason_code=mpi_abort, pid_count>0, assist/analysis.json.
set -u
SHARED="${AGENT_SHARED:-/shared}"
ROOT="${1:-$SHARED/agent-sidecar}"
OUT="${2:-$SHARED/agent-runs}"
WORK_S="${AGENT_MPI_ABORT_WORK_S:-10}"
ABORT_RANK="${AGENT_MPI_ABORT_RANK:-0}"
MPI_SRC="${AGENT_MPI_MONITOR_SRC:-$SHARED/mpi-monitor/src}"

export PYTHONPATH="${ROOT}/src:${MPI_SRC}${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUNBUFFERED=1
export AGENT_VERBOSE=1
# Deterministic pack must still write analysis.json without post-job OpenCode.
export AGENT_OPENCODE_FINAL_TIMEOUT="${AGENT_OPENCODE_FINAL_TIMEOUT:-0}"
mkdir -p "$OUT"

echo "======== 0. mpi abort fixture ========"
echo "host=$(hostname -s) root=$ROOT out=$OUT work_s=$WORK_S abort_rank=$ABORT_RANK"
MPICC="${MPICC:-}"
if [[ -z "$MPICC" ]]; then
  if command -v mpicc >/dev/null 2>&1; then
    MPICC=mpicc
  elif command -v mpicc.openmpi >/dev/null 2>&1; then
    MPICC=mpicc.openmpi
  fi
fi
if [[ -z "$MPICC" ]]; then
  echo "mpicc not found" >&2
  exit 1
fi
BIN="$ROOT/examples/06x/mpi_fault_abort"
make -C "$ROOT/examples/06x" CC="$MPICC"
test -x "$BIN"
echo "compiled $BIN with $MPICC"
echo

salloc -N3 -n3 -w cn1,cn2,cn3 -p test bash -lc "
set -u
export PYTHONPATH='$PYTHONPATH'
export PYTHONUNBUFFERED=1
export AGENT_VERBOSE=1
export AGENT_OPENCODE_FINAL_TIMEOUT='$AGENT_OPENCODE_FINAL_TIMEOUT'
echo \"======== 1. sidecar.sh srun mpi_fault_abort ========\"
bash '$ROOT/scripts/sidecar.sh' --agent-verbose \\
  --agent-skills=proc-monitor,slurm-tap,mpi-scan,node-diag \\
  --agent-output-dir '$OUT' \\
  srun -n3 -l \\
  $BIN $WORK_S $ABORT_RANK 1 || true
"

echo
echo "======== 2. latest run dir ========"
RUN=$(ls -1dt "$OUT"/* 2>/dev/null | head -1 || true)
echo "RUN=$RUN"
if [[ -n "${RUN}" ]]; then
  python3 -m agent_sidecar report --run-dir "$RUN" || true
  echo "---- assist/ ----"
  ls -l "$RUN/assist" 2>/dev/null || true
  echo "---- analysis.json ----"
  cat "$RUN/assist/analysis.json" 2>/dev/null || echo "(no analysis.json)"
  echo "---- job.json (phase-1: ask for --code, no file:line) ----"
  cat "$RUN/assist/job.json" 2>/dev/null || echo "(no job.json)"
  echo "---- phase-1 offline analy (no --code, --no-llm) ----"
  bash "$ROOT/scripts/sidecar-analy.sh" --log "$RUN" --no-llm || true
  echo "---- phase-2 optional: authorized source, LLM default (uncomment to run) ----"
  echo "# bash $ROOT/scripts/sidecar-analy.sh --log \"$RUN\" --code $ROOT/examples"
  echo "---- files ----"
  find "$RUN" -type f | sort
fi
echo "======== done (expect reason_code=mpi_abort, pid_count>0, needs_source=true) ========"
