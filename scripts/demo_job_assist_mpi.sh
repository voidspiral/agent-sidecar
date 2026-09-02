#!/bin/bash
# Submit-host job-assist + ~60s MPI IO on NFS /shared. Run on mn.
set -u
SHARED="${AGENT_SHARED:-/shared}"
ROOT="${1:-$SHARED/agent-sidecar}"
OUT="${2:-$SHARED/agent-runs}"
WORK="${AGENT_MPI_WORKDIR:-$SHARED/mpi-io}"
SECONDS_IO="${AGENT_MPI_SECONDS:-60}"
MPI_SRC="${AGENT_MPI_MONITOR_SRC:-$SHARED/mpi-monitor/src}"

export PYTHONPATH="${ROOT}/src:${MPI_SRC}${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUNBUFFERED=1
export AGENT_VERBOSE=1
mkdir -p "$OUT" "$WORK"

echo "======== 0. launch host ========"
echo "host=$(hostname -s) user=$(whoami) date=$(date -Is)"
echo "shared=$SHARED root=$ROOT out=$OUT work=$WORK"
echo "profile=job-assist opencode=$(command -v opencode || echo missing)"
echo "opencode_model=${AGENT_OPENCODE_MODEL:-default}"
if ! command -v opencode >/dev/null 2>&1; then
  echo "opencode is not on PATH; install it on mn or stop. No HTTP fallback." >&2
  exit 2
fi
df -h "$SHARED"
command -v srun
command -v python3
python3 -c "import agent_sidecar; print('agent_sidecar', agent_sidecar.__version__)"
echo

echo "======== 1. build MPI IO load on NFS ========"
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
BIN="$ROOT/examples/mpi_io_load"
"$MPICC" -O2 -Wall -Wextra -o "$BIN" "$ROOT/examples/mpi_io_load.c"
test -x "$BIN"
echo "compiled $BIN with $MPICC"
echo

salloc -N3 -n3 -w cn1,cn2,cn3 -p test bash -lc "
set -u
export PYTHONPATH='$PYTHONPATH'
export PYTHONUNBUFFERED=1
export AGENT_VERBOSE=1
echo \"======== 2a. allocation ========\"
echo \"SLURM_JOB_ID=\$SLURM_JOB_ID\"
echo \"SLURM_NODELIST=\$SLURM_NODELIST\"
echo \"opencode_model=\${AGENT_OPENCODE_MODEL:-default}\"
echo
echo \"======== 2b. NFS visible on ranks ========\"
srun -N3 -n3 -l bash -c 'hostname -s; df -h $SHARED; ls -l $BIN; test -x $BIN'
echo
echo \"======== 2c. agent srun job-assist + mpi_io_load ${SECONDS_IO}s on $WORK ========\"
python3 -m agent_sidecar srun --agent-verbose --agent-profile=job-assist \\
  --agent-skills=proc-monitor,slurm-tap,mpi-scan,node-diag \\
  --agent-output-dir '$OUT' \\
  -n3 -l -- \\
  $BIN ${SECONDS_IO} $WORK
echo
echo \"======== 2d. salloc ending ========\"
"

echo
echo "======== 3. latest run dir ========"
RUN=$(ls -1dt "$OUT"/* 2>/dev/null | head -1 || true)
echo "RUN=$RUN"
if [[ -n "${RUN}" ]]; then
  echo "---- meta.json ----"
  cat "$RUN/meta.json"
  echo "---- telemetry.json ----"
  python3 -m agent_sidecar report --run-dir "$RUN"
  echo "---- assist/ ----"
  ls -l "$RUN/assist" 2>/dev/null || true
  if [[ -f "$RUN/assist/job.json" ]]; then
    echo "---- assist/job.json ----"
    cat "$RUN/assist/job.json"
  fi
  echo "---- series / charts ----"
  ls -l "$RUN/series" 2>/dev/null || true
  ls -l "$RUN/charts" 2>/dev/null || true
  echo "---- files ----"
  find "$RUN" -type f | sort
fi
echo "======== done ========"
