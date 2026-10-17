#!/usr/bin/env python3
"""Build packages against an explicitly pinned, local DockPipe Go SDK."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import tempfile
import candidate_contract

# Candidate-lane capacity: small source SDKs, never native runtimes or caches.
MAX_MANIFEST_BYTES = 4 * 1024 * 1024
MAX_LOCK_BYTES = 64 * 1024
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_SOURCE_BYTES = 256 * 1024 * 1024
MAX_FILES = 10000
MAX_TAR_BYTES = MAX_SOURCE_BYTES + MAX_FILES * 2048 + 10240
EXCLUDED = ('packages/dorkpipe/', 'packages/dorkpipe-mcp/', 'packages/pipeon/', 'packages/cockpit/')


def snapshot(path, maximum):
    with path.open('rb') as source:
        data = source.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError(f'Candidate input exceeds {maximum} bytes: {path}')
    return data


def safe_path(name):
    path = PurePosixPath(name)
    if not name or name == '.' or path.is_absolute() or path.as_posix() != name or '..' in path.parts or '\\' in name or ':' in name or '\x00' in name:
        raise ValueError(f'Unsafe SDK path: {name!r}')
    if name.startswith(EXCLUDED):
        raise ValueError(f'Private implementation included in SDK: {name}')
    return path


class ExpansionBudget:
    def __init__(self, source):
        self.source = source
        self.remaining = MAX_TAR_BYTES

    def read(self, size):
        if size < 0 or size > self.remaining:
            raise ValueError('SDK archive expansion exceeds candidate capacity')
        data = self.source.read(size)
        self.remaining -= len(data)
        return data


def unpack_sdk(manifest_path, archive_path, expected_manifest_sha256, destination):
    manifest_bytes = snapshot(manifest_path, MAX_MANIFEST_BYTES)
    if hashlib.sha256(manifest_bytes).hexdigest() != expected_manifest_sha256:
        raise ValueError('SDK manifest does not match the independently supplied SHA-256')
    manifest = json.loads(manifest_bytes)
    if manifest.get('schema') != 1 or manifest.get('module') != 'dockpipe':
        raise ValueError('Unsupported SDK manifest')
    inventory = manifest['files']
    if not inventory or len(inventory) > MAX_FILES:
        raise ValueError('SDK file count exceeds candidate capacity')
    expected = {}
    total = 0
    for entry in inventory:
        name = entry['path']
        safe_path(name)
        size = entry['bytes']
        if name in expected or type(size) is not int or size < 0:
            raise ValueError('Duplicate SDK path or invalid file size')
        total += size
        if total > MAX_SOURCE_BYTES:
            raise ValueError('SDK source size exceeds candidate capacity')
        expected[name] = entry
    identity = hashlib.sha256(json.dumps(inventory, separators=(',', ':')).encode()).hexdigest()
    if identity != manifest['source_digest']:
        raise ValueError('SDK source inventory identity mismatch')
    archive_bytes = snapshot(archive_path, MAX_ARCHIVE_BYTES)
    if len(archive_bytes) != manifest['bytes'] or hashlib.sha256(archive_bytes).hexdigest() != manifest['sha256']:
        raise ValueError('SDK archive checksum or size mismatch')
    if destination.exists():
        raise ValueError('Use a fresh SDK destination')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='sdk-import-', dir=destination.parent) as temporary:
        staging = Path(temporary)
        archive_copy = staging / 'input.tar.gz'
        archive_copy.write_bytes(archive_bytes)
        root = staging / 'source'
        root.mkdir()
        seen = set()
        with gzip.open(archive_copy, 'rb') as compressed, tarfile.open(fileobj=ExpansionBudget(compressed), mode='r|') as archive:
            for member in archive:
                prefix = 'dockpipe-go-sdk/'
                if not member.name.startswith(prefix) or not member.isfile():
                    raise ValueError('SDK archive contains an unexpected root or non-regular member')
                name = member.name[len(prefix):]
                safe_path(name)
                if name in seen or name not in expected:
                    raise ValueError(f'Duplicate or unlisted archive member: {name}')
                entry = expected[name]
                if member.size != entry['bytes']:
                    raise ValueError(f'SDK member size mismatch: {name}')
                source = archive.extractfile(member)
                digest = hashlib.sha256()
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                remaining = member.size
                with source, path.open('xb') as output:
                    while remaining:
                        chunk = source.read(min(1024 * 1024, remaining))
                        if not chunk:
                            raise ValueError(f'Truncated SDK member: {name}')
                        remaining -= len(chunk)
                        digest.update(chunk)
                        output.write(chunk)
                if digest.hexdigest() != entry['sha256']:
                    raise ValueError(f'SDK member checksum mismatch: {name}')
                seen.add(name)
        if seen != set(expected):
            raise ValueError('SDK archive is missing listed files')
        root.rename(destination)
    return manifest


def run_go(go, module, modfile, arguments, environment):
    subprocess.run([go, *arguments[:1], '-mod=mod', f'-modfile={modfile}', *arguments[1:]],
                   cwd=module, env=environment, check=True, timeout=900)


def unique_lock_keys(pairs):
    document = {}
    for key, value in pairs:
        if key in document:
            raise ValueError('Duplicate SDK dependency lock field')
        document[key] = value
    return document


def validate_sdk_pin(root, manifest, manifest_digest):
    """Enforce the committed source snapshot pin before any Go operation.

    The source prerelease version identifies an inventory, not a stable SDK ABI.
    Dependency upgrades require a reviewed source lock change and build evidence.
    """
    lock_path = root / 'release/dependencies.lock.json'
    document = json.loads(snapshot(lock_path, MAX_LOCK_BYTES), object_pairs_hook=unique_lock_keys)
    if not isinstance(document, dict) or type(document.get('schema')) is not int or document['schema'] != 1:
        raise ValueError('Unsupported SDK dependency lock schema')
    lock = document.get('dockpipe_go_sdk')
    required = {'version', 'source_commit', 'source_digest', 'manifest_sha256', 'archive_sha256'}
    if not isinstance(lock, dict) or set(lock) != required:
        raise ValueError('Incomplete or unknown SDK dependency lock fields')
    if not all(isinstance(value, str) for value in lock.values()):
        raise ValueError('SDK dependency lock fields must be strings')
    if not re.fullmatch(r'[0-9a-f]{40}', lock['source_commit']):
        raise ValueError('SDK dependency lock requires an exact source commit')
    for field in ['source_digest', 'manifest_sha256', 'archive_sha256']:
        if not re.fullmatch(r'[0-9a-f]{64}', lock[field]):
            raise ValueError(f'Invalid SDK dependency lock {field}')
    version_pattern = rf"[0-9]+\.[0-9]+\.[0-9]+-source\.{lock['source_digest'][:16]}"
    if not re.fullmatch(version_pattern, lock['version']):
        raise ValueError('SDK dependency lock version does not identify its source snapshot')
    expected = {
        'sdk_version': lock['version'],
        'source_commit': lock['source_commit'],
        'source_digest': lock['source_digest'],
        'sha256': lock['archive_sha256'],
    }
    if any(manifest.get(field) != value for field, value in expected.items()):
        raise ValueError('SDK manifest identity differs from the committed dependency lock')
    if manifest_digest != lock['manifest_sha256']:
        raise ValueError('SDK manifest digest differs from the committed dependency lock')


def build(args):
    root = args.source.resolve()
    output = args.output.resolve()
    if output.exists():
        raise ValueError('Use a fresh candidate output directory')
    output.mkdir(parents=True)
    sdk = output / 'sdk'
    manifest = unpack_sdk(args.manifest, args.archive, args.manifest_sha256, sdk)
    validate_sdk_pin(root, manifest, args.manifest_sha256)
    candidate_contract.require_target()
    source = candidate_contract.source_identity(root)
    environment = dict(os.environ, GOTOOLCHAIN='local', GOWORK='off', GOPROXY='off', GOSUMDB='off', CGO_ENABLED='0',
                       GOOS='linux', GOARCH='amd64', GOAMD64='v1', GOENV='off', GOFLAGS='',
                       TMPDIR=str(output), XDG_CACHE_HOME=str(output / 'test-cache'))
    if args.download_dependencies:
        download_environment = dict(environment, GOPROXY='https://proxy.golang.org', GOSUMDB='sum.golang.org',
                                    GOPRIVATE='', GONOPROXY='', GONOSUMDB='')
        subprocess.run([args.go, 'mod', 'download', 'all'], cwd=sdk,
                       env=download_environment, check=True, timeout=900)
    modules = [('orchestrator', root / 'packages/dorkpipe/lib'), ('mcp', root / 'packages/dorkpipe-mcp')]
    for name, module in modules:
        modfile = output / f'{name}.mod'
        shutil.copyfile(module / 'go.mod', modfile)
        sumfile = output / f'{name}.sum'
        sumfile.write_text((module / 'go.sum').read_text() + '\n' + (sdk / 'go.sum').read_text())
        subprocess.run([args.go, 'mod', 'edit', f'-modfile={modfile}', f'-replace=dockpipe={sdk}',
                        f'-replace=dorkpipe.orchestrator={modules[0][1]}'], cwd=module,
                       env=environment, check=True, timeout=30)
        if args.download_dependencies:
            subprocess.run([args.go, 'mod', 'download', f'-modfile={modfile}', 'all'], cwd=module,
                           env=download_environment, check=True, timeout=900)
        tests = ['./...'] if args.tests else []
        if tests:
            run_go(args.go, module, modfile, ['test', '-p=1', '-timeout=180s', *tests], environment)
        tools = [('dorkpipe', './cmd/dorkpipe'), ('skills-render', './cmd/skills-render'),
                 ('orchestrate-helper', './cmd/orchestrate-helper')] if name == 'orchestrator' else [('mcpd', './cmd/mcpd')]
        for tool, package in tools:
            run_go(args.go, module, modfile, ['build', '-trimpath', '-ldflags', f"-s -w -X main.Version={source['version']}",
                                            '-o', str(output / 'bin' / tool), package], environment)
    binaries = []
    for path in sorted((output / 'bin').iterdir()):
        binaries.append({'name': path.name, 'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    receipt = {'schema': 1, 'sdk_source_digest': manifest['source_digest'],
               'sdk_manifest_sha256': args.manifest_sha256, 'distribution_approved': False,
               'tests_requested': args.tests, 'binaries': binaries, 'target': {'os': 'linux', 'arch': 'amd64'},
               'source': source, 'sdk_lock': candidate_contract.read_json(root / 'release/dependencies.lock.json', MAX_LOCK_BYTES)}
    candidate_contract.validate_binaries(output / 'bin', binaries)
    if candidate_contract.source_identity(root) != source:
        raise ValueError('Package source changed while preparing candidate')
    encoded_receipt = json.dumps(receipt, indent=2) + '\n'
    if len(encoded_receipt.encode()) > candidate_contract.MAX_RECEIPT_BYTES:
        raise ValueError('Prepared receipt exceeds candidate capacity')
    (output / 'candidate.json').write_text(encoded_receipt)
    print(output / 'candidate.json')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--go', default='go')
    parser.add_argument('--tests', action='store_true')
    parser.add_argument('--download-dependencies', action='store_true', help='Explicitly fetch checksum-verified public Go dependencies before the offline build')
    build(parser.parse_args())
