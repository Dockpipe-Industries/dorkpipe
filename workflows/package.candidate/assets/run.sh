#!/usr/bin/env bash
set -euo pipefail

: "${DOCKPIPE_GO_SDK_MANIFEST:?Supply the local pinned SDK manifest}"
: "${DOCKPIPE_GO_SDK_ARCHIVE:?Supply the local pinned SDK archive}"
dockpipe_bin="${DOCKPIPE_BIN:-dockpipe}"
source_root="$("$dockpipe_bin" scope source)"
python3 "$source_root/tooling/prepare_package_candidate.py" \
  --manifest "$DOCKPIPE_GO_SDK_MANIFEST" --archive "$DOCKPIPE_GO_SDK_ARCHIVE" --go "${GO_EXECUTABLE:-go}"
