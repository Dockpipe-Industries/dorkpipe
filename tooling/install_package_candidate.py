#!/usr/bin/env python3
"""Verify local prepared package tools before copying hook-owned outputs.

This receipt describes a trusted local preparation. It is not authenticated
external publisher evidence and cannot authorize a download or shared feed write.
"""
import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

import candidate_contract as contract
import go_candidate


def require_unlinked_path(path):
    for component in (path, *path.parents):
        if component.is_symlink():
            raise ValueError('Linked preparation or output path')


def verify_candidate(root):
    contract.require_target()
    directory = contract.prepared_directory(root)
    require_unlinked_path(directory)
    receipt = contract.read_json(directory / 'candidate.json', contract.MAX_RECEIPT_BYTES)
    if not isinstance(receipt, dict) or type(receipt.get('schema')) is not int or receipt['schema'] != 1:
        raise ValueError('Unsupported prepared candidate receipt')
    if receipt.get('target') != {'os': 'linux', 'arch': 'amd64'}:
        raise ValueError('Prepared candidate target mismatch')
    if receipt.get('tests_requested') is not True or receipt.get('distribution_approved') is not False:
        raise ValueError('Prepared package candidate must request tests and retain its distribution gate')
    lock = contract.read_json(root / 'release/dependencies.lock.json', go_candidate.MAX_LOCK_BYTES)
    if receipt.get('sdk_lock') != lock:
        raise ValueError('Prepared candidate SDK lock drift')
    sdk = lock['dockpipe_go_sdk']
    manifest_identity = {
        'sdk_version': sdk['version'], 'source_commit': sdk['source_commit'],
        'source_digest': sdk['source_digest'], 'sha256': sdk['archive_sha256'],
    }
    go_candidate.validate_sdk_pin(root, manifest_identity, receipt.get('sdk_manifest_sha256'))
    if receipt.get('sdk_source_digest') != sdk['source_digest']:
        raise ValueError('Prepared candidate SDK identity drift')
    if receipt.get('source') != contract.source_identity(root):
        raise ValueError('Prepared candidate package source or version drift')
    entries = contract.validate_binaries(directory / 'bin', receipt.get('binaries'))
    return directory / 'bin', entries


def verify_engine_archive(root, archive, destination):
    """Extract only a source-locked released CLI; never execute or download it."""
    helper = root / '.github/scripts/bootstrap-dockpipe.py'
    require_unlinked_path(helper)
    spec = importlib.util.spec_from_file_location('locked_engine_bootstrap', helper)
    bootstrap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bootstrap)
    lock = bootstrap.load_lock(root / 'release/toolchains.lock.json')
    require_unlinked_path(archive)
    _, digest = contract.file_digest(archive, bootstrap.MAX_ARCHIVE_BYTES)
    if digest != lock['sha256']:
        raise ValueError('Released engine archive does not match the committed source lock')
    bootstrap.extract_executable(archive, destination)


def copy_verified_binary(source, destination, entry):
    contract.regular_file(source, contract.MAX_BINARY_BYTES)
    digest = hashlib.sha256()
    remaining = entry['bytes']
    with source.open('rb') as input_stream, destination.open('xb') as output_stream:
        while remaining:
            block = input_stream.read(min(1 << 20, remaining))
            if not block:
                raise ValueError('Prepared tool was truncated while copying')
            remaining -= len(block)
            digest.update(block)
            output_stream.write(block)
        if input_stream.read(1) or digest.hexdigest() != entry['sha256']:
            raise ValueError('Prepared tool changed while copying')
    destination.chmod(0o755)


def install(root, output, operation, engine_archive=None):
    binaries, entries = verify_candidate(root)
    output = output.absolute()
    require_unlinked_path(output)
    selected = contract.TOOLS
    if operation == 'source-dorkpipe':
        selected = tuple(name for name in contract.TOOLS if name != 'mcpd')
    elif operation == 'source-mcp':
        selected = ('mcpd',)
    elif operation != 'consumer':
        raise ValueError('Unknown package installation operation')
    if operation == 'consumer' and engine_archive is None:
        raise ValueError('Consumer compilation requires an explicit local released engine archive')

    # Validate and stage every input before creating or replacing hook outputs.
    with tempfile.TemporaryDirectory(prefix='dorkpipe-verified-tools-') as temporary:
        staged = Path(temporary)
        for name in selected:
            copy_verified_binary(binaries / name, staged / name, entries[name])
        if operation == 'consumer':
            verify_engine_archive(root, engine_archive, staged / 'dockpipe')
        names = sorted(path.name for path in staged.iterdir())
        for name in names:
            if (output / name).is_symlink():
                raise ValueError('Linked existing tool output')
        output.mkdir(parents=True, exist_ok=True)
        for name in names:
            # Atomic replacement per owned tool, retaining unrelated source tools.
            descriptor, local_name = tempfile.mkstemp(prefix=f'.{name}.', dir=output)
            os.close(descriptor)
            local = Path(local_name)
            try:
                shutil.copyfile(staged / name, local)
                local.chmod(0o755)
                local.replace(output / name)
            finally:
                local.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operation', choices=['source-dorkpipe', 'source-mcp', 'consumer'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--engine-archive', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        install(root, args.output, args.operation, args.engine_archive)
    except (OSError, EOFError, ValueError, TypeError, KeyError, RecursionError, tarfile.TarError, subprocess.SubprocessError) as error:
        parser.exit(1, f'Prepared package installation failed: {error}\n')


if __name__ == '__main__':
    main()
