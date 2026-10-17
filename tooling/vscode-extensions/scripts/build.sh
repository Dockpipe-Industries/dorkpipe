#!/usr/bin/env bash
set -euo pipefail

editors_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output_root="${1:?Usage: build.sh <absolute-output-directory>}"
if [[ "$output_root" != /* ]]; then
  echo "Use an absolute output directory." >&2
  exit 1
fi
mkdir -p "$output_root"
vsce_entrypoint="${DORKPIPE_VSCE_ENTRYPOINT:-$editors_root/dockpipe-language-support/node_modules/@vscode/vsce/vsce}"
if [[ ! -f "$vsce_entrypoint" ]]; then
  echo "Run npm ci in dockpipe-language-support before packaging." >&2
  exit 1
fi

node --check "$editors_root/dockpipe-language-support/extension.js"
node "$editors_root/dockpipe-language-support/extension.test.js"
npm --prefix "$editors_root/pipeon" run build
node "$editors_root/pipeon/scripts/webview-smoke.js"
node "$editors_root/pipeon/scripts/runtime-contract.test.js"
for extension in dockpipe-language-support pipeon; do
  (
    cd "$editors_root/$extension"
    version="$(node -p "require('./package.json').version")"
    node "$vsce_entrypoint" package --no-dependencies \
      --out "$output_root/$extension-$version.vsix"
  )
done
python3 - "$output_root" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
files = []
for path in sorted(root.glob('*.vsix')):
    files.append({'path': path.name, 'bytes': path.stat().st_size,
                  'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
(root / 'extensions.json').write_text(json.dumps({'schema': 1, 'files': files}, indent=2) + '\n')
PY
