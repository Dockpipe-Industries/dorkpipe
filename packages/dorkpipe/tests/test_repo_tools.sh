#!/usr/bin/env bash
# Shared Dockpipe helper should retain the explicitly selected installed CLI, and the
# DorkPipe package helper should resolve the declared source-build tooling output.
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"

# shellcheck source=packages/dorkpipe/tests/lib/test-tools.sh
source "$ROOT/packages/dorkpipe/tests/lib/test-tools.sh"
dorkpipe_test_init_sdk "$ROOT"
# shellcheck source=/dev/null
source "$ROOT/packages/dorkpipe/resolvers/dorkpipe/assets/scripts/lib/dorkpipe-cli.sh"

dockpipe_sdk refresh "$ROOT"

expected_dockpipe="$DOCKPIPE_TEST_DOCKPIPE_BIN"
actual_dockpipe="$(dockpipe_sdk require dockpipe-bin)"
if [[ "$actual_dockpipe" != "$expected_dockpipe" ]]; then
  echo "test_repo_tools: expected dockpipe $expected_dockpipe, got $actual_dockpipe" >&2
  exit 1
fi

expected_dorkpipe="$(dockpipe_sdk require tooling-bin dorkpipe)"
actual_dorkpipe="$(dorkpipe_script_resolve_bin "$ROOT")"
if [[ "$actual_dorkpipe" != "$expected_dorkpipe" ]]; then
  echo "test_repo_tools: expected dorkpipe $expected_dorkpipe, got $actual_dorkpipe" >&2
  exit 1
fi

actual_orch="$(dorkpipe_script_resolve_bin "$ROOT")"
if [[ "$actual_orch" != "$expected_dorkpipe" ]]; then
  echo "test_repo_tools: expected orchestrator dorkpipe $expected_dorkpipe, got $actual_orch" >&2
  exit 1
fi

ci_analysis="$(DOCKPIPE_WORKDIR="$ROOT" DOCKPIPE_CI_ARTIFACT_SCOPE=package:dorkpipe bash -c '
  sdk_exports="$("$DOCKPIPE_BIN" sdk --workdir "$DOCKPIPE_WORKDIR")" || exit
  eval "$sdk_exports"
  dockpipe_sdk ci analysis findings.json
')"
runtime_root="$("$expected_dockpipe" __state package-runtime --workdir "$ROOT" --owner dorkpipe)"
expected_ci_analysis="$runtime_root/ci/analysis/findings.json"
if [[ "$ci_analysis" != "$expected_ci_analysis" ]]; then
  echo "test_repo_tools: expected explicit DorkPipe CI binding at $expected_ci_analysis, got $ci_analysis" >&2
  exit 1
fi

echo "test_repo_tools OK"
