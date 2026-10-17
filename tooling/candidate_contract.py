"""Local Linux amd64 package preparation contract; no remote receipt authority."""
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import stat
import subprocess
import tempfile


TOOLS = ('dorkpipe', 'mcpd', 'orchestrate-helper', 'skills-render')
MAX_FILES = 10000
MAX_SOURCE_BYTES = 256 << 20
MAX_RECEIPT_BYTES = 4 << 20
MAX_BINARY_BYTES = 256 << 20
MODULES = ('packages/dorkpipe/lib', 'packages/dorkpipe-mcp')
MANIFESTS = ('packages/dorkpipe/package.yml', 'packages/dorkpipe-mcp/package.yml')
LOCKS = ('release/dependencies.lock.json', 'release/toolchains.lock.json')
PREPARATION_CODE = (
    'tooling/go_candidate.py', 'tooling/candidate_contract.py',
    'tooling/install_package_candidate.py', 'tooling/prepare_package_candidate.py',
    'tooling/run_shell_candidate.py',
    '.github/scripts/bootstrap-dockpipe.py',
    'workflows/package.candidate/config.yml', 'workflows/package.candidate/assets/run.sh',
    'workflows/sdk.candidate/assets/run.sh',
    'packages/dorkpipe/assets/scripts/build-source.sh',
    'packages/dorkpipe/resolvers/dorkpipe/assets/scripts/package-consumer-artifacts.sh',
)


def require_target():
    if platform.system() != 'Linux' or platform.machine() not in {'x86_64', 'amd64'}:
        raise ValueError('Independent package preparation supports Linux amd64 only')
    for variable, expected in [('GOOS', 'linux'), ('GOARCH', 'amd64'), ('DORKPIPE_STACK_GOARCH', 'amd64')]:
        if os.environ.get(variable, expected) != expected:
            raise ValueError(f'{variable} must be {expected} for this prepared candidate')


def regular_file(path, maximum):
    if any(parent.is_symlink() for parent in path.parents):
        raise ValueError(f'Linked file parent: {path}')
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError(f'Expected regular file: {path}')
    if path.stat().st_size > maximum:
        raise ValueError(f'File exceeds preparation capacity: {path}')


def file_digest(path, maximum):
    regular_file(path, maximum)
    digest = hashlib.sha256()
    total = 0
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            total += len(block)
            if total > maximum:
                raise ValueError('File grew beyond preparation capacity')
            digest.update(block)
    return total, digest.hexdigest()


def unique_keys(pairs):
    output = {}
    for key, value in pairs:
        if key in output:
            raise ValueError('Duplicate preparation receipt field')
        output[key] = value
    return output


def read_json(path, maximum):
    regular_file(path, maximum)
    with path.open('rb') as stream:
        data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError('Preparation JSON exceeds capacity')
    return json.loads(data, object_pairs_hook=unique_keys)


def source_identity(root):
    """Inventory both modules, embed assets, manifests, locks and builder code.

    Reuse SDK candidate capacity: at most 10,000 source entries and 256 MiB.
    Module bin/cache directories are generated output and cannot be build inputs.
    """
    paths = []
    visited_entries = 0
    for relative in MODULES:
        module = root / relative
        if module.is_symlink() or not module.is_dir():
            raise ValueError('Missing or linked package Go module')
        pending = [module]
        while pending:
            current = pending.pop()
            with os.scandir(current) as entries:
                for entry in entries:
                    visited_entries += 1
                    if visited_entries > MAX_FILES:
                        raise ValueError('Package source inventory exceeds entry capacity')
                    if entry.is_symlink():
                        raise ValueError('Linked entry in package source inventory')
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name not in {'bin', '.git', '.cache'}:
                            pending.append(Path(entry.path))
                    else:
                        paths.append(Path(entry.path))
        for required in ['go.mod', 'go.sum']:
            regular_file(module / required, MAX_SOURCE_BYTES)
    paths = set(paths)
    paths.update(root / name for name in (*MANIFESTS, *LOCKS, *PREPARATION_CODE))
    if len(paths) > MAX_FILES:
        raise ValueError('Package source inventory exceeds file capacity')
    inventory = []
    total = 0
    for path in sorted(paths):
        size, digest = file_digest(path, MAX_SOURCE_BYTES - total)
        total += size
        inventory.append({'path': path.relative_to(root).as_posix(), 'bytes': size, 'sha256': digest})
    versions = []
    for relative in MANIFESTS:
        manifest_path = root / relative
        regular_file(manifest_path, 64 << 10)
        matches = re.findall(r'^version:\s*([0-9]+\.[0-9]+\.[0-9]+)\s*$', manifest_path.read_text(), re.MULTILINE)
        if len(matches) != 1:
            raise ValueError('Package manifest requires one explicit numeric version')
        versions.append(matches[0])
    if len(set(versions)) != 1:
        raise ValueError('DorkPipe and MCP package versions must match')
    digest = hashlib.sha256(json.dumps(inventory, separators=(',', ':')).encode()).hexdigest()
    return {'version': versions[0], 'sha256': digest, 'files': inventory}


def prepared_directory(root):
    # The fixed maintenance workflow owns its preparation scope. Callers cannot
    # choose an arbitrary receipt directory or reconstruct runtime paths.
    dockpipe = os.environ.get('DOCKPIPE_BIN') or 'dockpipe'
    with tempfile.TemporaryFile() as output:
        subprocess.run([
            dockpipe, 'scope', 'workflow', 'package.candidate', 'prepared', '--workdir', str(root),
        ], stdout=output, stderr=subprocess.DEVNULL, check=True, timeout=30)
        output.seek(0)
        data = output.read(4097)
    if len(data) > 4096:
        raise ValueError('Workflow scope output exceeds 4096 bytes')
    value = data.decode('utf-8').rstrip('\n')
    if not value or '\n' in value or '\r' in value or '\0' in value:
        raise ValueError('Invalid package preparation workflow scope')
    path = Path(value)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('Package preparation workflow scope must be absolute')
    return path


def validate_binaries(directory, entries):
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError('Prepared binary directory is missing or linked')
    if not isinstance(entries, list) or len(entries) != len(TOOLS):
        raise ValueError('Prepared receipt requires exactly four package tools')
    by_name = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {'name', 'bytes', 'sha256'}:
            raise ValueError('Malformed prepared binary entry')
        name = entry['name']
        if not isinstance(name, str) or name not in TOOLS or name in by_name:
            raise ValueError('Unexpected or duplicate prepared tool')
        if type(entry['bytes']) is not int or not 0 < entry['bytes'] <= MAX_BINARY_BYTES:
            raise ValueError('Invalid prepared tool size')
        if not isinstance(entry['sha256'], str) or not re.fullmatch(r'[0-9a-f]{64}', entry['sha256']):
            raise ValueError('Invalid prepared tool digest')
        by_name[name] = entry
    if set(path.name for path in directory.iterdir()) != set(TOOLS):
        raise ValueError('Missing or extra prepared tool files')
    for name, entry in by_name.items():
        size, digest = file_digest(directory / name, MAX_BINARY_BYTES)
        if size != entry['bytes'] or digest != entry['sha256']:
            raise ValueError('Prepared binary checksum or size drift')
    return by_name


def validate_public_repository(payload, expected_repository):
    """Require the exact public producer before publishing or consuming a release."""
    try:
        repository = json.loads(payload, object_pairs_hook=unique_keys)
    except (TypeError, ValueError) as error:
        raise ValueError('Invalid public repository metadata') from error
    if (not isinstance(repository, dict)
            or repository.get('full_name') != expected_repository
            or repository.get('private') is not False
            or repository.get('visibility') != 'public'):
        raise ValueError('Source repository must be the exact public producer')
