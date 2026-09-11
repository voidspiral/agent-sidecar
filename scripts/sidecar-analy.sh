#!/bin/bash
# Login-host analysis. --log is the sidecar run directory. LLM is on by default.
# Usage: sidecar-analy.sh --log DIR [--code PATH] [--no-llm]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m agent_sidecar analy "$@"
