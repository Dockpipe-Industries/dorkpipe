"""Offline bundle reproducibility and integrity checks for public delivery."""
import hashlib
import json
import os
from pathlib import Path
import tarfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import assemble_package_delivery as delivery
import publish_package_delivery as publisher


SOURCE_ROOT = Path(os.environ.get('DORKPIPE_TEST_SOURCE_ROOT', Path(__file__).resolve().parents[1]))


class PackageDeliveryTests(unittest.TestCase):
    def setUp(self):
        from test_validate_package_store import PackageStoreTests

        fixture = PackageStoreTests(methodName='test_exact_owned_twenty_six_leaf_store')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.root = fixture.root
        self.store = fixture.store
        self.editors = self.root / 'editors'
        self.editors.mkdir()
        entries = []
        for extension in ('dockpipe-language-support', 'pipeon'):
            package = json.loads((SOURCE_ROOT / f'tooling/vscode-extensions/{extension}/package.json').read_text())
            if extension == 'dockpipe-language-support':
                self.language_version = package['version']
            name = f"{extension}-{package['version']}.vsix"
            payload = f'{extension} fixture'.encode()
            (self.editors / name).write_bytes(payload)
            entries.append({'path': name, 'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()})
        (self.editors / 'extensions.json').write_text(json.dumps({'schema': 1, 'files': entries}))

    def test_bundle_is_deterministic_and_includes_only_curated_store(self):
        first = self.root / 'first'
        second = self.root / 'second'
        for output in (first, second):
            delivery.assemble(SOURCE_ROOT, self.store, self.editors, 'a' * 40, output)
        archive_name = delivery.ARCHIVE_NAME
        self.assertEqual((first / archive_name).read_bytes(), (second / archive_name).read_bytes())
        sdk_name = f'dockpipe-language-test-sdk-{self.language_version}.tar.gz'
        self.assertEqual((first / sdk_name).read_bytes(), (second / sdk_name).read_bytes())
        provenance = json.loads((first / 'delivery-provenance.json').read_text())
        self.assertEqual(provenance['package_count'], 26)
        self.assertEqual(len(provenance['files']), 4)
        self.assertEqual(len(list(first.iterdir())), 6)

        with tarfile.open(first / sdk_name, mode='r:gz') as archive:
            members = archive.getmembers()
            names = {member.name for member in members}
            expected_names = {
                f'{delivery.EDITOR_SOURCE_DIRECTORY}/{name}'
                for name in (*delivery.EDITOR_SOURCE_FILES, 'editor-source.json')
            }
            self.assertEqual(names, expected_names)
            self.assertTrue(all(member.isfile() and member.mode == 0o644 for member in members))
            manifest_member = archive.extractfile(f'{delivery.EDITOR_SOURCE_DIRECTORY}/editor-source.json')
            self.assertIsNotNone(manifest_member)
            manifest_bytes = manifest_member.read()
            manifest = json.loads(manifest_bytes)
            self.assertEqual(manifest_bytes, delivery.canonical_json(manifest))
            self.assertEqual(set(manifest), {
                'schema', 'editor_version', 'source_dorkpipe_sha', 'source_digest', 'files',
            })
            self.assertEqual(manifest['schema'], 1)
            self.assertEqual(manifest['source_dorkpipe_sha'], 'a' * 40)
            self.assertEqual(manifest['editor_version'], self.language_version)
            self.assertEqual([entry['path'] for entry in manifest['files']], sorted(delivery.EDITOR_SOURCE_FILES))
            self.assertTrue(all(set(entry) == {'path', 'bytes', 'sha256'} for entry in manifest['files']))
            source_digest = hashlib.sha256(json.dumps(
                manifest['files'], sort_keys=True, separators=(',', ':'),
            ).encode()).hexdigest()
            self.assertEqual(manifest['source_digest'], source_digest)
            for entry in manifest['files']:
                payload = archive.extractfile(f"{delivery.EDITOR_SOURCE_DIRECTORY}/{entry['path']}").read()
                self.assertEqual(len(payload), entry['bytes'])
                self.assertEqual(hashlib.sha256(payload).hexdigest(), entry['sha256'])

    def test_source_sdk_rejects_linked_input_and_oversized_file(self):
        source_root = self.root / 'source'
        editor_root = source_root / 'tooling/vscode-extensions/dockpipe-language-support'
        for name in delivery.EDITOR_SOURCE_FILES:
            destination = editor_root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((SOURCE_ROOT / 'tooling/vscode-extensions/dockpipe-language-support' / name).read_bytes())
        (editor_root / 'extension.js').unlink()
        (editor_root / 'extension.js').symlink_to(self.root / 'outside')
        (self.root / 'outside').write_bytes(b'outside')
        with self.assertRaisesRegex(ValueError, 'Expected regular file'):
            delivery.build_editor_source_sdk(source_root, 'a' * 40, self.root)

        (editor_root / 'extension.js').unlink()
        (editor_root / 'extension.js').write_bytes(b'x' * (delivery.MAX_EDITOR_SOURCE_BYTES + 1))
        with self.assertRaisesRegex(ValueError, 'exceeds'):
            delivery.build_editor_source_sdk(source_root, 'a' * 40, self.root)

    def test_changed_editor_and_extra_store_file_fail(self):
        editor = next(self.editors.glob('pipeon-*.vsix'))
        editor.write_bytes(editor.read_bytes() + b'changed')
        with self.assertRaisesRegex(ValueError, 'Editor extension checksum differs'):
            delivery.assemble(SOURCE_ROOT, self.store, self.editors, 'a' * 40, self.root / 'tampered')
        editor.write_bytes(b'pipeon fixture')
        (self.store / 'extra').write_bytes(b'unowned')
        with self.assertRaisesRegex(ValueError, 'extra or missing files'):
            delivery.assemble(SOURCE_ROOT, self.store, self.editors, 'a' * 40, self.root / 'extra')

    def test_delivery_rejects_oversized_file_and_linked_parent(self):
        source = self.root / 'bounded'
        source.write_bytes(b'ab')
        with self.assertRaisesRegex(ValueError, 'exceeds'):
            delivery.read_regular(source, 1)
        linked_parent = self.root / 'linked'
        linked_parent.symlink_to(self.editors, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'Linked file parent'):
            delivery.read_regular(linked_parent / 'extensions.json', 1024)

    def test_publisher_rejects_unowned_path_and_oversized_metadata(self):
        output = self.root / 'delivery'
        delivery.assemble(SOURCE_ROOT, self.store, self.editors, 'a' * 40, output)
        provenance_path = output / 'delivery-provenance.json'
        provenance = json.loads(provenance_path.read_text())
        provenance['files'][0]['name'] = '../unowned.vsix'
        provenance_path.write_text(json.dumps(provenance))
        editor_names = {path.name for path in self.editors.glob('*.vsix')}
        environment = {
            'GITHUB_REPOSITORY': publisher.REPOSITORY,
            'GITHUB_REF': 'refs/heads/staging',
            'GITHUB_SHA': 'a' * 40,
        }
        with (patch.dict(os.environ, environment),
              patch.object(publisher, 'editor_asset_names', return_value=editor_names),
              patch.object(publisher, 'editor_source_asset_name', return_value=f'dockpipe-language-test-sdk-{self.language_version}.tar.gz')):
            with self.assertRaisesRegex(ValueError, 'unowned delivery asset'):
                publisher.publish(output)
            provenance_path.write_bytes(b'x' * (publisher.MAX_PROVENANCE_BYTES + 1))
            with self.assertRaisesRegex(ValueError, 'exceeds'):
                publisher.publish(output)

    def test_publisher_rejects_tampered_source_sdk_before_network(self):
        output = self.root / 'delivery'
        delivery.assemble(SOURCE_ROOT, self.store, self.editors, 'a' * 40, output)
        sdk_path = output / f'dockpipe-language-test-sdk-{self.language_version}.tar.gz'
        sdk_path.write_bytes(sdk_path.read_bytes() + b'tampered')
        environment = {
            'GITHUB_REPOSITORY': publisher.REPOSITORY,
            'GITHUB_REF': 'refs/heads/staging',
            'GITHUB_SHA': 'a' * 40,
        }
        editor_names = {path.name for path in self.editors.glob('*.vsix')}
        with (patch.dict(os.environ, environment),
              patch.object(publisher, 'editor_asset_names', return_value=editor_names),
              patch.object(publisher, 'editor_source_asset_name', return_value=sdk_path.name),
              patch.object(publisher, 'release_api') as remote):
            with self.assertRaisesRegex(ValueError, 'differs from provenance'):
                publisher.publish(output)
            remote.assert_not_called()

    def test_publication_rejects_private_wrong_owner_and_malformed_repository(self):
        output = self.root / 'delivery'
        delivery.assemble(SOURCE_ROOT, self.store, self.editors, 'a' * 40, output)
        environment = {'GITHUB_REPOSITORY': publisher.REPOSITORY,
                       'GITHUB_REF': 'refs/heads/staging', 'GITHUB_SHA': 'a' * 40}
        repository = {'full_name': publisher.REPOSITORY, 'private': False, 'visibility': 'public'}
        rejected = [dict(repository, private=True),
                    dict(repository, full_name='other-owner/dorkpipe'),
                    dict(repository, private=0), dict(repository, visibility='private'),
                    [], None]
        payloads = [json.dumps(value) for value in rejected] + ['invalid-json']
        for payload in payloads:
            with self.subTest(payload=payload):
                with (patch.dict(os.environ, environment, clear=True),
                      patch.object(publisher, 'editor_asset_names', return_value={path.name for path in self.editors.glob('*.vsix')}),
                      patch.object(publisher, 'editor_source_asset_name', return_value=f'dockpipe-language-test-sdk-{self.language_version}.tar.gz'),
                      patch.object(publisher, 'gh', return_value=SimpleNamespace(stdout=payload)) as remote,
                      patch.object(publisher, 'release_api') as lookup):
                    with self.assertRaises(ValueError):
                        publisher.publish(output)
                    remote.assert_called_once_with('api', f'repos/{publisher.REPOSITORY}')
                    lookup.assert_not_called()

    def test_draft_lookup_checks_list_and_rejects_duplicate_tags(self):
        tag = 'v0.6.5-staging.' + 'a' * 12
        draft = {'id': 71, 'tag_name': tag, 'draft': True}
        missing = SimpleNamespace(returncode=1, stdout='', stderr='HTTP 404')
        listed = SimpleNamespace(returncode=0, stdout=json.dumps([draft]), stderr='')
        with patch.object(publisher, 'gh', side_effect=[missing, listed]):
            with patch.object(publisher, 'release_by_id', return_value=draft) as refresh:
                self.assertEqual(publisher.release_api(tag), draft)
                refresh.assert_called_once_with(71)
        duplicates = SimpleNamespace(returncode=0, stdout=json.dumps([draft, draft]), stderr='')
        with patch.object(publisher, 'gh', side_effect=[missing, duplicates]):
            with self.assertRaisesRegex(ValueError, 'Multiple GitHub releases'):
                publisher.release_api(tag)

    def test_created_draft_uses_id_and_existing_changed_bytes_cannot_be_clobbered(self):
        output = self.root / 'delivery'
        publisher_names = {path.name for path in self.editors.glob('*.vsix')}
        delivery.assemble(SOURCE_ROOT, self.store, self.editors, 'a' * 40, output)
        names = {path.name for path in output.iterdir()}
        tag = 'v0.6.5-staging.' + 'a' * 12
        empty = {'id': 71, 'tag_name': tag, 'target_commitish': 'a' * 40,
                 'prerelease': True, 'draft': True, 'assets': []}
        full = dict(empty, assets=[{'name': name} for name in names])
        environment = {'GITHUB_REPOSITORY': publisher.REPOSITORY,
                       'GITHUB_REF': 'refs/heads/staging', 'GITHUB_SHA': 'a' * 40}

        def github(*arguments, **_):
            if arguments == ('api', f'repos/{publisher.REPOSITORY}'):
                return SimpleNamespace(stdout=json.dumps({
                    'full_name': publisher.REPOSITORY, 'private': False, 'visibility': 'public'}))
            if arguments[:3] == ('api', '-X', 'POST'):
                return SimpleNamespace(stdout=json.dumps({'id': 71}))
            if arguments[:2] == ('release', 'download'):
                name = arguments[arguments.index('--pattern') + 1]
                destination = Path(arguments[arguments.index('--dir') + 1]) / name
                destination.write_bytes((output / name).read_bytes())
            return SimpleNamespace(stdout='{}')

        with (patch.dict(os.environ, environment),
              patch.object(publisher, 'editor_asset_names', return_value=publisher_names),
              patch.object(publisher, 'editor_source_asset_name', return_value=f'dockpipe-language-test-sdk-{self.language_version}.tar.gz'),
              patch.object(publisher, 'release_api', return_value=None),
              patch.object(publisher, 'release_by_id', side_effect=[empty, full]) as refresh,
              patch.object(publisher, 'gh', side_effect=github) as commands):
            publisher.publish(output)
        self.assertEqual([call.args for call in refresh.call_args_list], [(71,), (71,)])
        self.assertEqual(len([call for call in commands.call_args_list if call.args[:2] == ('release', 'upload')]), 6)

        draft_with_asset = dict(empty, assets=[{'name': delivery.ARCHIVE_NAME}])
        def changed_download(*arguments, **_):
            if arguments == ('api', f'repos/{publisher.REPOSITORY}'):
                return SimpleNamespace(stdout=json.dumps({
                    'full_name': publisher.REPOSITORY, 'private': False, 'visibility': 'public'}))
            self.assertEqual(arguments[:2], ('release', 'download'))
            name = arguments[arguments.index('--pattern') + 1]
            destination = Path(arguments[arguments.index('--dir') + 1]) / name
            destination.write_bytes(b'changed remote bytes')
        with (patch.dict(os.environ, environment),
              patch.object(publisher, 'editor_asset_names', return_value=publisher_names),
              patch.object(publisher, 'editor_source_asset_name', return_value=f'dockpipe-language-test-sdk-{self.language_version}.tar.gz'),
              patch.object(publisher, 'release_api', return_value=draft_with_asset),
              patch.object(publisher, 'gh', side_effect=changed_download) as commands):
            with self.assertRaisesRegex(ValueError, 'refusing to clobber'):
                publisher.publish(output)
            self.assertEqual(commands.call_count, 2)


if __name__ == '__main__':
    unittest.main()
