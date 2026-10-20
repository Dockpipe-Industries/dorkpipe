#!/usr/bin/env python3
"""Validate the exact DorkPipe-owned compiled resolver/workflow store."""
import argparse
import gzip
import hashlib
from pathlib import Path, PurePosixPath
import re
import tarfile

import candidate_contract


MAX_JSON_BYTES = 1 << 20
MAX_ARCHIVE_BYTES = 128 << 20
MAX_EXPANDED_BYTES = 256 << 20
MAX_MEMBERS = 20000
MAX_PACKAGE_MANIFEST_BYTES = 64 << 10


def load_ownership(path):
    ownership = candidate_contract.read_json(path, MAX_JSON_BYTES)
    required = {'schema', 'version', 'namespace', 'resolvers', 'workflows', 'min_dockpipe_version', 'license_sha256'}
    if (not isinstance(ownership, dict) or set(ownership) != required
            or type(ownership['schema']) is not int or ownership['schema'] != 1):
        raise ValueError('Unsupported package ownership descriptor')
    if not isinstance(ownership['version'], str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', ownership['version']) or ownership['namespace'] != 'dockpipeproject':
        raise ValueError('DorkPipe ownership requires the qualified version and namespace')
    if not isinstance(ownership['min_dockpipe_version'], str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', ownership['min_dockpipe_version']):
        raise ValueError('Ownership requires an exact minimum engine version')
    if not isinstance(ownership['license_sha256'], str) or not re.fullmatch(r'[0-9a-f]{64}', ownership['license_sha256']):
        raise ValueError('Ownership requires the inherited license digest')
    for section in ['resolvers', 'workflows']:
        names = ownership[section]
        if not isinstance(names, list) or len(names) != (8 if section == 'resolvers' else 18):
            raise ValueError('DorkPipe ownership requires eight resolver and eighteen workflow identities')
        if (any(not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9.-]*', name) for name in names)
                or len(set(names)) != len(names)):
            raise ValueError('DorkPipe ownership requires unique identities per package kind')
    if not set(ownership['resolvers']).issubset(ownership['workflows']):
        raise ValueError('Every resolver must retain its public workflow alias')
    return ownership


class ExpansionBudget:
    def __init__(self, source):
        self.source = source
        self.remaining = MAX_EXPANDED_BYTES

    def read(self, size):
        if size < 0 or size > self.remaining:
            raise ValueError('Package archive exceeds expanded capacity')
        block = self.source.read(size)
        self.remaining -= len(block)
        return block


def manifest_scalar(text, field, optional=False):
    # Read only the required canonical top-level scalar fields. This deliberately
    # rejects ambiguous/complex YAML instead of accepting another manifest shape.
    matches = re.findall(r'^' + re.escape(field) + r':\s*([^\r\n]+)$', text, re.MULTILINE)
    if not matches and optional:
        return None
    if len(matches) != 1:
        raise ValueError(f'Package manifest requires exactly one {field} scalar')
    value = matches[0].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', value):
        raise ValueError(f'Package manifest {field} is not a canonical scalar')
    return value


def validate_archive(path, section, name, ownership):
    prefix = f'{section}/{name}'
    manifest_name = prefix + '/package.yml'
    manifest = None
    config = None
    license_digest = None
    seen = set()
    declared_bytes = 0
    with gzip.open(path, 'rb') as compressed:
        with tarfile.open(fileobj=ExpansionBudget(compressed), mode='r|') as archive:
            for member in archive:
                if len(seen) >= MAX_MEMBERS:
                    raise ValueError('Package archive exceeds member capacity')
                canonical = member.name.rstrip('/') if member.isdir() else member.name
                parsed = PurePosixPath(canonical)
                if canonical != parsed.as_posix() or parsed.is_absolute() or '..' in parsed.parts or '\\' in canonical or ':' in canonical or canonical in seen:
                    raise ValueError('Package archive contains an unsafe or duplicate member')
                if canonical != prefix and not canonical.startswith(prefix + '/'):
                    raise ValueError('Package archive contains an unowned root')
                if not member.isfile() and not member.isdir():
                    raise ValueError('Package archive contains a non-regular member')
                seen.add(canonical)
                declared_bytes += member.size
                if declared_bytes > MAX_EXPANDED_BYTES:
                    raise ValueError('Package archive exceeds source capacity')
                if canonical in {manifest_name, prefix + '/config.yml', prefix + '/LICENSE'}:
                    if not member.isfile() or member.size > MAX_PACKAGE_MANIFEST_BYTES:
                        raise ValueError('Package manifest is not a bounded regular file')
                    stream = archive.extractfile(member)
                    with stream:
                        payload = stream.read(MAX_PACKAGE_MANIFEST_BYTES + 1)
                    if canonical == prefix + '/LICENSE':
                        license_digest = hashlib.sha256(payload).hexdigest()
                        continue
                    text = payload.decode('utf-8')
                    if canonical == manifest_name:
                        manifest = text
                    else:
                        config = text
    if manifest is None:
        raise ValueError('Package archive is missing its owned manifest')
    if license_digest != ownership['license_sha256']:
        raise ValueError('Package archive is missing or changed its inherited license')
    expected = {'name': name, 'kind': section[:-1], 'version': ownership['version'],
                'license': 'Apache-2.0', 'min_dockpipe_version': ownership['min_dockpipe_version']}
    for field, value in expected.items():
        if manifest_scalar(manifest, field) != value:
            raise ValueError(f'Package archive {name} has unexpected {field}')
    namespaces = [manifest_scalar(manifest, 'namespace', optional=True)]
    if section == 'workflows':
        if config is None or manifest_scalar(config, 'name') != name:
            raise ValueError('Workflow config does not declare its owned name')
        namespaces.append(manifest_scalar(config, 'namespace', optional=True))
    declared_namespaces = [namespace for namespace in namespaces if namespace is not None]
    if not declared_namespaces or any(namespace != ownership['namespace'] for namespace in declared_namespaces):
        raise ValueError('Package archive namespace is missing or differs from its owned namespace')


def validate(store, ownership_path):
    ownership = load_ownership(ownership_path)
    manifest_path = store / 'packages-store-manifest.json'
    manifest = candidate_contract.read_json(manifest_path, MAX_JSON_BYTES)
    if not isinstance(manifest, dict) or type(manifest.get('schema')) is not int or manifest['schema'] != 1 or manifest.get('platform') != 'linux-amd64':
        raise ValueError('Package store must be a Linux amd64 schema 1 manifest')
    packages = manifest.get('packages')
    if not isinstance(packages, dict) or set(packages) != {'resolvers', 'workflows'}:
        raise ValueError('Package store must contain only resolver and workflow leaves; core is forbidden')
    expected_files = {'packages-store-manifest.json'}
    for section in ['resolvers', 'workflows']:
        entries = packages[section]
        if not isinstance(entries, list) or len(entries) != len(ownership[section]):
            raise ValueError(f'Package store has an unexpected {section} count')
        names = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError('Package store entry is not an object')
            name = entry.get('name')
            if name not in ownership[section] or name in names or entry.get('version') != ownership['version']:
                raise ValueError('Package store contains an unowned, duplicate or incorrectly versioned identity')
            if entry.get('min_dockpipe_version') != ownership['min_dockpipe_version']:
                raise ValueError('Package catalog minimum engine version differs from ownership')
            names.append(name)
            filename = f"dockpipe-{section[:-1]}-{name}-{ownership['version']}.tar.gz"
            if entry.get('tarball') != filename:
                raise ValueError('Package store archive name differs from its owned identity')
            path = store / filename
            size, digest = candidate_contract.file_digest(path, MAX_ARCHIVE_BYTES)
            if type(entry.get('size_bytes')) is not int or entry['size_bytes'] != size or entry.get('sha256') != digest:
                raise ValueError('Package store archive size or checksum mismatch')
            checksum = store / (filename + '.sha256')
            candidate_contract.regular_file(checksum, 1024)
            if checksum.read_text().strip() != digest:
                raise ValueError('Package store checksum sidecar mismatch')
            validate_archive(path, section, name, ownership)
            expected_files.update({filename, filename + '.sha256'})
        if set(names) != set(ownership[section]):
            raise ValueError('Package store is missing an owned identity')
    if {path.name for path in store.iterdir()} != expected_files:
        raise ValueError('Package store contains extra or missing files')
    return {'schema': 1, 'version': ownership['version'], 'resolvers': sorted(ownership['resolvers']),
            'workflows': sorted(ownership['workflows']), 'archive_count': 26}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', type=Path, required=True)
    parser.add_argument('--ownership', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = validate(args.store, args.ownership)
    except (OSError, ValueError, UnicodeError, tarfile.TarError) as error:
        parser.exit(1, f'DorkPipe package store validation failed: {error}\n')
    print(f"DorkPipe store passed: 8 resolvers, 18 workflows, version {result['version']}; no core or maintainer workflows.")


if __name__ == '__main__':
    main()
