"""Offline exact ownership, archive metadata, integrity and capacity checks."""
import copy
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import validate_package_store as validator


class PackageStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.store = self.root / 'store'
        self.store.mkdir()
        self.ownership_path = self.root / 'ownership.json'
        self.ownership = validator.load_ownership(Path(__file__).resolve().parents[1] / 'release/package-ownership.json')
        self.ownership_path.write_text(json.dumps(self.ownership))
        self.manifest = {'schema': 1, 'platform': 'linux-amd64', 'packages': {}}
        for section in ['resolvers', 'workflows']:
            entries = []
            for name in self.ownership[section]:
                entry = {'name': name, 'version': self.ownership['version'],
                         'tarball': f"dockpipe-{section[:-1]}-{name}-{self.ownership['version']}.tar.gz",
                         'min_dockpipe_version': self.ownership['min_dockpipe_version']}
                entries.append(entry)
                self.write_archive(section, entry)
            self.manifest['packages'][section] = entries
        self.write_manifest()

    def write_manifest(self):
        (self.store / 'packages-store-manifest.json').write_text(json.dumps(self.manifest))

    def write_archive(self, section, entry, manifest_values=None, extra=None, config_values=None, include_license=True, license_payload=None):
        values = {'name': entry['name'], 'version': self.ownership['version'],
                  'namespace': self.ownership['namespace'], 'kind': section[:-1],
                  'license': 'Apache-2.0', 'min_dockpipe_version': self.ownership['min_dockpipe_version']}
        values.update(manifest_values or {})
        payload = ''.join(f'{key}: {value}\n' for key, value in values.items() if value is not None).encode()
        path = self.store / entry['tarball']
        with tarfile.open(path, 'w:gz') as archive:
            member = tarfile.TarInfo(f"{section}/{entry['name']}/package.yml")
            member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))
            if include_license:
                notice = license_payload if license_payload is not None else (Path(__file__).resolve().parents[1] / 'LICENSE').read_bytes()
                member = tarfile.TarInfo(f"{section}/{entry['name']}/LICENSE")
                member.size = len(notice)
                archive.addfile(member, io.BytesIO(notice))
            if section == 'workflows':
                config_fields = {'name': entry['name'], 'namespace': self.ownership['namespace']}
                config_fields.update(config_values or {})
                config = ''.join(f'{key}: {value}\n' for key, value in config_fields.items() if value is not None).encode()
                member = tarfile.TarInfo(f"{section}/{entry['name']}/config.yml")
                member.size = len(config)
                archive.addfile(member, io.BytesIO(config))
            if extra is not None:
                member = tarfile.TarInfo(extra)
                member.size = 1
                archive.addfile(member, io.BytesIO(b'x'))
        raw = path.read_bytes()
        entry['size_bytes'] = len(raw)
        entry['sha256'] = hashlib.sha256(raw).hexdigest()
        (self.store / (entry['tarball'] + '.sha256')).write_text(entry['sha256'] + '\n')

    def test_license_and_minimum_version_required_for_distribution(self):
        entry = self.manifest['packages']['resolvers'][0]
        for options in [{'include_license': False}, {'license_payload': b'changed notice'},
                        {'manifest_values': {'license': 'MIT'}},
                        {'manifest_values': {'min_dockpipe_version': '0.6.0'}}]:
            with self.subTest(options=options):
                self.write_archive('resolvers', entry, **options)
                self.write_manifest()
                with self.assertRaises(ValueError):
                    validator.validate(self.store, self.ownership_path)
        self.write_archive('resolvers', entry)
        entry['min_dockpipe_version'] = '0.6.0'
        self.write_manifest()
        with self.assertRaises(ValueError):
            validator.validate(self.store, self.ownership_path)

    def test_exact_owned_twenty_six_leaf_store(self):
        receipt = validator.validate(self.store, self.ownership_path)
        self.assertEqual(receipt['archive_count'], 26)
        self.assertEqual(receipt['resolvers'], sorted(self.ownership['resolvers']))
        self.assertEqual(receipt['workflows'], sorted(self.ownership['workflows']))

    def test_core_maintainer_and_duplicate_identities_rejected(self):
        original = copy.deepcopy(self.manifest)
        for scenario in ['core', 'maintainer', 'duplicate', 'missing']:
            with self.subTest(scenario=scenario):
                self.manifest = copy.deepcopy(original)
                if scenario == 'core':
                    self.manifest['packages']['core'] = {'name': 'core'}
                elif scenario == 'maintainer':
                    self.manifest['packages']['workflows'][0]['name'] = 'package.compile'
                elif scenario == 'duplicate':
                    self.manifest['packages']['workflows'][1] = self.manifest['packages']['workflows'][0]
                else:
                    self.manifest['packages']['resolvers'].pop()
                self.write_manifest()
                with self.assertRaises(ValueError):
                    validator.validate(self.store, self.ownership_path)

    def test_wrong_archive_kind_namespace_version_and_name_rejected(self):
        entry = self.manifest['packages']['workflows'][0]
        for field, value in [('kind', 'resolver'), ('namespace', 'other'), ('version', '0.6.6'), ('name', 'other')]:
            with self.subTest(field=field):
                self.write_archive('workflows', entry, {field: value})
                self.write_manifest()
                with self.assertRaises(ValueError):
                    validator.validate(self.store, self.ownership_path)

    def test_workflow_namespace_uses_public_config_fallback(self):
        entry = self.manifest['packages']['workflows'][0]
        self.write_archive('workflows', entry, {'namespace': None})
        self.write_manifest()
        validator.validate(self.store, self.ownership_path)
        self.write_archive('workflows', entry, {'namespace': None}, config_values={'namespace': None})
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'namespace is missing'):
            validator.validate(self.store, self.ownership_path)
        self.write_archive('workflows', entry, config_values={'namespace': 'other'})
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'namespace is missing or differs'):
            validator.validate(self.store, self.ownership_path)

    def test_corrupted_archive_checksum_and_sidecar_rejected(self):
        entry = self.manifest['packages']['resolvers'][0]
        archive = self.store / entry['tarball']
        original = archive.read_bytes()
        archive.write_bytes(original + b'changed')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            validator.validate(self.store, self.ownership_path)
        archive.write_bytes(original)
        (self.store / (entry['tarball'] + '.sha256')).write_text('0' * 64)
        with self.assertRaisesRegex(ValueError, 'sidecar mismatch'):
            validator.validate(self.store, self.ownership_path)

    def test_archive_cannot_escape_owned_root(self):
        entry = self.manifest['packages']['resolvers'][0]
        for extra in ['core/package.yml', '../escape', 'resolvers/other/config.yml']:
            with self.subTest(extra=extra):
                self.write_archive('resolvers', entry, extra=extra)
                self.write_manifest()
                with self.assertRaises(ValueError):
                    validator.validate(self.store, self.ownership_path)

    def test_links_and_unlisted_output_files_rejected(self):
        extra = self.store / 'maintainer.tar.gz'
        extra.write_bytes(b'extra')
        with self.assertRaisesRegex(ValueError, 'extra or missing files'):
            validator.validate(self.store, self.ownership_path)
        extra.unlink()
        entry = self.manifest['packages']['resolvers'][0]
        archive = self.store / entry['tarball']
        renamed = self.root / 'archive'
        archive.rename(renamed)
        archive.symlink_to(renamed)
        with self.assertRaises(ValueError):
            validator.validate(self.store, self.ownership_path)

    def test_archive_and_manifest_capacity_enforced(self):
        for constant in ['MAX_ARCHIVE_BYTES', 'MAX_EXPANDED_BYTES', 'MAX_PACKAGE_MANIFEST_BYTES', 'MAX_MEMBERS']:
            maximum = 0 if constant == 'MAX_MEMBERS' else 1
            with self.subTest(constant=constant), patch.object(validator, constant, maximum):
                with self.assertRaises(ValueError):
                    validator.validate(self.store, self.ownership_path)

    def test_ownership_descriptor_is_exact_and_versioned(self):
        for field, value in [('schema', 2), ('version', 'latest'), ('namespace', 'other'), ('resolvers', [])]:
            with self.subTest(field=field):
                ownership = copy.deepcopy(self.ownership)
                ownership[field] = value
                self.ownership_path.write_text(json.dumps(ownership))
                with self.assertRaises(ValueError):
                    validator.validate(self.store, self.ownership_path)


if __name__ == '__main__':
    unittest.main()
