#!/usr/bin/env bash
set -euo pipefail

source_dir="${DOCKPIPE_COMPILE_SOURCE_DIR:?DOCKPIPE_COMPILE_SOURCE_DIR is required}"
staging_dir="${DOCKPIPE_COMPILE_STAGING_DIR:?DOCKPIPE_COMPILE_STAGING_DIR is required}"
: "${DOCKPIPE_COMPILE_WORKDIR:?DOCKPIPE_COMPILE_WORKDIR is required}"
: "${DOCKPIPE_RELEASE_ARCHIVE:?Supply the source-locked released Linux amd64 engine archive}"
package_root="$(cd -- "$source_dir/../.." && pwd)"
repo_root="$(cd -- "$package_root/../.." && pwd)"

python3 "$repo_root/tooling/install_package_candidate.py" \
  --operation consumer --output "$staging_dir/assets/tooling/bin/linux" \
  --engine-archive "$DOCKPIPE_RELEASE_ARCHIVE"
