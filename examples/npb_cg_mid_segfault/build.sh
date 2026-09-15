#!/bin/bash
# Build patched NPB 3.4-MPI CG (Class B default) onto a shared path.
# Requires NPB_MPI_ROOT = NPB3.4-MPI directory (contains CG/cg.f90).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
CLASS="${NPB_CG_CLASS:-B}"
SHARED="${AGENT_SHARED:-/shared}"
WORK="${NPB_BUILD_DIR:-$SHARED/npb-build/cg-mid-segfault}"
DEST="$ROOT/examples/cg.${CLASS}.x"

if [[ -z "${NPB_MPI_ROOT:-}" ]]; then
  echo "NPB_MPI_ROOT must point at the NPB 3.4-MPI directory (contains CG/cg.f90)." >&2
  exit 2
fi
if [[ ! -f "$NPB_MPI_ROOT/CG/cg.f90" || ! -f "$NPB_MPI_ROOT/Makefile" ]]; then
  echo "NPB_MPI_ROOT=$NPB_MPI_ROOT is not an NPB 3.4-MPI tree (need CG/cg.f90 and Makefile)." >&2
  echo "Set NPB_MPI_ROOT to the NPB 3.4-MPI directory." >&2
  exit 2
fi

mkdir -p "$WORK" "$WORK/bin"
rsync -a --delete --exclude bin/ --exclude 'CG/*.o' --exclude 'CG/*.mod' \
  "$NPB_MPI_ROOT/" "$WORK/"
mkdir -p "$WORK/bin"
# Original tree stays clean; patch the copy.
patch -p1 -d "$WORK" -i "$HERE/cg.f90.patch"
make -C "$WORK" cg "CLASS=$CLASS"
src="$WORK/bin/cg.${CLASS}.x"
test -x "$src"
cp -f "$src" "$DEST"
chmod +x "$DEST"
echo "installed $DEST"
