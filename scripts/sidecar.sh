#!/bin/bash
# Login-host wrap: collect beside srun. Omits OpenCode unless --agent-profile is set.
# Usage: sidecar.sh srun [ --agent-* ] <slurm/user argv>
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
export AGENT_ENTRY=sidecar
exec python3 -m agent_sidecar "$@"
