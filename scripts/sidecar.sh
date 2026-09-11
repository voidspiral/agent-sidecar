#!/bin/bash
# Login-host wrap: collect beside srun and run job-assist OpenCode on tool artifacts.
# Usage: sidecar.sh [--agent-*] srun <slurm> <user>
# --agent-profile=tools-only skips the model. Sidecar flags go before srun.
# Source-authorized root-cause is sidecar-analy.sh --log DIR --code PATH.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m agent_sidecar "$@"
