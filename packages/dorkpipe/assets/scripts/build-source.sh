#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
package_root="$(cd -- "${DOCKPIPE_PACKAGE_ROOT:-$script_dir/../..}" && pwd)"
repo_root="$(cd -- "$package_root/../.." && pwd)"
if [[ -z "${DOCKPIPE_SOURCE_BUILD_OUT_DIR:-}" ]]; then
  sdk_exports="$("${DOCKPIPE_BIN:-dockpipe}" sdk --workdir "$repo_root")"
  eval "$sdk_exports"
  DOCKPIPE_SOURCE_BUILD_OUT_DIR="$(dockpipe_sdk path state tooling bin)"
fi
output="$DOCKPIPE_SOURCE_BUILD_OUT_DIR"

python3 "$repo_root/tooling/install_package_candidate.py" \
  --operation source-dorkpipe --output "$output"
