#!/bin/bash
# 16 — 环境未 inherit：strip LD_LIBRARY_PATH then run the 01 missing-.so binary.
# Cluster demo uses srun --export=NONE (see scripts/run_fault_case.sh 16).
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
BIN="${AGENT_MISSING_SO_BIN:-$HERE/../01/mpi_missing_so}"
unset LD_LIBRARY_PATH || true
export -n LD_LIBRARY_PATH 2>/dev/null || true
exec "$BIN" "$@"
