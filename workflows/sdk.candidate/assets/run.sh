#!/usr/bin/env bash
set -euo pipefail
dockpipe_bin="${DOCKPIPE_BIN:-dockpipe}"
artifacts="$("$dockpipe_bin" scope artifacts)"
attempt="$(mktemp -d "$artifacts/candidate.XXXXXX")"
python3 -B tooling/fetch_sdk_release.py --output "$attempt/inputs"
unset GH_TOKEN
python3 -B tooling/prepare_package_candidate.py \
  --manifest "$attempt/inputs/sdk.json" --archive "$attempt/inputs/sdk.tar.gz" \
  --go "${GO_EXECUTABLE:-go}" --download-dependencies
python3 -B tooling/run_shell_candidate.py \
  --manifest "$attempt/inputs/sdk.json" --archive "$attempt/inputs/sdk.tar.gz" \
  --dockpipe-bin "$(command -v "$dockpipe_bin")" \
  --receipt "$attempt/shell-fixture.json"
prepared="$("$dockpipe_bin" scope workflow package.candidate prepared)"

delivery="$(mktemp -d "$artifacts/delivery.XXXXXX")"
source_root="$("$dockpipe_bin" scope source)"
tar -czf "$delivery/dorkpipe-go-candidate.tar.gz" \
  -C "$prepared" bin candidate.json -C "$source_root" LICENSE
cp "$attempt/shell-fixture.json" "$delivery/shell-fixture.json"
(cd "$delivery" && sha256sum dorkpipe-go-candidate.tar.gz shell-fixture.json > SHA256SUMS)
printf '%s\n' "$delivery" > "$artifacts/delivery.path"
printf 'Candidate delivery: %s\n' "$delivery"
