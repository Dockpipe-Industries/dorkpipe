#!/usr/bin/env bash
set -euo pipefail
dockpipe_bin="${DOCKPIPE_BIN:-dockpipe}"
artifacts="$("$dockpipe_bin" scope artifacts)"
npm --prefix tooling/vscode-extensions/dockpipe-language-support ci --no-audit --no-fund
npm --prefix tooling/vscode-extensions/pipeon ci --no-audit --no-fund
exec bash tooling/vscode-extensions/scripts/build.sh "$artifacts/editors"
