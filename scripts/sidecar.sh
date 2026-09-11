#!/bin/bash
# Login-host wrap: collect beside srun and run job-assist OpenCode on tool artifacts.
# Usage: sidecar.sh srun [ --agent-* ] <slurm/user argv>
# --agent-profile=tools-only skips the model. Source-authorized root-cause
# analysis is sidecar-analy.sh --log DIR --code PATH.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m agent_sidecar "$@"
