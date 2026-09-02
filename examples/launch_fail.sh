#!/bin/bash
# Documented missing binary for OpenCode launch-fail diagnosis.
# Compute nodes should not find this path. Do not create examples/no-such-mpi.
echo "This script is documentation only." >&2
echo "Demo: scripts/demo_opencode_launch_fail.sh" >&2
echo "Expected user argv after -- : /shared/agent-sidecar/examples/no-such-mpi" >&2
exit 2
