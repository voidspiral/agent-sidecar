#!/bin/bash
# Login-host helper: rsync this sidecar plus mpi-monitor and eth-monitor onto NFS /shared.
# Usage: bash scripts/deploy_shared.sh [--dry-run] [--shared DIR] <mpi-monitor-dir> <eth-monitor-dir>
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m agent_sidecar deploy --sidecar "$ROOT" "$@"
