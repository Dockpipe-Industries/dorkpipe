#!/usr/bin/env bash
set -euo pipefail
dockpipe_bin="${DOCKPIPE_BIN:-dockpipe}"
test -s AGENTS.md
test -s README.md
test -s dockpipe.config.json
for config in workflows/*/config.yml; do
  "$dockpipe_bin" workflow validate "$config"
done
python3 -B tooling/test_go_candidate.py
python3 -B tooling/test_run_shell_candidate.py
python3 -B tooling/test_sdk_pin.py
python3 -B tooling/test_fetch_sdk_release.py
python3 -B tooling/test_independent_hooks.py
python3 -B tooling/test_validate_package_store.py
python3 -B tooling/test_generate_compat_workflows.py
python3 -B tooling/test_package_delivery.py
python3 -B tooling/test_bootstrap.py
printf '%s\n' 'Repository scaffold and workflow declarations passed; application/build proof is separate.'
