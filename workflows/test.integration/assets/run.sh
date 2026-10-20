#!/usr/bin/env bash
set -euo pipefail
dockpipe_bin="${DOCKPIPE_BIN:-dockpipe}"
artifacts="$("$dockpipe_bin" scope artifacts)"
candidate_parent="$(mktemp -d "$artifacts/candidate.XXXXXX")"
: "${DORKPIPE_TEST_PIPEON_SOURCE:?Select an absolute private Pipeon source checkout}"
export DORKPIPE_TEST_PIPEON_SOURCE
python3 -B tooling/go_candidate.py --source . \
  --manifest "${DOCKPIPE_GO_SDK_MANIFEST:?}" --archive "${DOCKPIPE_GO_SDK_ARCHIVE:?}" \
  --manifest-sha256 "${DOCKPIPE_GO_SDK_MANIFEST_SHA256:?}" \
  --go "${GO_EXECUTABLE:-go}" --output "$candidate_parent/build" --tests
