#!/usr/bin/env python3
"""Publish an exact, retry-safe public staging release with gh CLI authentication."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

import candidate_contract


REPOSITORY = 'Dockpipe-Industries/dorkpipe'
PACKAGE_ASSET = 'dorkpipe-packages-0.6.5-linux-amd64.tar.gz'
MAX_ASSET_BYTES = 512 << 20
MAX_PROVENANCE_BYTES = 1 << 20
MAX_CHECKSUM_BYTES = 64 << 10
GH_TIMEOUT_SECONDS = 120


def gh(*arguments, check=True):
    try:
        result = subprocess.run(
            ['gh', *arguments], text=True, capture_output=True, check=False,
            timeout=GH_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise ValueError('GitHub release operation exceeded its time limit') from error
    if check and result.returncode:
        raise ValueError(f'gh command failed: {" ".join(arguments[:3])}: {result.stderr.strip()}')
    return result


def file_digest(path):
    candidate_contract.regular_file(path, MAX_ASSET_BYTES)
    hasher = hashlib.sha256()
    total = 0
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            total += len(block)
            if total > MAX_ASSET_BYTES:
                raise ValueError(f'Release asset exceeds capacity: {path}')
            hasher.update(block)
    return hasher.hexdigest()


def read_metadata(path, maximum):
    candidate_contract.regular_file(path, maximum)
    with path.open('rb') as stream:
        payload = stream.read(maximum + 1)
    if len(payload) > maximum:
        raise ValueError(f'Release metadata exceeds capacity: {path}')
    return payload


def editor_asset_names():
    source_root = Path(__file__).resolve().parents[1]
    names = set()
    for extension in ('dockpipe-language-support', 'pipeon'):
        manifest_path = source_root / f'tooling/vscode-extensions/{extension}/package.json'
        manifest = json.loads(read_metadata(manifest_path, MAX_CHECKSUM_BYTES))
        version = manifest.get('version')
        if not isinstance(version, str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version):
            raise ValueError(f'Invalid editor source version: {extension}')
        names.add(f'{extension}-{version}.vsix')
    return names


def editor_source_asset_name():
    source_root = Path(__file__).resolve().parents[1]
    manifest_path = source_root / 'tooling/vscode-extensions/dockpipe-language-support/package.json'
    manifest = json.loads(read_metadata(manifest_path, MAX_CHECKSUM_BYTES))
    version = manifest.get('version')
    if not isinstance(version, str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version):
        raise ValueError('Invalid language-support source version')
    return f'dockpipe-language-test-sdk-{version}.tar.gz'


MAX_RELEASE_METADATA_BYTES = 2 << 20
MAX_RELEASE_PAGES = 5


def release_document(result):
    if len(result.stdout.encode('utf-8')) > MAX_RELEASE_METADATA_BYTES:
        raise ValueError('GitHub release metadata exceeds capacity')
    return json.loads(result.stdout)


def release_by_id(release_id):
    if type(release_id) is not int or release_id <= 0:
        raise ValueError('GitHub release ID is invalid')
    release = release_document(gh('api', f'repos/{REPOSITORY}/releases/{release_id}'))
    if not isinstance(release, dict) or release.get('id') != release_id:
        raise ValueError('GitHub release ID response differs from the created release')
    return release


def release_api(tag):
    result = gh('api', f'repos/{REPOSITORY}/releases/tags/{tag}', check=False)
    if not result.returncode:
        release = release_document(result)
        if not isinstance(release, dict):
            raise ValueError('GitHub release response is invalid')
        return release
    if 'HTTP 404' not in result.stderr:
        raise ValueError(f'Cannot inspect release: {result.stderr.strip()}')

    matches = []
    for page in range(1, MAX_RELEASE_PAGES + 1):
        result = gh('api', f'repos/{REPOSITORY}/releases?per_page=100&page={page}',
                    '--jq', '[.[] | {id,tag_name}]')
        releases = release_document(result)
        if not isinstance(releases, list) or len(releases) > 100:
            raise ValueError('GitHub release page is invalid')
        matches.extend(release for release in releases if isinstance(release, dict) and release.get('tag_name') == tag)
        if len(matches) > 1:
            raise ValueError('Multiple GitHub releases have the exact staging tag')
        if len(releases) < 100:
            return release_by_id(matches[0].get('id')) if matches else None
    raise ValueError('Release list page cap prevents proving the exact staging tag is unique or absent')


def verify_release_fields(release, tag, source_sha):
    if (release.get('tag_name') != tag or release.get('target_commitish') != source_sha
            or release.get('prerelease') is not True or release.get('make_latest') is True):
        raise ValueError('Existing release metadata differs from the frozen source')


def publish(delivery):
    if os.environ.get('GITHUB_REPOSITORY') != REPOSITORY or os.environ.get('GITHUB_REF') != 'refs/heads/staging':
        raise ValueError('Publication is restricted to the public repository staging branch')
    source_sha = os.environ.get('GITHUB_SHA', '')
    if not re.fullmatch(r'[0-9a-f]{40}', source_sha):
        raise ValueError('Publication requires an exact source commit')
    tag = f'v0.6.5-staging.{source_sha[:12]}'
    provenance_path = delivery / 'delivery-provenance.json'
    provenance = json.loads(read_metadata(provenance_path, MAX_PROVENANCE_BYTES))
    if (provenance.get('source_sha') != source_sha or provenance.get('source_repository') != REPOSITORY
            or provenance.get('version') != '0.6.5' or provenance.get('package_count') != 26):
        raise ValueError('Delivery provenance differs from release source')
    entries = provenance.get('files')
    exact_names = editor_asset_names() | {PACKAGE_ASSET, editor_source_asset_name()}
    if not isinstance(entries, list) or len(entries) != 4:
        raise ValueError('Delivery must contain two editors, one package archive and one source SDK')
    expected = {}
    expected_sizes = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {'name', 'bytes', 'sha256'}:
            raise ValueError('Invalid delivery provenance entry')
        name = entry['name']
        if (name not in exact_names or name in expected or type(entry['bytes']) is not int
                or entry['bytes'] < 0 or entry['bytes'] > MAX_ASSET_BYTES
                or not isinstance(entry['sha256'], str)
                or not re.fullmatch(r'[0-9a-f]{64}', entry['sha256'])):
            raise ValueError('Invalid or unowned delivery asset')
        expected[name] = entry['sha256']
        expected_sizes[name] = entry['bytes']
    if set(expected) != exact_names:
        raise ValueError('Delivery provenance differs from exact editor versions')
    expected['delivery-provenance.json'] = file_digest(provenance_path)
    sums_path = delivery / 'SHA256SUMS'
    sums_payload = read_metadata(sums_path, MAX_CHECKSUM_BYTES)
    expected['SHA256SUMS'] = hashlib.sha256(sums_payload).hexdigest()
    expected_sums = ''.join(f'{expected[name]}  {name}\n' for name in sorted(set(expected) - {'SHA256SUMS'}))
    if sums_payload != expected_sums.encode():
        raise ValueError('SHA256SUMS differs from frozen assets')
    if {path.name for path in delivery.iterdir()} != set(expected):
        raise ValueError('Delivery directory has missing or extra assets')
    for name, sha256 in expected.items():
        if name in expected_sizes and (delivery / name).stat().st_size != expected_sizes[name]:
            raise ValueError(f'Frozen release asset size differs from provenance: {name}')
        if file_digest(delivery / name) != sha256:
            raise ValueError(f'Frozen release asset differs from provenance: {name}')

    repository = gh('api', f'repos/{REPOSITORY}')
    candidate_contract.validate_public_repository(repository.stdout, REPOSITORY)
    release = release_api(tag)
    if release is None:
        body = {
            'tag_name': tag,
            'target_commitish': source_sha,
            'name': f'DorkPipe 0.6.5 staging ({source_sha[:12]})',
            'body': 'Frozen Linux amd64 package store, editor VSIX candidates and language test source SDK. Verify SHA256SUMS and delivery-provenance.json.',
            'draft': True,
            'prerelease': True,
            'make_latest': 'false',
        }
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json') as request:
            json.dump(body, request)
            request.flush()
            created = release_document(gh('api', '-X', 'POST', f'repos/{REPOSITORY}/releases', '--input', request.name))
        if not isinstance(created, dict):
            raise ValueError('Created GitHub release response is invalid')
        release = release_by_id(created.get('id'))
    verify_release_fields(release, tag, source_sha)
    remote_assets = {asset['name']: asset for asset in release.get('assets', [])}
    if set(remote_assets) - set(expected):
        raise ValueError('Release contains an unexpected asset')
    if not release.get('draft') and set(remote_assets) != set(expected):
        raise ValueError('Published release has missing assets and cannot be changed')

    with tempfile.TemporaryDirectory(prefix='dorkpipe-release-verify-') as temporary:
        temporary_path = Path(temporary)
        for name in sorted(remote_assets):
            gh('release', 'download', tag, '--repo', REPOSITORY, '--pattern', name, '--dir', temporary)
            if file_digest(temporary_path / name) != expected[name]:
                raise ValueError(f'Existing release asset differs; refusing to clobber: {name}')
    if release.get('draft'):
        for name in sorted(set(expected) - set(remote_assets)):
            gh('release', 'upload', tag, str(delivery / name), '--repo', REPOSITORY)
        release = release_by_id(release['id'])
        verify_release_fields(release, tag, source_sha)
        if {asset['name'] for asset in release.get('assets', [])} != set(expected):
            raise ValueError('Release upload did not produce the exact asset inventory')
        with tempfile.TemporaryDirectory(prefix='dorkpipe-release-final-') as temporary:
            temporary_path = Path(temporary)
            for name in sorted(expected):
                gh('release', 'download', tag, '--repo', REPOSITORY, '--pattern', name, '--dir', temporary)
                if file_digest(temporary_path / name) != expected[name]:
                    raise ValueError(f'Uploaded release asset differs: {name}')
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json') as request:
            json.dump({'draft': False, 'prerelease': True, 'make_latest': 'false'}, request)
            request.flush()
            gh('api', '-X', 'PATCH', f'repos/{REPOSITORY}/releases/{release["id"]}', '--input', request.name)
    print(f'Qualified immutable staging release: {tag}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--delivery', type=Path, required=True)
    args = parser.parse_args()
    publish(args.delivery)


if __name__ == '__main__':
    main()
