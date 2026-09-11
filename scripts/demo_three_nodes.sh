#!/bin/bash
# Run on mn: three-node sidecar demo (cn1,cn2,cn3).
set -u
ROOT="${1:-/tmp/agent-sidecar}"
OUT="${2:-/tmp/agent-runs}"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUNBUFFERED=1
export AGENT_VERBOSE=1
mkdir -p "$OUT"

echo "======== 0. launch host ========"
echo "host=$(hostname -s) user=$(whoami) date=$(date -Is)"
echo "PYTHONPATH=$PYTHONPATH"
command -v srun
command -v python3
python3 -c "import agent_sidecar; print('agent_sidecar', agent_sidecar.__version__)"
echo
echo "======== 1. partition nodes ========"
sinfo -N -p test -l
echo
echo "======== 1b. copy tree from mn to cn1,cn2,cn3 ========"
for h in cn1 cn2 cn3; do
  echo "-- $h --"
  tar czf - -C "$ROOT" src | ssh -o BatchMode=yes -o ConnectTimeout=10 "$h" \
    'mkdir -p /tmp/agent-sidecar && tar xzf - -C /tmp/agent-sidecar && python3 -c "import sys; sys.path.insert(0,\"/tmp/agent-sidecar/src\"); import agent_sidecar; print(agent_sidecar.__version__, __import__(\"socket\").gethostname().split(\".\")[0])"'
done
echo

salloc -N3 -n3 -w cn1,cn2,cn3 -p test bash -lc "
set -u
export PYTHONPATH='$PYTHONPATH'
export PYTHONUNBUFFERED=1
export AGENT_VERBOSE=1
echo \"======== 2a. allocation ========\"
echo \"SLURM_JOB_ID=\$SLURM_JOB_ID\"
echo \"SLURM_NODELIST=\$SLURM_NODELIST\"
echo \"SLURM_JOB_NUM_NODES=\$SLURM_JOB_NUM_NODES\"
echo \"SLURM_NTASKS=\$SLURM_NTASKS\"
echo
echo \"======== 2b. nodes in this job ========\"
scontrol show hostnames \"\$SLURM_NODELIST\"
echo
echo \"======== 2c. stage source onto cn1,cn2,cn3 (no shared FS) ========\"
srun -N3 -n3 -l mkdir -p /tmp/agent-sidecar
tar czf /tmp/agent-sidecar-src.tgz -C '$ROOT' src
if command -v sbcast >/dev/null 2>&1; then
  sbcast -f /tmp/agent-sidecar-src.tgz /tmp/agent-sidecar-src.tgz
else
  echo 'sbcast missing; scp from mn'
fi
srun -N3 -n3 -l bash -c 'tar xzf /tmp/agent-sidecar-src.tgz -C /tmp/agent-sidecar && ls /tmp/agent-sidecar/src/agent_sidecar/__init__.py && hostname -s'
echo
echo \"======== 2d. agent srun (sidecar overlap + user step) ========\"
python3 -m agent_sidecar --agent-verbose --agent-profile=tools-only \
  --agent-skills=proc-monitor,node-diag \
  --agent-output-dir '$OUT' \
  srun -n3 -l -- \
  bash -c 'echo HOST=\$(hostname -s) PROC=\$SLURM_PROCID NODEID=\$SLURM_NODEID JOB=\$SLURM_JOB_ID PID=\$\$ PPID=\$PPID; echo --- processes on \$(hostname -s) ---; ps -eo pid,ppid,user,comm,args | grep -E \"agent_sidecar|srun|slurmstepd\" | grep -v grep; sleep 4'
echo
echo \"======== 2e. salloc ending ========\"
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
  echo "---- files ----"
  find "$RUN" -type f | sort
fi
echo "======== done ========"
