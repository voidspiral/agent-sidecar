#!/bin/bash
# Run one 调研2 case-library fixture under sidecar.sh srun, then assert telemetry.
# Usage: run_fault_case.sh <id>
# Exit 2 when srun is missing or the case is not a cluster demo (skip). Do not fake pass.
# Env: AGENT_SHARED, AGENT_BAD_PARTITION, AGENT_CASE_MEM, AGENT_CASE_TIME,
#      AGENT_OPENCODE_FINAL_TIMEOUT (default 0), AGENT_SALLOC_OPTS.
set -u

CASE="${1:-}"
if [[ -z "$CASE" ]]; then
  echo "usage: run_fault_case.sh <id>" >&2
  echo "ids: 01 02 03 04 05 06 06x 07a 10 11a 12 13 16" >&2
  exit 1
fi

SHARED="${AGENT_SHARED:-/shared}"
ROOT="${AGENT_ROOT:-$SHARED/agent-sidecar}"
OUT="${AGENT_RUNS:-$SHARED/agent-runs}"
MPI_SRC="${AGENT_MPI_MONITOR_SRC:-$SHARED/mpi-monitor/src}"
BAD_PARTITION="${AGENT_BAD_PARTITION:-__no_such_partition__}"
CASE_MEM="${AGENT_CASE_MEM:-16M}"
CASE_TIME="${AGENT_CASE_TIME:-00:00:10}"
SALLOC_OPTS="${AGENT_SALLOC_OPTS:--N2 -n2 -w cn[1-2] -p test}"

if ! command -v srun >/dev/null 2>&1; then
  echo "skip: srun not on PATH (no cluster)" >&2
  exit 2
fi

case "$CASE" in
  18|19|20|21|22|23)
    echo "skip: hardware case $CASE stays an empty Makefile target" >&2
    exit 2
    ;;
  07b|08|09|11b|14|15|17)
    echo "skip: case $CASE is not a cluster fault demo this round" >&2
    exit 2
    ;;
esac

export PYTHONPATH="${ROOT}/src:${MPI_SRC}${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUNBUFFERED=1
export AGENT_VERBOSE="${AGENT_VERBOSE:-1}"
export AGENT_OPENCODE_FINAL_TIMEOUT="${AGENT_OPENCODE_FINAL_TIMEOUT:-0}"
mkdir -p "$OUT"

MPICC="${MPICC:-}"
if [[ -z "$MPICC" ]]; then
  if command -v mpicc >/dev/null 2>&1; then
    MPICC=mpicc
  elif command -v mpicc.openmpi >/dev/null 2>&1; then
    MPICC=mpicc.openmpi
  fi
fi

need_mpicc() {
  if [[ -z "$MPICC" ]]; then
    echo "mpicc not found" >&2
    exit 1
  fi
}

SKIP_SALLOC=0
REASON=""
PACK=""
PID_MIN=""
SRUN_N=2
SRUN_EXTRA=()
USER_CMD=()

case "$CASE" in
  01)
    need_mpicc
    make -C "$ROOT/examples/01" CC="$MPICC"
    USER_CMD=("$ROOT/examples/01/mpi_missing_so")
    REASON=execution_error
    PACK=launch_fail
    SRUN_N=1
    ;;
  02)
    need_mpicc
    make -C "$ROOT/examples/02" CC="$MPICC"
    USER_CMD=("$ROOT/examples/02/cgroup_oom")
    SRUN_EXTRA=(--mem="$CASE_MEM")
    REASON=slurm_oom
    PACK=stub
    SRUN_N=1
    PID_MIN=1
    ;;
  03)
    need_mpicc
    make -C "$ROOT/examples/03" CC="$MPICC"
    USER_CMD=("$ROOT/examples/03/mpi_fault_segfault" "${AGENT_MPI_SEGFAULT_WORK_S:-5}" 0)
    REASON=mpi_segfault
    PACK=mpi_segfault
    PID_MIN=1
    ;;
  04)
    make -C "$ROOT/examples/04"
    chmod +x "$ROOT/examples/04/job.sh"
    USER_CMD=("$ROOT/examples/04/job.sh")
    REASON=execution_error
    SRUN_N=1
    ;;
  05)
    need_mpicc
    make -C "$ROOT/examples/05" CC="$MPICC"
    USER_CMD=("$ROOT/examples/05/mpi_fault_fpe" "${AGENT_MPI_FPE_WORK_S:-5}" 0)
    REASON=mpi_fpe
    PACK=stub
    PID_MIN=1
    ;;
  06)
    need_mpicc
    make -C "$ROOT/examples/06" CC="$MPICC"
    USER_CMD=("$ROOT/examples/06/mpi_fault_deadlock" "${AGENT_MPI_DEADLOCK_WORK_S:-5}" 0)
    SRUN_EXTRA=(--time="$CASE_TIME")
    REASON=mpi_deadlock
    PACK=stub
    PID_MIN=1
    ;;
  06x)
    need_mpicc
    make -C "$ROOT/examples/06x" CC="$MPICC"
    USER_CMD=("$ROOT/examples/06x/mpi_fault_abort" "${AGENT_MPI_ABORT_WORK_S:-5}" 0 1)
    REASON=mpi_abort
    PACK=mpi_abort
    PID_MIN=1
    ;;
  07a)
    need_mpicc
    make -C "$ROOT/examples/07a" CC="$MPICC"
    USER_CMD=("$ROOT/examples/07a/io_enoent")
    REASON=execution_error
    SRUN_N=1
    PID_MIN=1
    ;;
  10)
    USER_CMD=("$ROOT/examples/10/no-such-mpi")
    REASON=execution_error
    PACK=launch_fail
    SRUN_N=1
    ;;
  11a)
    USER_CMD=(hostname)
    SRUN_EXTRA=(-p "$BAD_PARTITION")
    REASON=execution_error
    SRUN_N=1
    SKIP_SALLOC=1
    ;;
  12)
    make -C "$ROOT/examples/12"
    USER_CMD=("$ROOT/examples/12/sleep_timeout.sh")
    SRUN_EXTRA=(--time="$CASE_TIME")
    REASON=timeout
    SRUN_N=1
    PID_MIN=1
    ;;
  13)
    need_mpicc
    make -C "$ROOT/examples/13" CC="$MPICC"
    USER_CMD=("$ROOT/examples/02/cgroup_oom")
    SRUN_EXTRA=(--mem="$CASE_MEM")
    REASON=slurm_oom
    PACK=stub
    SRUN_N=1
    PID_MIN=1
    ;;
  16)
    need_mpicc
    make -C "$ROOT/examples/16" CC="$MPICC"
    USER_CMD=("$ROOT/examples/01/mpi_missing_so")
    SRUN_EXTRA=(--export=NONE)
    REASON=execution_error
    PACK=launch_fail
    SRUN_N=1
    ;;
  *)
    echo "unknown case id: $CASE" >&2
    exit 1
    ;;
esac

echo "======== run_fault_case $CASE ========"
echo "host=$(hostname -s) root=$ROOT out=$OUT reason=$REASON"
srun_args=(-n "$SRUN_N" -l)
if [[ ${#SRUN_EXTRA[@]} -gt 0 ]]; then
  srun_args+=("${SRUN_EXTRA[@]}")
fi
srun_args+=(-- "${USER_CMD[@]}")
SRUN_TAIL=$(printf '%q ' "${srun_args[@]}")
run_sidecar() {
  echo "======== 1. sidecar.sh srun case $CASE ========"
  bash "$ROOT/scripts/sidecar.sh" --agent-verbose \
    --agent-skills=proc-monitor,slurm-tap,mpi-scan,node-diag \
    --agent-output-dir "$OUT" \
    srun $SRUN_TAIL || true
}
if [[ "${SKIP_SALLOC:-0}" == "1" ]]; then
  export PYTHONPATH PYTHONUNBUFFERED=1 AGENT_VERBOSE AGENT_OPENCODE_FINAL_TIMEOUT
  run_sidecar
else
  # shellcheck disable=SC2086
  salloc $SALLOC_OPTS bash -lc "
set -u
export PYTHONPATH='$PYTHONPATH'
export PYTHONUNBUFFERED=1
export AGENT_VERBOSE='$AGENT_VERBOSE'
export AGENT_OPENCODE_FINAL_TIMEOUT='$AGENT_OPENCODE_FINAL_TIMEOUT'
$(declare -f run_sidecar)
ROOT='$ROOT'
OUT='$OUT'
CASE='$CASE'
SRUN_TAIL='$SRUN_TAIL'
run_sidecar
"
fi

echo
echo "======== 2. latest run dir ========"
RUN=$(ls -1dt "$OUT"/20* 2>/dev/null | head -1 || true)
echo "RUN=$RUN"
if [[ -z "${RUN}" ]]; then
  echo "no run directory under $OUT" >&2
  exit 1
fi

ASSERT=(python3 "$ROOT/scripts/assert_telemetry.py" --run-dir "$RUN" --reason "$REASON")
if [[ -n "$PACK" ]]; then
  ASSERT+=(--pack "$PACK")
fi
if [[ -n "$PID_MIN" ]]; then
  ASSERT+=(--pid-min "$PID_MIN")
fi
if ! "${ASSERT[@]}"; then
  echo "assert failed case=$CASE run=$RUN" >&2
  exit 1
fi
echo "======== ok case=$CASE reason=$REASON run=$RUN ========"
