#!/usr/bin/env bash
set -euo pipefail
: "${DOCKPIPE_RELEASE_ARCHIVE:?Supply the local source-locked released engine archive}"
dockpipe_bin="${DOCKPIPE_BIN:-dockpipe}"
source_root="$("$dockpipe_bin" scope source)"
artifacts="$("$dockpipe_bin" scope artifacts)"
attempt="$(mktemp -d "$artifacts/package-store.XXXXXX")"
# Every attempt owns an empty store. Existing core or maintainer packages cannot
# leak into the package export, and source hooks write only attempt-owned tools.
export DOCKPIPE_PACKAGES_ROOT="$attempt/packages"
export DOCKPIPE_SOURCE_BUILD_OUT_DIR="$attempt/source-tools"
"$dockpipe_bin" package build source --workdir "$source_root" --only dorkpipe
"$dockpipe_bin" package build source --workdir "$source_root" --only dorkpipe.mcp
"$dockpipe_bin" package compile resolvers --workdir "$source_root" \
  --from "$source_root/packages/dorkpipe" --force
"$dockpipe_bin" package compile workflows --workdir "$source_root" \
  --from "$source_root/packages/dorkpipe/workflows" --force
# Retain published workflow identities from their authoritative resolver leaves.
python3 -B "$source_root/tooling/generate_compat_workflows.py" \
  --source-root "$source_root" --output "$attempt/compatibility" \
  --ownership "$source_root/release/package-ownership.json"
"$dockpipe_bin" package compile workflows --workdir "$source_root" \
  --from "$attempt/compatibility" --force
"$dockpipe_bin" package build store --workdir "$source_root" --only all \
  --out "$attempt/store" --version "$(tr -d ' \t\r\n' < "$source_root/VERSION")"
python3 -B "$source_root/tooling/validate_package_store.py" --store "$attempt/store" \
  --ownership "$source_root/release/package-ownership.json"
# Publish this attempt's path only after the exact owned leaf set passes validation.
printf '%s\n' "$attempt/store" > "$artifacts/store.path"
printf 'Validated DorkPipe package store: %s\n' "$attempt/store"
