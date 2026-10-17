#!/usr/bin/env python3
"""Validate one frozen public release and publish its exact assets to R2."""
import argparse
import gzip
import hashlib
import json
import mimetypes
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
import tempfile
from urllib.parse import urlsplit

import candidate_contract

PRODUCT = 'dorkpipe'
REPOSITORY = 'Dockpipe-Industries/dorkpipe'
VERSION = '0.6.5'
PACKAGE_COUNT = 26
REQUIRED_ASSETS = {'delivery-provenance.json', 'dockpipe-language-test-sdk-0.0.2.tar.gz', 'pipeon-0.0.7.vsix', 'dockpipe-language-support-0.0.2.vsix', 'dorkpipe-packages-0.6.5-linux-amd64.tar.gz', 'SHA256SUMS'}
MAX_ASSETS = 6
MAX_ASSET_BYTES = 512 << 20
MAX_TOTAL_BYTES = 768 << 20
MAX_METADATA_BYTES = 2 << 20
COMMAND_TIMEOUT = 300
MAX_STORE_ENTRY_BYTES = 128 << 20
MAX_STORE_BYTES = 512 << 20


def run(arguments, *, environment=None, allow_failure=False):
    try:
        with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
            completed = subprocess.run(arguments, env=environment, stdout=output,
                                       stderr=errors, timeout=COMMAND_TIMEOUT, check=False)
            output.seek(0)
            errors.seek(0)
            stdout = output.read(MAX_METADATA_BYTES + 1)
            stderr = errors.read(MAX_METADATA_BYTES + 1)
    except subprocess.TimeoutExpired as error:
        raise ValueError('Package-host operation timed out') from error
    if len(stdout) > MAX_METADATA_BYTES or len(stderr) > MAX_METADATA_BYTES:
        raise ValueError('Package-host response exceeds capacity')
    result = subprocess.CompletedProcess(arguments, completed.returncode,
                                         stdout.decode('utf-8'), stderr.decode('utf-8'))
    if result.returncode and not allow_failure:
        raise ValueError(f'Package-host command failed: {arguments[0]} {arguments[1]}')
    return result


def read_regular(path, maximum):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise ValueError(f'Frozen asset is not a bounded regular file: {path.name}')
    with path.open('rb') as stream:
        payload = stream.read(maximum + 1)
    if len(payload) > maximum:
        raise ValueError(f'Frozen asset exceeds capacity: {path.name}')
    return payload


def digest(path, maximum=MAX_ASSET_BYTES):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise ValueError(f'Frozen asset is not a bounded regular file: {path.name}')
    hasher = hashlib.sha256()
    total = 0
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            total += len(block)
            if total > maximum:
                raise ValueError(f'Frozen asset exceeds capacity: {path.name}')
            hasher.update(block)
    return hasher.hexdigest()


def source_lock(root):
    lock = json.loads(read_regular(root / 'release/package-host-source.lock.json', 64 << 10))
    source_sha = lock.get('source_sha')
    tag = lock.get('release_tag')
    if (lock.get('schema') != 1 or lock.get('product') != PRODUCT
            or lock.get('source_repository') != REPOSITORY
            or lock.get('version') != VERSION or lock.get('package_count') != PACKAGE_COUNT
            or not isinstance(source_sha, str) or not re.fullmatch(r'[0-9a-f]{40}', source_sha)
            or tag != f'v{VERSION}-staging.{source_sha[:12]}'):
        raise ValueError('Package-host source lock has an invalid release identity')
    assets = lock.get('assets')
    if not isinstance(assets, list) or len(assets) != len(REQUIRED_ASSETS) or len(assets) > MAX_ASSETS:
        raise ValueError('Package-host asset count differs from product contract')
    names = []
    for asset in assets:
        if (not isinstance(asset, dict) or set(asset) != {'name', 'bytes', 'sha256'}
                or asset.get('name') not in REQUIRED_ASSETS
                or type(asset.get('bytes')) is not int or not 0 < asset['bytes'] <= MAX_ASSET_BYTES
                or not isinstance(asset.get('sha256'), str)
                or not re.fullmatch(r'[0-9a-f]{64}', asset['sha256'])):
            raise ValueError('Package-host asset lock is invalid')
        names.append(asset['name'])
    if sum(asset['bytes'] for asset in assets) > MAX_TOTAL_BYTES:
        raise ValueError('Package-host asset inventory exceeds total capacity')
    if names != sorted(REQUIRED_ASSETS):
        raise ValueError('Package-host asset names must be exact and sorted')
    return lock


def verify_release(lock):
    repository = run(['gh', 'api', f'repos/{REPOSITORY}'])
    candidate_contract.validate_public_repository(repository.stdout, REPOSITORY)
    tag = lock['release_tag']
    release = json.loads(run(['gh', 'api', f'repos/{REPOSITORY}/releases/tags/{tag}']).stdout)
    if (release.get('tag_name') != tag or release.get('target_commitish') != lock['source_sha']
            or release.get('draft') is not False or release.get('prerelease') is not True):
        raise ValueError('Public frozen release differs from source lock')
    actual = release.get('assets')
    if not isinstance(actual, list) or len(actual) != len(lock['assets']):
        raise ValueError('Public frozen release has a different asset count')
    expected = {asset['name']: asset for asset in lock['assets']}
    if {asset.get('name') for asset in actual if isinstance(asset, dict)} != set(expected):
        raise ValueError('Public frozen release has a different asset inventory')
    for asset in actual:
        pinned = expected[asset['name']]
        if (asset.get('size') != pinned['bytes']
                or asset.get('digest') != f"sha256:{pinned['sha256']}"):
            raise ValueError(f"Public frozen release asset differs: {asset['name']}")


def validate_payload(lock, directory):
    expected = {asset['name']: asset for asset in lock['assets']}
    if {path.name for path in directory.iterdir()} != set(expected):
        raise ValueError('Frozen asset directory inventory differs')
    for name, asset in expected.items():
        path = directory / name
        if path.stat().st_size != asset['bytes'] or digest(path) != asset['sha256']:
            raise ValueError(f'Frozen asset differs from source lock: {name}')
    checksums = {}
    for line in read_regular(directory / 'SHA256SUMS', 64 << 10).decode().splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  ([A-Za-z0-9_.-]+)', line)
        if match is None or match.group(2) in checksums:
            raise ValueError('Frozen checksum file is malformed')
        checksums[match.group(2)] = match.group(1)
    if checksums != {name: asset['sha256'] for name, asset in expected.items() if name != 'SHA256SUMS'}:
        raise ValueError('Frozen checksums differ from source lock')
    provenance = json.loads(read_regular(directory / 'delivery-provenance.json', 1 << 20))
    if (provenance.get('source_repository') != REPOSITORY
            or provenance.get('source_sha') != lock['source_sha']
            or provenance.get('version') != VERSION
            or provenance.get('package_count') != PACKAGE_COUNT
            or provenance.get('platform') != 'linux-amd64'):
        raise ValueError('Frozen provenance differs from source lock')
    files = provenance.get('files')
    payloads = set(expected) - {'SHA256SUMS', 'delivery-provenance.json'}
    if not isinstance(files, list) or len(files) != len(payloads):
        raise ValueError('Frozen provenance payload count differs')
    if {item.get('name') for item in files if isinstance(item, dict)} != payloads:
        raise ValueError('Frozen provenance payload inventory differs')
    for item in files:
        asset = expected[item['name']]
        if item.get('bytes') != asset['bytes'] or item.get('sha256') != asset['sha256']:
            raise ValueError('Frozen provenance payload differs from source lock')


def delivery_lock(directory, source_sha):
    if not isinstance(source_sha, str) or not re.fullmatch(r'[0-9a-f]{40}', source_sha):
        raise ValueError('Delivery requires an exact producer commit')
    if {path.name for path in directory.iterdir()} != REQUIRED_ASSETS:
        raise ValueError('Delivery has missing or unexpected assets')
    assets = []
    for name in sorted(REQUIRED_ASSETS):
        path = directory / name
        assets.append({'name': name, 'bytes': path.stat().st_size, 'sha256': digest(path)})
    if sum(asset['bytes'] for asset in assets) > MAX_TOTAL_BYTES:
        raise ValueError('Candidate delivery exceeds total capacity')
    lock = {'schema': 1, 'product': PRODUCT, 'source_repository': REPOSITORY,
            'source_sha': source_sha, 'release_tag': f'v{VERSION}-staging.{source_sha[:12]}',
            'version': VERSION, 'package_count': PACKAGE_COUNT, 'assets': assets}
    validate_payload(lock, directory)
    return lock


def download_and_validate(lock, directory):
    for asset in lock['assets']:
        run(['gh', 'release', 'download', lock['release_tag'], '--repo', REPOSITORY,
             '--pattern', asset['name'], '--dir', str(directory)])
    validate_payload(lock, directory)


def bundle_name():
    return f'{PRODUCT}-packages-{VERSION}-linux-amd64.tar.gz'


def unpack_store(bundle, directory):
    """Extract only the bounded flat package store carried by the frozen bundle."""
    store = directory / 'store'
    store.mkdir()
    expected_count = PACKAGE_COUNT * 2 + 2
    names = set()
    total = 0
    with tarfile.open(bundle, 'r|gz') as archive:
        for member in archive:
            if len(names) >= expected_count or not member.isfile():
                raise ValueError('Frozen package bundle has extra or non-file entries')
            name = member.name
            if name != 'LICENSE':
                if (not name.startswith('packages/') or name.count('/') != 1
                        or name[9:] in {'.', '..'}
                        or not re.fullmatch(r'[A-Za-z0-9_.-]+', name[9:])):
                    raise ValueError('Frozen package bundle has an unsafe path')
            if name in names or member.size < 0 or member.size > MAX_STORE_ENTRY_BYTES:
                raise ValueError('Frozen package bundle entry is duplicate or oversized')
            total += member.size
            if total > MAX_STORE_BYTES:
                raise ValueError('Frozen package bundle exceeds store capacity')
            names.add(name)
            destination = directory / ('LICENSE' if name == 'LICENSE' else f'store/{name[9:]}')
            source = archive.extractfile(member)
            if source is None:
                raise ValueError('Frozen package bundle entry cannot be read')
            remaining = member.size
            with destination.open('xb') as output:
                while remaining:
                    block = source.read(min(1 << 20, remaining))
                    if not block:
                        raise ValueError('Frozen package bundle entry is truncated')
                    output.write(block)
                    remaining -= len(block)
    if len(names) != expected_count or 'LICENSE' not in names or 'packages/packages-store-manifest.json' not in names:
        raise ValueError('Frozen package bundle is incomplete')
    return store


def verify_store(root, store):
    validator = root / 'tooling/validate_package_store.py'
    ownership = root / 'release/package-ownership.json'
    result = run([sys.executable, '-B', str(validator), '--store', str(store),
                  '--ownership', str(ownership)])
    if 'passed' not in result.stdout:
        raise ValueError('Frozen package store validation did not pass')
    manifest = json.loads(read_regular(store / 'packages-store-manifest.json', 1 << 20))
    entries = manifest['packages']['resolvers'] + manifest['packages']['workflows']
    if len(entries) != PACKAGE_COUNT:
        raise ValueError('Frozen package store has an unexpected package count')
    return manifest


def verify_seed(root, seed_path):
    pin = json.loads(read_regular(root / 'release/dependencies.lock.json', 64 << 10))['dorkpipe_resolver']
    source = json.loads(read_regular(root / 'release/dependency-source.lock.json', 64 << 10))
    entry = json.loads(read_regular(root / 'release/package-host-dependency.lock.json', 64 << 10))
    pinned = entry.get('resolver')
    if (entry.get('schema') != 1 or source.get('repository') != REPOSITORY
            or source.get('tag') != f"dorkpipe-inputs-0.6.3.{source.get('source_dorkpipe_sha', '')[:12]}"
            or not re.fullmatch(r'[0-9a-f]{40}', source.get('source_dorkpipe_sha', ''))
            or entry.get('source_dorkpipe_sha') != source['source_dorkpipe_sha']
            or entry.get('seed_release_tag') != source['tag']
            or not isinstance(pinned, dict)
            or pin.get('kind') != 'resolver'
            or {key: pinned.get(key) for key in pin if key != 'kind'} != {key: value for key, value in pin.items() if key != 'kind'}
            or pinned.get('name') != 'dorkpipe' or pinned.get('version') != '0.6.3'):
        raise ValueError('Pipeon resolver seed differs from committed dependency pins')
    if seed_path.name != pin['tarball'] or seed_path.stat().st_size != pin['size_bytes'] or digest(seed_path) != pin['sha256']:
        raise ValueError('Pipeon resolver seed bytes differ from committed dependency pin')
    from validate_package_store import ExpansionBudget, manifest_scalar
    ownership = json.loads(read_regular(root / 'release/package-ownership.json', 64 << 10))
    prefix = 'resolvers/dorkpipe'
    seen = set()
    package_manifest = None
    license_digest = None
    with gzip.open(seed_path, 'rb') as compressed:
        with tarfile.open(fileobj=ExpansionBudget(compressed), mode='r|') as archive:
            for member in archive:
                canonical = member.name.rstrip('/') if member.isdir() else member.name
                parsed = PurePosixPath(canonical)
                if (len(seen) >= 20000 or canonical != parsed.as_posix()
                        or parsed.is_absolute() or '..' in parsed.parts or '\\' in canonical
                        or ':' in canonical or canonical in seen
                        or (canonical != prefix and not canonical.startswith(prefix + '/'))
                        or not (member.isfile() or member.isdir())):
                    raise ValueError('Pipeon resolver seed contains an unsafe member')
                seen.add(canonical)
                if canonical in {prefix + '/package.yml', prefix + '/LICENSE'}:
                    if not member.isfile() or member.size > 64 << 10:
                        raise ValueError('Pipeon resolver seed manifest exceeds capacity')
                    payload = archive.extractfile(member).read((64 << 10) + 1)
                    if canonical.endswith('/package.yml'):
                        package_manifest = payload.decode()
                    else:
                        license_digest = hashlib.sha256(payload).hexdigest()
    if package_manifest is None or license_digest != ownership['license_sha256']:
        raise ValueError('Pipeon resolver seed has incorrect package manifest or license')
    expected = {'name': 'dorkpipe', 'kind': 'resolver', 'version': '0.6.3',
                'namespace': 'dockpipeproject', 'license': 'Apache-2.0',
                'min_dockpipe_version': pinned['min_dockpipe_version']}
    if any(manifest_scalar(package_manifest, field) != value for field, value in expected.items()):
        raise ValueError('Pipeon resolver seed identity differs from pinned catalog')
    return entry, pinned


def acquire_seed(root, scratch, supplied):
    pin = json.loads(read_regular(root / 'release/dependencies.lock.json', 64 << 10))['dorkpipe_resolver']
    source = json.loads(read_regular(root / 'release/dependency-source.lock.json', 64 << 10))
    if supplied is None:
        release = json.loads(run(['gh', 'api',
                                  f"repos/{REPOSITORY}/releases/tags/{source['tag']}"]).stdout)
        matching = [asset for asset in release.get('assets', []) if asset.get('name') == pin['tarball']]
        if (release.get('tag_name') != source['tag'] or release.get('draft') is not False
                or len(matching) != 1 or matching[0].get('size') != pin['size_bytes']
                or matching[0].get('digest') != f"sha256:{pin['sha256']}"):
            raise ValueError('Pipeon frozen seed release differs from committed dependency pin')
        run(['gh', 'release', 'download', source['tag'], '--repo', REPOSITORY,
             '--pattern', pin['tarball'], '--dir', str(scratch)])
        supplied = scratch / pin['tarball']
    return verify_seed(root, supplied)


def require_dependency_closure(manifest, requirements):
    resolver_names = {entry['name'] for entry in manifest['packages']['resolvers']}
    if 'dorkpipe' not in requirements or not requirements.issubset(resolver_names):
        raise ValueError('Pipeon package feed has an unresolved resolver dependency')


def verify_feed_entries(manifest, store):
    expected = set()
    for section in ('resolvers', 'workflows'):
        for entry in manifest['packages'][section]:
            name = entry['tarball']
            if (not isinstance(name, str)
                    or not re.fullmatch(r'dockpipe-(resolver|workflow)-[a-z][a-z0-9.-]*-[0-9]+\.[0-9]+\.[0-9]+\.tar\.gz', name)
                    or name in expected):
                raise ValueError('Package feed archive path or identity is invalid')
            path = store / name
            if path.stat().st_size != entry['size_bytes'] or digest(path) != entry['sha256']:
                raise ValueError('Package feed archive differs from manifest')
            sidecar = store / (name + '.sha256')
            if read_regular(sidecar, 1024).decode().strip() != entry['sha256']:
                raise ValueError('Package feed checksum sidecar differs from manifest')
            expected.update({name, name + '.sha256'})
    expected.add('packages-store-manifest.json')
    if {path.name for path in store.iterdir()} != expected:
        raise ValueError('Package feed has extra or missing files')
    if len(manifest['packages']['resolvers']) + len(manifest['packages']['workflows']) != PACKAGE_COUNT + (PRODUCT == 'pipeon'):
        raise ValueError('Package feed dependency closure is incomplete')


def prepare_feed(root, directory, bundle, seed_archive=None):
    store = unpack_store(bundle, directory)
    ownership = json.loads(read_regular(root / 'release/package-ownership.json', 64 << 10))
    if digest(directory / 'LICENSE', 64 << 10) != ownership['license_sha256']:
        raise ValueError('Frozen package bundle license differs from ownership')
    manifest = verify_store(root, store)
    if PRODUCT == 'pipeon':
        dependency, resolver = acquire_seed(root, directory, seed_archive)
        seed = seed_archive or directory / resolver['tarball']
        target = store / resolver['tarball']
        if seed != target:
            target.write_bytes(read_regular(seed, MAX_ASSET_BYTES))
        (store / (resolver['tarball'] + '.sha256')).write_text(resolver['sha256'] + '\n')
        manifest['packages']['resolvers'].append(resolver)
        manifest['packages']['resolvers'].sort(key=lambda item: (item['name'], item['version']))
        manifest['dependency_provenance'] = {
            'resolver': {'name': resolver['name'], 'version': resolver['version'],
                         'sha256': resolver['sha256'], 'size_bytes': resolver['size_bytes']},
            'source_dorkpipe_sha': dependency['source_dorkpipe_sha'],
            'seed_release_tag': dependency['seed_release_tag'],
        }
        (store / 'packages-store-manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
        from validate_package_store import manifest_sequence
        requirements = set()
        for entry in manifest['packages']['resolvers'] + manifest['packages']['workflows']:
            with tarfile.open(store / entry['tarball'], 'r:gz') as archive:
                path = f"{'resolvers' if entry in manifest['packages']['resolvers'] else 'workflows'}/{entry['name']}/package.yml"
                member = archive.getmember(path)
                if member.size > 64 << 10:
                    raise ValueError('Package dependency manifest exceeds capacity')
                requirements.update(manifest_sequence(archive.extractfile(member).read().decode(), 'requires_resolvers'))
        require_dependency_closure(manifest, requirements)
    verify_feed_entries(manifest, store)
    return store


def publication_target():
    bucket = os.environ.get('DOCKPIPE_RELEASE_BUCKET', '')
    endpoint = os.environ.get('R2_ENDPOINT_URL', '')
    parsed = urlsplit(endpoint)
    if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{1,61}[A-Za-z0-9]', bucket)
            or parsed.scheme != 'https' or not parsed.hostname
            or parsed.username or parsed.password or parsed.path not in ('', '/')
            or parsed.query or parsed.fragment):
        raise ValueError('Package-host bucket or HTTPS endpoint is invalid')
    if not os.environ.get('AWS_ACCESS_KEY_ID') or not os.environ.get('AWS_SECRET_ACCESS_KEY'):
        raise ValueError('Package-host read/write credentials are unavailable')
    return bucket, endpoint


def aws(arguments, *, allow_failure=False):
    environment = dict(os.environ, AWS_DEFAULT_REGION='auto')
    return run(['aws', 's3api', *arguments], environment=environment,
               allow_failure=allow_failure)


def read_remote(bucket, endpoint, key, destination, maximum):
    result = aws(['head-object', '--bucket', bucket, '--key', key,
                  '--endpoint-url', endpoint, '--region', 'auto'], allow_failure=True)
    if result.returncode:
        if 'NoSuchKey' in result.stderr or '(404)' in result.stderr:
            return False
        raise ValueError('Cannot prove package-host object state')
    metadata = json.loads(result.stdout)
    if type(metadata.get('ContentLength')) is not int or metadata['ContentLength'] != maximum:
        raise ValueError('Existing package-host object size differs')
    aws(['get-object', '--bucket', bucket, '--key', key, str(destination),
         '--endpoint-url', endpoint, '--region', 'auto'])
    return True


def publish_asset(path, asset, bucket, endpoint, key, scratch):
    remote = scratch / f"readback-{asset['name']}"
    if read_remote(bucket, endpoint, key, remote, asset['bytes']):
        if remote.stat().st_size != asset['bytes'] or digest(remote) != asset['sha256']:
            raise ValueError(f"Existing package-host object differs: {asset['name']}")
        return
    content_type = mimetypes.guess_type(asset['name'])[0] or 'application/octet-stream'
    result = aws(['put-object', '--bucket', bucket, '--key', key, '--body', str(path),
                  '--if-none-match', '*', '--endpoint-url', endpoint, '--region', 'auto',
                  '--content-type', content_type,
                  '--cache-control', 'public, max-age=31536000, immutable'], allow_failure=True)
    if result.returncode and 'PreconditionFailed' not in result.stderr and '(412)' not in result.stderr:
        raise ValueError(f"Conditional package-host upload failed: {asset['name']}")
    if not read_remote(bucket, endpoint, key, remote, asset['bytes']):
        raise ValueError(f"Package-host readback is missing: {asset['name']}")
    if remote.stat().st_size != asset['bytes'] or digest(remote) != asset['sha256']:
        raise ValueError(f"Package-host readback differs: {asset['name']}")


def publish(lock, directory, store, channel):
    repository = os.environ.get('GITHUB_REPOSITORY')
    branch = os.environ.get('GITHUB_REF')
    event = os.environ.get('GITHUB_EVENT_NAME')
    environment = os.environ.get('PACKAGE_HOST_ENVIRONMENT')
    if repository != REPOSITORY:
        raise ValueError('Package-host repository differs from product owner')
    if channel == 'staging':
        if (branch != 'refs/heads/staging' or event not in {'push', 'workflow_dispatch'}
                or environment != 'release-staging'):
            raise ValueError('Staging publication requires staging branch and environment')
        prefix = f"packages/standalone/{PRODUCT}/candidates/{VERSION}-staging.{lock['source_sha'][:12]}"
    elif channel == 'production':
        if branch != 'refs/heads/master' or event != 'push' or environment != 'release':
            raise ValueError('Production publication requires master push and release environment')
        prefix = f'packages/standalone/{PRODUCT}/releases/{VERSION}'
    else:
        raise ValueError('Package-host channel is invalid')
    bucket, endpoint = publication_target()
    assets = {asset['name']: asset for asset in lock['assets']}
    for name in sorted(assets):
        publish_asset(directory / name, assets[name], bucket, endpoint,
                      f'{prefix}/{name}', directory)
    feed = sorted(path.name for path in store.iterdir() if path.name != 'packages-store-manifest.json')
    for name in feed + ['packages-store-manifest.json']:
        path = store / name
        asset = {'name': name, 'bytes': path.stat().st_size, 'sha256': digest(path)}
        publish_asset(path, asset, bucket, endpoint, f'{prefix}/packages/{name}', directory)
    print(f'Published verified frozen {PRODUCT} package feed at {prefix}/packages/')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('local', 'frozen', 'pin'), required=True)
    parser.add_argument('--delivery', type=Path)
    parser.add_argument('--source-sha')
    parser.add_argument('--channel', choices=('staging', 'production'))
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--seed-archive', type=Path)
    args = parser.parse_args()
    if args.mode == 'local' and args.publish:
        parser.error('Local validation cannot publish')
    if args.publish != bool(args.channel):
        parser.error('Publication and channel must be selected together')
    root = Path(__file__).resolve().parents[1]
    if args.mode in ('local', 'frozen'):
        if args.delivery is None or args.source_sha is None:
            parser.error('Candidate delivery and exact producer SHA are required')
        lock = delivery_lock(args.delivery, args.source_sha)
    else:
        if args.delivery is not None or args.source_sha is not None:
            parser.error('Pinned publication accepts no delivery or source override')
        lock = source_lock(root)
    if PRODUCT != 'pipeon' and args.seed_archive is not None:
        parser.error('Only Pipeon accepts a pinned resolver seed')
    if args.mode == 'local':
        with tempfile.TemporaryDirectory(prefix=f'{PRODUCT}-package-feed-') as temporary:
            prepare_feed(root, Path(temporary), args.delivery / bundle_name(), args.seed_archive)
        print(f"Validated local frozen {PRODUCT} package feed from {lock['source_sha']}")
        return
    verify_release(lock)
    with tempfile.TemporaryDirectory(prefix=f'{PRODUCT}-package-host-') as temporary:
        directory = Path(temporary)
        download_and_validate(lock, directory)
        with tempfile.TemporaryDirectory(prefix=f'{PRODUCT}-store-') as extracted:
            store = prepare_feed(root, Path(extracted), directory / bundle_name(), args.seed_archive)
            if args.mode == 'frozen':
                local = {asset['name']: asset for asset in lock['assets']}
                for name, asset in local.items():
                    if digest(args.delivery / name) != asset['sha256']:
                        raise ValueError(f'Same-run delivery differs from frozen release: {name}')
            if args.publish:
                publish(lock, directory, store, args.channel)
            else:
                print(f"Validated frozen {PRODUCT} package feed {lock['release_tag']} without publication")


if __name__ == '__main__':
    main()
