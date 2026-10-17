#!/usr/bin/env bash
set -euo pipefail

dockpipe_bin="${DOCKPIPE_BIN:-dockpipe}"
source_root="$("$dockpipe_bin" scope source)"
mode="${PACKAGE_HOST_MODE:?Select local, frozen or pin mode}"
arguments=(--mode "$mode")
case "$mode" in
  local|frozen)
    : "${PACKAGE_HOST_DELIVERY:?Supply exact frozen delivery directory}"
    : "${PACKAGE_HOST_SOURCE_SHA:?Supply exact producer source commit}"
    arguments+=(--delivery "$PACKAGE_HOST_DELIVERY" --source-sha "$PACKAGE_HOST_SOURCE_SHA")
    ;;
  pin) ;;
  *) echo 'Invalid package-host mode' >&2; exit 2 ;;
esac
if [[ "${PACKAGE_HOST_PUBLISH:-0}" == 1 ]]; then
  : "${PACKAGE_HOST_CHANNEL:?Supply staging or production channel}"
  arguments+=(--publish --channel "$PACKAGE_HOST_CHANNEL")
fi
python3 -B "$source_root/tooling/publish_package_host.py" "${arguments[@]}"
