#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/../.." && pwd)"
python3 "$script_dir/bootstrap-dockpipe.py" --lock "$repo_root/release/toolchains.lock.json" "$@"
