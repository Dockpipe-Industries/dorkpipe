"""Offline contract tests for immutable standalone package-host publication."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import publish_package_host as host


class PackageHostTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.delivery = self.root / 'delivery'
        self.delivery.mkdir()
        self.store = self.root / 'store'
        self.store.mkdir()
        (self.store / 'packages-store-manifest.json').write_text('{}')
        payloads = {}
        for name in sorted(host.REQUIRED_ASSETS - {'SHA256SUMS', 'delivery-provenance.json'}):
            data = f'frozen {name}\n'.encode()
            (self.delivery / name).write_bytes(data)
            payloads[name] = {'name': name, 'bytes': len(data),
                              'sha256': hashlib.sha256(data).hexdigest()}
        provenance = {'source_repository': host.REPOSITORY, 'source_sha': 'a' * 40,
                      'version': host.VERSION, 'package_count': host.PACKAGE_COUNT,
                      'platform': 'linux-amd64', 'files': list(payloads.values())}
        (self.delivery / 'delivery-provenance.json').write_text(json.dumps(provenance))
        digests = dict(payloads)
        data = (self.delivery / 'delivery-provenance.json').read_bytes()
        digests['delivery-provenance.json'] = {
            'sha256': hashlib.sha256(data).hexdigest()}
        sums = ''.join(f"{digests[name]['sha256']}  {name}\n" for name in sorted(digests))
        (self.delivery / 'SHA256SUMS').write_text(sums)

    def test_public_release_requires_exact_repository_and_visibility(self):
        lock = {'release_tag': 'v' + host.VERSION + '-staging.' + 'a' * 12,
                'source_sha': 'a' * 40, 'assets': []}
        release = {'tag_name': lock['release_tag'], 'target_commitish': lock['source_sha'],
                   'draft': False, 'prerelease': True, 'assets': []}
        repository = {'full_name': host.REPOSITORY, 'private': False, 'visibility': 'public'}
        with patch.object(host, 'run', side_effect=[
                SimpleNamespace(stdout=json.dumps(repository)),
                SimpleNamespace(stdout=json.dumps(release))]):
            self.assertIsNone(host.verify_release(lock))
        rejected = [dict(repository, private=True),
                    dict(repository, full_name='other-owner/dorkpipe'),
                    dict(repository, visibility='internal'),
                    dict(repository, private='false'),
                    {'full_name': host.REPOSITORY, 'private': False},
                    [], None]
        payloads = [json.dumps(value) for value in rejected]
        payloads.extend(['invalid-json', '{"private":false,"private":false}'])
        for payload in payloads:
            with self.subTest(payload=payload):
                with patch.object(host, 'run', return_value=SimpleNamespace(stdout=payload)) as remote:
                    with self.assertRaises(ValueError):
                        host.verify_release(lock)
                    self.assertEqual(remote.call_count, 1)

    def test_exact_delivery_and_tamper_rejection(self):
        lock = host.delivery_lock(self.delivery, 'a' * 40)
        self.assertEqual(set(asset['name'] for asset in lock['assets']), host.REQUIRED_ASSETS)
        archive = next(name for name in host.REQUIRED_ASSETS if name.endswith('linux-amd64.tar.gz'))
        (self.delivery / archive).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'checksums differ'):
            host.delivery_lock(self.delivery, 'a' * 40)

    def test_extra_asset_and_bad_source_rejected(self):
        (self.delivery / 'latest.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'missing or unexpected'):
            host.delivery_lock(self.delivery, 'a' * 40)
        (self.delivery / 'latest.json').unlink()
        with self.assertRaisesRegex(ValueError, 'exact producer'):
            host.delivery_lock(self.delivery, 'main')

    def test_branch_environment_and_key_separation(self):
        lock = host.delivery_lock(self.delivery, 'a' * 40)
        base = {'GITHUB_REPOSITORY': host.REPOSITORY, 'GITHUB_REF': 'refs/heads/staging',
                'GITHUB_EVENT_NAME': 'workflow_dispatch',
                'PACKAGE_HOST_ENVIRONMENT': 'release-staging'}
        with patch.dict(host.os.environ, base, clear=True):
            with patch.object(host, 'publication_target', return_value=('test-bucket', 'https://r2.example')):
                with patch.object(host, 'publish_asset') as upload:
                    host.publish(lock, self.delivery, self.store, 'staging')
        self.assertEqual(upload.call_count, len(host.REQUIRED_ASSETS) + 1)
        self.assertTrue(upload.call_args_list[-1].args[4].endswith('/packages/packages-store-manifest.json'))
        self.assertTrue(all('/candidates/' in call.args[4] for call in upload.call_args_list))
        self.assertTrue(all('latest.json' not in call.args[4] for call in upload.call_args_list))
        with patch.dict(host.os.environ, base, clear=True):
            with self.assertRaisesRegex(ValueError, 'master push'):
                host.publish(lock, self.delivery, self.store, 'production')
        production = dict(base, GITHUB_REF='refs/heads/master', GITHUB_EVENT_NAME='push',
                          PACKAGE_HOST_ENVIRONMENT='release')
        with patch.dict(host.os.environ, production, clear=True):
            with patch.object(host, 'publication_target', return_value=('test-bucket', 'https://r2.example')):
                with patch.object(host, 'publish_asset') as upload:
                    host.publish(lock, self.delivery, self.store, 'production')
        self.assertTrue(all('/releases/' in call.args[4] for call in upload.call_args_list))

    def test_existing_mismatched_object_cannot_be_clobbered(self):
        archive = next(name for name in host.REQUIRED_ASSETS if name.endswith('linux-amd64.tar.gz'))
        path = self.delivery / archive
        asset = {'name': archive, 'bytes': path.stat().st_size, 'sha256': host.digest(path)}
        def mismatched(*args):
            args[3].write_bytes(b'x' * asset['bytes'])
            return True
        with patch.object(host, 'read_remote', side_effect=mismatched):
            with patch.object(host, 'aws') as aws:
                with self.assertRaisesRegex(ValueError, 'Existing package-host object differs'):
                    host.publish_asset(path, asset, 'test-bucket', 'https://r2.example',
                                       f'packages/standalone/{host.PRODUCT}/candidates/test/{archive}', self.root)
        aws.assert_not_called()

    def test_identical_object_is_idempotent(self):
        archive = next(name for name in host.REQUIRED_ASSETS if name.endswith('linux-amd64.tar.gz'))
        path = self.delivery / archive
        asset = {'name': archive, 'bytes': path.stat().st_size, 'sha256': host.digest(path)}

        def matching(*arguments):
            arguments[3].write_bytes(path.read_bytes())
            return True

        with patch.object(host, 'read_remote', side_effect=matching):
            with patch.object(host, 'aws') as aws:
                host.publish_asset(path, asset, 'test-bucket', 'https://r2.example',
                                   f'packages/standalone/{host.PRODUCT}/candidates/test/{archive}', self.root)
        aws.assert_not_called()

    def test_bundle_rejects_path_escape_and_nonregular_member(self):
        for name, kind in [('packages/..', tarfile.REGTYPE),
                           ('packages/link', tarfile.SYMTYPE)]:
            bundle = self.root / 'bundle.tar.gz'
            with tarfile.open(bundle, 'w:gz') as archive:
                member = tarfile.TarInfo(name)
                member.type = kind
                member.size = 1 if kind == tarfile.REGTYPE else 0
                archive.addfile(member, io.BytesIO(b'x') if member.size else None)
            with tempfile.TemporaryDirectory() as scratch:
                with self.assertRaises(ValueError):
                    host.unpack_store(bundle, Path(scratch))

    def test_feed_rejects_archive_and_sidecar_mismatch(self):
        name = 'dockpipe-resolver-example-0.6.3.tar.gz'
        archive = self.store / name
        archive.write_bytes(b'package')
        sidecar = self.store / (name + '.sha256')
        correct = host.digest(archive)
        manifest = {'packages': {'resolvers': [
            {'tarball': name, 'size_bytes': 7, 'sha256': correct}], 'workflows': []}}
        sidecar.write_text('0' * 64 + '\n')
        with self.assertRaisesRegex(ValueError, 'sidecar'):
            host.verify_feed_entries(manifest, self.store)
        sidecar.write_text(correct + '\n')
        manifest['packages']['resolvers'][0]['size_bytes'] = 8
        with self.assertRaisesRegex(ValueError, 'archive differs'):
            host.verify_feed_entries(manifest, self.store)


if __name__ == '__main__':
    unittest.main()
