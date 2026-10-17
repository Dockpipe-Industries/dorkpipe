#!/usr/bin/env python3
"""Freeze one validated DorkPipe package store and its qualified editor VSIXs."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile

import candidate_contract
from validate_package_store import validate


MAX_FILE_BYTES = 128 << 20
MAX_TOTAL_BYTES = 512 << 20
MAX_EDITOR_MANIFEST_BYTES = 64 << 10
MAX_EDITOR_SOURCE_BYTES = 8 << 20
MAX_EDITOR_SOURCE_TOTAL_BYTES = 64 << 20
ARCHIVE_NAME = 'dorkpipe-packages-0.6.5-linux-amd64.tar.gz'
EDITOR_SOURCE_DIRECTORY = 'dockpipe-language-support'
EDITOR_SOURCE_FILES = (
    'LICENSE',
    'README.md',
    'extension.js',
    'extension.test.js',
    'images/icon.png',
    'language-configuration.json',
    'package-lock.json',
    'package.json',
    'snippets/pipelang.json',
    'syntaxes/pipelang.tmLanguage.json',
)


def read_regular(path, maximum):
    candidate_contract.regular_file(path, maximum)
    with path.open('rb') as stream:
        payload = stream.read(maximum + 1)
    if len(payload) > maximum:
        raise ValueError(f'File exceeds delivery capacity: {path}')
    return payload


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical_json(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode('utf-8')


def add_tar_member(archive, name, data):
    member = tarfile.TarInfo(name)
    member.size = len(data)
    member.mode = 0o644
    member.mtime = 0
    member.uid = 0
    member.gid = 0
    member.uname = ''
    member.gname = ''
    archive.addfile(member, io.BytesIO(data))


def build_editor_source_sdk(source_root, source_sha, output):
    editor_root = source_root / 'tooling/vscode-extensions' / EDITOR_SOURCE_DIRECTORY
    package = json.loads(read_regular(editor_root / 'package.json', MAX_EDITOR_MANIFEST_BYTES))
    version = package.get('version')
    if not isinstance(version, str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version):
        raise ValueError('Invalid language-support source version')

    source_files = []
    source_payloads = []
    total_bytes = 0
    for name in EDITOR_SOURCE_FILES:
        payload = read_regular(editor_root / name, MAX_EDITOR_SOURCE_BYTES)
        total_bytes += len(payload)
        if total_bytes > MAX_EDITOR_SOURCE_TOTAL_BYTES:
            raise ValueError('Language-support source SDK exceeds capacity')
        source_files.append({'path': name, 'bytes': len(payload), 'sha256': digest(payload)})
        source_payloads.append((name, payload))

    source_files.sort(key=lambda entry: entry['path'])
    source_digest = digest(json.dumps(source_files, sort_keys=True, separators=(',', ':')).encode())
    manifest = {
        'schema': 1,
        'editor_version': version,
        'source_dorkpipe_sha': source_sha,
        'source_digest': source_digest,
        'files': source_files,
    }
    members = source_payloads + [('editor-source.json', canonical_json(manifest))]
    name = f'dockpipe-language-test-sdk-{version}.tar.gz'
    archive_path = output / name
    with archive_path.open('wb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0, compresslevel=9) as compressed:
            with tarfile.open(fileobj=compressed, mode='w', format=tarfile.PAX_FORMAT) as archive:
                for member_name, payload in sorted(members, key=lambda item: item[0]):
                    add_tar_member(archive, f'{EDITOR_SOURCE_DIRECTORY}/{member_name}', payload)
    archive_payload = read_regular(archive_path, MAX_EDITOR_SOURCE_TOTAL_BYTES)
    return {'name': name, 'bytes': len(archive_payload), 'sha256': digest(archive_payload)}


def assemble(source_root, store, editors, source_sha, output):
    if not re.fullmatch(r'[0-9a-f]{40}', source_sha):
        raise ValueError('Source SHA must be an exact forty-character commit ID')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Delivery output must be empty')
    output.mkdir(parents=True, exist_ok=True)

    ownership_path = source_root / 'release/package-ownership.json'
    validated = validate(store, ownership_path)
    if validated['version'] != '0.6.5' or validated['archive_count'] != 26:
        raise ValueError('Unexpected package version or archive count')

    store_files = sorted(store.iterdir(), key=lambda path: path.name)
    if len(store_files) != 53:
        raise ValueError('Expected exactly twenty-six archives, sidecars and one manifest')
    total_bytes = 0
    package_payloads = []
    for path in store_files:
        payload = read_regular(path, MAX_FILE_BYTES)
        total_bytes += len(payload)
        if total_bytes > MAX_TOTAL_BYTES:
            raise ValueError('Package delivery exceeds total capacity')
        package_payloads.append((f'packages/{path.name}', payload))
    license_payload = read_regular(source_root / 'LICENSE', MAX_EDITOR_MANIFEST_BYTES)

    editor_manifest = json.loads(read_regular(editors / 'extensions.json', MAX_EDITOR_MANIFEST_BYTES))
    entries = editor_manifest.get('files')
    if editor_manifest.get('schema') != 1 or not isinstance(entries, list) or len(entries) != 2:
        raise ValueError('Expected exactly two qualified editor extensions')
    expected_names = set()
    for extension in ('dockpipe-language-support', 'pipeon'):
        package = json.loads(read_regular(
            source_root / f'tooling/vscode-extensions/{extension}/package.json',
            MAX_EDITOR_MANIFEST_BYTES,
        ))
        expected_names.add(f"{extension}-{package['version']}.vsix")
    if {entry.get('path') for entry in entries if isinstance(entry, dict)} != expected_names:
        raise ValueError('Editor inventory differs from source versions')
    if {path.name for path in editors.iterdir()} != expected_names | {'extensions.json'}:
        raise ValueError('Editor output contains an unexpected file')

    release_files = []
    for entry in sorted(entries, key=lambda item: item['path']):
        filename = entry['path']
        payload = read_regular(editors / filename, MAX_FILE_BYTES)
        if type(entry.get('bytes')) is not int or len(payload) != entry['bytes'] or digest(payload) != entry.get('sha256'):
            raise ValueError(f'Editor extension checksum differs from receipt: {filename}')
        total_bytes += len(payload)
        if total_bytes > MAX_TOTAL_BYTES:
            raise ValueError('Release delivery exceeds total capacity')
        destination = output / filename
        destination.write_bytes(payload)
        release_files.append({'name': filename, 'bytes': len(payload), 'sha256': digest(payload)})

    archive_path = output / ARCHIVE_NAME
    with archive_path.open('wb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0, compresslevel=9) as compressed:
            with tarfile.open(fileobj=compressed, mode='w', format=tarfile.PAX_FORMAT) as archive:
                for name, payload in package_payloads:
                    add_tar_member(archive, name, payload)
                add_tar_member(archive, 'LICENSE', license_payload)
    archive_payload = read_regular(archive_path, MAX_TOTAL_BYTES)
    release_files.append({'name': ARCHIVE_NAME, 'bytes': len(archive_payload), 'sha256': digest(archive_payload)})
    release_files.append(build_editor_source_sdk(source_root, source_sha, output))

    provenance = {
        'schema': 1,
        'source_repository': 'Dockpipe-Industries/dorkpipe',
        'source_sha': source_sha,
        'version': validated['version'],
        'platform': 'linux-amd64',
        'package_count': validated['archive_count'],
        'package_ownership_sha256': digest(read_regular(ownership_path, MAX_EDITOR_MANIFEST_BYTES)),
        'dependency_lock_sha256': digest(read_regular(source_root / 'release/dependencies.lock.json', MAX_EDITOR_MANIFEST_BYTES)),
        'sdk_source_lock_sha256': digest(read_regular(source_root / 'release/sdk-source.lock.json', MAX_EDITOR_MANIFEST_BYTES)),
        'toolchain_lock_sha256': digest(read_regular(source_root / 'release/toolchains.lock.json', MAX_EDITOR_MANIFEST_BYTES)),
        'files': sorted(release_files, key=lambda entry: entry['name']),
    }
    provenance_path = output / 'delivery-provenance.json'
    provenance_path.write_bytes(canonical_json(provenance))
    release_files.append({'name': provenance_path.name, 'bytes': provenance_path.stat().st_size,
                          'sha256': digest(provenance_path.read_bytes())})
    sums = ''.join(f"{entry['sha256']}  {entry['name']}\n" for entry in sorted(release_files, key=lambda item: item['name']))
    (output / 'SHA256SUMS').write_text(sums)
    print(f'Frozen {validated["archive_count"]} packages, two editors and source SDK for {source_sha}: {output}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--store', type=Path, required=True)
    parser.add_argument('--editors', type=Path, required=True)
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assemble(args.source_root, args.store, args.editors, args.source_sha, args.output)


if __name__ == '__main__':
    main()
