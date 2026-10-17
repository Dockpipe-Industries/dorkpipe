#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
# Source hooks now install verified prepared tools instead of invoking Go builds.
# The owning fixture checks SDK/explicit outputs, bytes and executable modes,
# and rejection of missing or corrupted preparation without replacing outputs.
python3 -B "$ROOT/tooling/test_independent_hooks.py" \
  IndependentHookTests.test_mcp_source_hook_contract

echo "dorkpipe-mcp test_build_source_operation_results OK"
