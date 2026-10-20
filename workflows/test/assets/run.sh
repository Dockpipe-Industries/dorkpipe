#!/usr/bin/env bash
set -euo pipefail
dockpipe_bin="${DOCKPIPE_BIN:-dockpipe}"
artifacts="$("$dockpipe_bin" scope artifacts)"
candidate_parent="$(mktemp -d "$artifacts/candidate.XXXXXX")"
python3 -B tooling/go_candidate.py --source . \
  --manifest "${DOCKPIPE_GO_SDK_MANIFEST:?Select the SDK manifest}" \
  --archive "${DOCKPIPE_GO_SDK_ARCHIVE:?Select the SDK archive}" \
  --manifest-sha256 "${DOCKPIPE_GO_SDK_MANIFEST_SHA256:?Pin the manifest SHA-256}" \
  --go "${GO_EXECUTABLE:-go}" --output "$candidate_parent/build" --tests
