#!/usr/bin/env bash
set -euo pipefail

: "${GITHUB_SHA:?Release delivery requires the exact source commit}"
dockpipe_bin="${DOCKPIPE_BIN:-dockpipe}"
source_root="$("$dockpipe_bin" scope source)"
artifacts="$("$dockpipe_bin" scope artifacts)"
store_path="$(cat "$("$dockpipe_bin" scope workflow package.compile store.path)")"
editors_path="$("$dockpipe_bin" scope workflow editor.candidate editors)"
delivery="$(mktemp -d "$artifacts/delivery.XXXXXX")"
python3 -B "$source_root/tooling/assemble_package_delivery.py" \
  --source-root "$source_root" --store "$store_path" --editors "$editors_path" \
  --source-sha "$GITHUB_SHA" --output "$delivery"
printf '%s\n' "$delivery" > "$artifacts/delivery.path"
