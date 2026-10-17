#!/usr/bin/env python3
"""Run package shell proofs in a bounded package-source plus pinned-SDK fixture."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
import shutil
import subprocess
import tempfile

import candidate_contract
import go_candidate
import install_package_candidate


MAX_PRIVATE_FILES = 2500
MAX_PRIVATE_BYTES = 256 * 1024 * 1024
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_WORKSPACE_GRAPH_BYTES = 1 << 20
MAX_WORKSPACE_GRAPH_EDGES = 512
MAX_WORKSPACE_GRAPH_NODES = 128
WORKSPACE_FILES = ('go.work', 'go.work.sum')


def tracked_paths(root):
    result = subprocess.run(['git', '-C', str(root), 'ls-files', '-z', '--cached'],
                            capture_output=True, check=True, timeout=30)
    names = result.stdout.decode('utf-8').rstrip('\0').split('\0')
    if not names or len(names) > MAX_PRIVATE_FILES:
        raise ValueError('Private source inventory exceeds shell fixture capacity')
    return names


def private_path(name):
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or path.as_posix() != name or '..' in path.parts
            or '\\' in name or ':' in name or '\x00' in name):
        raise ValueError(f'Unsafe private source path: {name!r}')
    return path


def copy_regular(source, destination):
    candidate_contract.regular_file(source, MAX_FILE_BYTES)
    size = source.stat().st_size
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with source.open('rb') as input_file, destination.open('xb') as output_file:
        remaining = size
        while remaining:
            block = input_file.read(min(1024 * 1024, remaining))
            if not block:
                raise ValueError(f'Fixture input shrank while copying: {source}')
            output_file.write(block)
            digest.update(block)
            remaining -= len(block)
        if input_file.read(1):
            raise ValueError(f'Fixture input grew while copying: {source}')
    destination.chmod(source.stat().st_mode & 0o777)
    return {'bytes': size, 'sha256': digest.hexdigest()}


def prepare_fixture(root, manifest, archive, fixture):
    prepared_bin, binaries = install_package_candidate.verify_candidate(root)
    lock = candidate_contract.read_json(root / 'release/dependencies.lock.json', go_candidate.MAX_LOCK_BYTES)
    pinned_manifest = lock['dockpipe_go_sdk']['manifest_sha256']
    sdk = fixture / 'sdk-source'
    manifest_data = go_candidate.unpack_sdk(manifest, archive, pinned_manifest, sdk)
    go_candidate.validate_sdk_pin(root, manifest_data, pinned_manifest)

    source = fixture / 'source'
    shutil.move(str(sdk), str(source))
    inventory = [{'origin': 'sdk', **entry} for entry in manifest_data['files']]
    private_bytes = 0
    for name in tracked_paths(root):
        private_path(name)
        input_path = root / name
        private_bytes += input_path.stat().st_size
        if private_bytes > MAX_PRIVATE_BYTES:
            raise ValueError('Private source bytes exceed shell fixture capacity')
        destination = source / name
        if destination.exists():
            if name not in ('LICENSE', 'VERSION', 'workflows/README.md'):
                raise ValueError(f'Unexpected private/SDK path collision: {name}')
            destination.unlink()
        entry = copy_regular(input_path, destination)
        inventory.append({'origin': 'private', 'path': name, **entry})

    for name in WORKSPACE_FILES:
        fixture_path = root / 'packages/dorkpipe/tests/fixtures/backlog.remote' / name
        destination = source / name
        if destination.exists():
            raise ValueError(f'Unexpected workspace file in source fixture: {name}')
        entry = copy_regular(fixture_path, destination)
        inventory.append({'origin': 'test-workspace', 'path': name, **entry})

    prepared_source = prepared_bin.parent
    prepared_target = candidate_contract.prepared_directory(source)
    prepared_target.mkdir(parents=True)
    prepared_relative = prepared_target.relative_to(source)
    receipt_path = (prepared_relative / 'candidate.json').as_posix()
    entry = copy_regular(prepared_source / 'candidate.json', source / receipt_path)
    inventory.append({'origin': 'prepared-candidate', 'path': receipt_path, **entry})
    (prepared_target / 'bin').mkdir()
    tooling_bin = source / 'bin/.dockpipe/tooling/bin'
    tooling_bin.mkdir(parents=True)
    for name, binary in binaries.items():
        prepared_path = (prepared_relative / 'bin' / name).as_posix()
        install_package_candidate.copy_verified_binary(prepared_bin / name,
                                                         source / prepared_path, binary)
        inventory.append({'origin': 'prepared-candidate', 'path': prepared_path,
                          'bytes': binary['bytes'], 'sha256': binary['sha256']})
        install_package_candidate.copy_verified_binary(prepared_bin / name,
                                                         tooling_bin / name, binary)
        inventory.append({'origin': 'prepared-tool', 'path': f'bin/.dockpipe/tooling/bin/{name}',
                          'bytes': binary['bytes'], 'sha256': binary['sha256']})
    install_package_candidate.verify_candidate(source)
    subprocess.run(['git', 'init', '-q', str(source)], check=True, timeout=30)
    receipt = {'schema': 1, 'sdk_source_digest': manifest_data['source_digest'],
               'private_source': candidate_contract.source_identity(root),
               'test_fixture_files': sorted(inventory, key=lambda entry: entry['path'])}
    (fixture / 'shell-fixture.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return source


def shell_test_environment(dockpipe_bin):
    environment = dict(os.environ)
    for name in list(environment):
        if name.startswith('DOCKPIPE_'):
            environment.pop(name)
    environment.pop('CI', None)
    environment.pop('GOWORK', None)
    environment.pop('DORKPIPE_TEST_PIPEON_SOURCE', None)
    environment.update(DOCKPIPE_BIN=str(dockpipe_bin), GOPROXY='off', GOSUMDB='off',
                       GOENV='off', GOTOOLCHAIN='local')
    return environment


def workspace_module_graph(source, go, environment, timeout):
    with tempfile.TemporaryFile() as output:
        subprocess.run([go, 'mod', 'graph'], cwd=source, env=environment, stdout=output,
                       check=True, timeout=timeout)
        output.seek(0)
        graph = output.read(MAX_WORKSPACE_GRAPH_BYTES + 1)
    if len(graph) > MAX_WORKSPACE_GRAPH_BYTES:
        raise ValueError('Shell fixture workspace graph exceeds byte capacity')
    edges = graph.decode('utf-8').splitlines()
    if not edges or len(edges) > MAX_WORKSPACE_GRAPH_EDGES:
        raise ValueError('Shell fixture workspace graph exceeds edge capacity')
    nodes = set()
    for line in edges:
        edge = line.split()
        if len(edge) != 2 or '@' not in edge[1]:
            raise ValueError('Malformed shell fixture workspace graph')
        node = edge[1].split('@', 1)[0]
        if node not in {'go', 'toolchain', 'dockpipe', 'dorkpipe.orchestrator'}:
            nodes.add(edge[1])
        if len(nodes) > MAX_WORKSPACE_GRAPH_NODES:
            raise ValueError('Shell fixture workspace graph exceeds node capacity')
    if not nodes:
        raise ValueError('Shell fixture workspace graph has no external dependencies')
    return graph


def prefetch_shell_workspace_dependencies(source, go):
    environment = dict(os.environ, GOWORK='auto', GOTOOLCHAIN='local', GOENV='off',
                       GOFLAGS='-mod=readonly', GOPROXY='https://proxy.golang.org',
                       GOSUMDB='sum.golang.org', GOPRIVATE='', GONOPROXY='', GONOSUMDB='')
    online_graph = workspace_module_graph(source, go, environment, 900)
    subprocess.run([go, 'mod', 'download', 'all'], cwd=source, env=environment,
                   stdout=subprocess.DEVNULL, check=True, timeout=900)
    offline_environment = dict(environment, GOPROXY='off', GOSUMDB='off')
    offline_graph = workspace_module_graph(source, go, offline_environment, 60)
    if offline_graph != online_graph:
        raise ValueError('Shell fixture workspace graph changed before offline proof')
    subprocess.run([go, 'mod', 'download', 'all'], cwd=source, env=offline_environment,
                   stdout=subprocess.DEVNULL, check=True, timeout=60)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--dockpipe-bin', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    if args.receipt.exists() or args.receipt.is_symlink():
        parser.error('Shell fixture receipt destination must be fresh')
    if not args.receipt.parent.is_dir() or any(parent.is_symlink() for parent in args.receipt.parents):
        parser.error('Shell fixture receipt requires an unlinked existing directory')
    root = Path(__file__).resolve().parents[1]
    os.environ['DOCKPIPE_BIN'] = str(args.dockpipe_bin.resolve())
    environment = shell_test_environment(args.dockpipe_bin.resolve())
    with tempfile.TemporaryDirectory(prefix='dorkpipe-shell-candidate-') as temporary:
        fixture = Path(temporary)
        source = prepare_fixture(root, args.manifest, args.archive, fixture)
        prefetch_shell_workspace_dependencies(source, os.environ.get('GO_EXECUTABLE', 'go'))
        result = subprocess.run(['bash', 'packages/dorkpipe/tests/run.sh'], cwd=source,
                                env=environment, timeout=900)
        receipt = json.loads((fixture / 'shell-fixture.json').read_text())
        receipt['shell_test_exit_code'] = result.returncode
        args.receipt.write_text(json.dumps(receipt, indent=2) + '\n')
        print(f'Shell fixture receipt: {args.receipt}', flush=True)
        result.check_returncode()


if __name__ == '__main__':
    main()
