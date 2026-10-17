#!/usr/bin/env python3
"""Generate legacy workflow identities from the authoritative resolver leaves."""
import argparse
import hashlib
import json
from pathlib import Path
import re

import candidate_contract
import validate_package_store as validator


MAX_FILES = 20000
MAX_BYTES = 256 << 20
MAX_METADATA_BYTES = 64 << 10


def read_metadata(path):
    candidate_contract.regular_file(path, MAX_METADATA_BYTES)
    with path.open('rb') as stream:
        data = stream.read(MAX_METADATA_BYTES + 1)
    if len(data) > MAX_METADATA_BYTES:
        raise ValueError('Compatibility metadata grew beyond capacity')
    return data.decode('utf-8')


def check_manifest(text, name, ownership):
    expected = {'kind': 'resolver', 'name': name, 'version': ownership['version'],
                'namespace': ownership['namespace'], 'license': 'Apache-2.0',
                'min_dockpipe_version': ownership['min_dockpipe_version']}
    for field, value in expected.items():
        if validator.manifest_scalar(text, field) != value:
            raise ValueError(f'Compatibility source {name} differs in {field}')
    if re.search(r'^depends:', text, re.MULTILINE):
        raise ValueError('Resolver aliases cannot introduce workflow dependencies')
    dependencies = re.findall(r'^requires_resolvers:[ \t]*\n((?:[ \t]*-[^\n]*\n)+)', text, re.MULTILINE)
    if name == 'dorkpipe':
        if re.search(r'^requires_resolvers:', text, re.MULTILINE):
            raise ValueError('Shared resolver must not depend on itself')
    elif dependencies != ['- dorkpipe\n']:
        raise ValueError('Compatibility source requires exactly the shared dorkpipe resolver')


def generate(source_root, output, ownership_path):
    ownership = validator.load_ownership(ownership_path)
    source = source_root / 'packages/dorkpipe/resolvers'
    if source.is_symlink() or any(parent.is_symlink() for parent in source.parents):
        raise ValueError('Compatibility source root cannot be linked')
    if {path.name for path in source.iterdir()} != set(ownership['resolvers']):
        raise ValueError('Compatibility resolver source identities differ from ownership')
    if output.exists() or output.is_symlink():
        raise ValueError('Compatibility output must be fresh')
    if any(parent.is_symlink() for parent in output.parents):
        raise ValueError('Compatibility output parent cannot be linked')

    # Inventory first: only bounded, regular authored leaf files can be copied.
    # The shared-assets alias has no assets of its own; its typed resolver edge
    # selects the same-version resolver, avoiding a workflow self-dependency.
    plans = []
    total = 0
    count = 0
    for name in sorted(ownership['resolvers']):
        leaf = source / name
        if not leaf.is_dir() or leaf.is_symlink():
            raise ValueError('Compatibility source leaf must be a directory')
        manifest = read_metadata(leaf / 'package.yml')
        check_manifest(manifest, name, ownership)
        config = read_metadata(leaf / 'config.yml')
        if validator.manifest_scalar(config, 'name') != name:
            raise ValueError('Compatibility source config identity differs')
        notice = read_metadata(leaf / 'LICENSE').encode('utf-8')
        if hashlib.sha256(notice).hexdigest() != ownership['license_sha256']:
            raise ValueError('Compatibility source license differs from ownership')
        if name != 'dorkpipe' and re.search(r'^compile_hooks:', config, re.MULTILINE):
            raise ValueError('Compatibility workflow cannot invoke resolver compile hooks')
        files = []
        for path in sorted(leaf.rglob('*')):
            relative = path.relative_to(leaf)
            if path.is_symlink():
                raise ValueError('Compatibility source contains a linked member')
            if any(part.startswith('.') or part in {'bin', '__pycache__', 'node_modules'} for part in relative.parts):
                raise ValueError('Compatibility source contains generated or private state')
            if path.is_dir():
                continue
            candidate_contract.regular_file(path, MAX_BYTES)
            count += 1
            total += path.stat().st_size
            if count > MAX_FILES or total > MAX_BYTES:
                raise ValueError('Compatibility source exceeds capacity')
            if name != 'dorkpipe' or relative.as_posix() in {'package.yml', 'LICENSE'}:
                files.append((path, relative))
        workflow_manifest = re.sub(r'^kind:[^\r\n]*$', 'kind: workflow', manifest, count=1, flags=re.MULTILINE)
        if name == 'dorkpipe':
            workflow_manifest += '\nrequires_resolvers:\n- dorkpipe\n'
            config = f"name: dorkpipe\nnamespace: {ownership['namespace']}\nsteps: []\n"
        plans.append((name, files, workflow_manifest, config))

    output.mkdir(parents=True)
    copied_bytes = 0
    for name, files, manifest, config in plans:
        destination = output / name
        destination.mkdir()
        for path, relative in files:
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            candidate_contract.regular_file(path, MAX_BYTES)
            with path.open('rb') as source_stream, target.open('xb') as target_stream:
                while True:
                    block = source_stream.read(1 << 20)
                    if not block:
                        break
                    copied_bytes += len(block)
                    if copied_bytes > MAX_BYTES:
                        raise ValueError('Compatibility source grew beyond copy capacity')
                    target_stream.write(block)
            target.chmod(path.stat().st_mode & 0o777)
        (destination / 'package.yml').write_text(manifest)
        (destination / 'config.yml').write_text(config)
        if name == 'dorkpipe':
            profile = destination / 'assets/flatpak/package.json'
            profile.parent.mkdir(parents=True)
            profile.write_text(json.dumps({
                'schema': 1, 'artifacts': [{'kind': 'workflow', 'name': name}],
                'tools': [], 'host_commands': [], 'required_files': [],
            }, indent=2) + '\n')
    return [name for name, _, _, _ in plans]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ownership', type=Path, required=True)
    args = parser.parse_args()
    try:
        names = generate(args.source_root, args.output, args.ownership)
    except (OSError, ValueError, UnicodeError) as error:
        parser.exit(1, f'Compatibility workflow generation failed: {error}\n')
    print(f'Generated {len(names)} compatibility workflows from resolver sources')


if __name__ == '__main__':
    main()
