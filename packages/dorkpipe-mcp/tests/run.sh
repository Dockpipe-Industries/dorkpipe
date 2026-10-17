#!/usr/bin/env bash
# Self-contained Go tests for DorkPipe MCP (`dorkpipe.mcp`).
# From repo root: dockpipe package test --only dorkpipe.mcp
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
MCP_ROOT="$ROOT/packages/dorkpipe-mcp"
source "$ROOT/packages/dorkpipe/tests/lib/test-tools.sh"
dorkpipe_test_init_sdk "$ROOT"
export TMPDIR="${DORKPIPE_MCP_PACKAGE_TEST_TMPDIR:-$(dockpipe_sdk path state tmp package-tests)}"
mkdir -p "$TMPDIR"
mkdir -p "$(dockpipe_sdk path build go-cache)" "$(dockpipe_sdk path build go-tmp)"
export GOCACHE="${GOCACHE:-$(dockpipe_sdk path build go-cache)}"
export GOTMPDIR="${GOTMPDIR:-$(dockpipe_sdk path build go-tmp)}"
# The root test workflow verifies the committed source SDK pin and supplies
# temporary module files for both Go suites. Direct go test bypasses that contract.
(
  cd "$ROOT"
  "$DOCKPIPE_TEST_DOCKPIPE_BIN" --workflow-file "$ROOT/workflows/test/config.yml"
)
bash "$MCP_ROOT/tests/test_build_source_operation_results.sh"
