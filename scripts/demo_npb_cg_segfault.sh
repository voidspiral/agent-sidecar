#!/bin/bash
# Submit-host demo: NPB CG Class B (~60s, 2 ranks) with mid-iteration segfault.
# Compile and run on mn / shared disk. Do not use WSL as the cluster.
# Expect: reason_code=mpi_segfault after rank 0 crashes at iteration (niter+1)/2.
set -u
SHARED="${AGENT_SHARED:-/shared}"
ROOT="${1:-$SHARED/agent-sidecar}"
OUT="${2:-$SHARED/agent-runs}"
CLASS="${NPB_CG_CLASS:-B}"
MPI_SRC="${AGENT_MPI_MONITOR_SRC:-$SHARED/mpi-monitor/src}"
ETH_SRC="${AGENT_ETH_MONITOR_SRC:-$SHARED/eth-monitor/src}"

export PYTHONPATH="${ROOT}/src:${MPI_SRC}:${ETH_SRC}${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUNBUFFERED=1
export AGENT_VERBOSE=1
export AGENT_OPENCODE_FINAL_TIMEOUT="${AGENT_OPENCODE_FINAL_TIMEOUT:-0}"
mkdir -p "$OUT"

echo "======== 0. NPB CG mid-segfault fixture ========"
echo "host=$(hostname -s) root=$ROOT out=$OUT class=$CLASS NPB_MPI_ROOT=${NPB_MPI_ROOT:-}"
if [[ -z "${NPB_MPI_ROOT:-}" ]]; then
  echo "NPB_MPI_ROOT must point at the NPB 3.4-MPI directory." >&2
  exit 2
fi
export NPB_CG_CLASS="$CLASS"
export AGENT_SHARED="$SHARED"
bash "$ROOT/examples/npb_cg_mid_segfault/build.sh"
BIN="$ROOT/examples/cg.${CLASS}.x"
test -x "$BIN"
MATCH="$(basename "$BIN")"
echo "binary=$BIN match=$MATCH"
echo

salloc -N2 -n2 -w cn1,cn3 -p test bash -lc "
set -u
export PYTHONPATH='$PYTHONPATH'
export PYTHONUNBUFFERED=1
export AGENT_VERBOSE=1
export AGENT_OPENCODE_FINAL_TIMEOUT='$AGENT_OPENCODE_FINAL_TIMEOUT'
echo \"======== 1. sidecar.sh srun NPB CG Class $CLASS ========\"
bash '$ROOT/scripts/sidecar.sh' --agent-verbose \\
  --agent-skills=proc-monitor,slurm-tap,mpi-scan,node-diag,eth-monitor \\
  --agent-match='$MATCH' \\
  --agent-output-dir '$OUT' \\
  srun --mpi=pmi2 -N2 -n2 -l \\
  $BIN || true
"

echo
echo "======== 2. latest run dir ========"
RUN=$(ls -1dt "$OUT"/* 2>/dev/null | head -1 || true)
echo "RUN=$RUN"
if [[ -n "${RUN}" ]]; then
  python3 -m agent_sidecar report --run-dir "$RUN" || true
  echo "---- stderr.tail (expect rank 0 segfault) ----"
  cat "$RUN/events/stderr.tail" 2>/dev/null || echo "(no stderr.tail)"
  echo "---- telemetry reason_code ----"
  python3 -c "import json,sys; p=sys.argv[1];
print(json.load(open(p)).get('reason_code'))" "$RUN/telemetry.json" 2>/dev/null || true
fi
echo "======== done (expect reason_code=mpi_segfault, ~60s Class B CG) ========"
