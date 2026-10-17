"""Compatibility identities retain one authored resolver source and typed edges."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import generate_compat_workflows as generator
import validate_package_store as validator


class CompatibilityWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.output = self.root / 'generated'
        self.source = self.root / 'packages/dorkpipe/resolvers'
        committed = Path(__file__).resolve().parents[1] / 'release/package-ownership.json'
        self.ownership = validator.load_ownership(committed)
        self.license = b'fixture Apache-2.0 notice\n'
        self.ownership['license_sha256'] = hashlib.sha256(self.license).hexdigest()
        self.lock = self.root / 'ownership.json'
        self.lock.write_text(json.dumps(self.ownership))
        for name in self.ownership['resolvers']:
            leaf = self.source / name
            (leaf / 'assets').mkdir(parents=True)
            fields = {'schema': 1, 'kind': 'resolver', 'name': name,
                      'version': self.ownership['version'], 'namespace': self.ownership['namespace'],
                      'license': 'Apache-2.0', 'min_dockpipe_version': self.ownership['min_dockpipe_version']}
            manifest = ''.join(f'{key}: {value}\n' for key, value in fields.items())
            config = f'name: {name}\nsteps: []\n'
            if name == 'dorkpipe':
                config += 'compile_hooks:\n- bash assets/compile.sh\n'
            else:
                manifest += 'requires_resolvers:\n- dorkpipe\n'
            (leaf / 'package.yml').write_text(manifest)
            (leaf / 'config.yml').write_text(config)
            (leaf / 'LICENSE').write_bytes(self.license)
            (leaf / 'assets/run.sh').write_text('#!/bin/sh\nexit 0\n')
            (leaf / 'assets/run.sh').chmod(0o755)

    def generate(self):
        return generator.generate(self.root, self.output, self.lock)

    def test_all_eight_public_aliases_retain_pinned_metadata_and_typed_resolver_edge(self):
        self.assertEqual(self.generate(), sorted(self.ownership['resolvers']))
        self.assertEqual({path.name for path in self.output.iterdir()}, set(self.ownership['resolvers']))
        for name in self.ownership['resolvers']:
            manifest = (self.output / name / 'package.yml').read_text()
            self.assertEqual(validator.manifest_scalar(manifest, 'kind'), 'workflow')
            for field in ['version', 'min_dockpipe_version', 'namespace']:
                self.assertEqual(validator.manifest_scalar(manifest, field), self.ownership[field])
            self.assertIn('requires_resolvers:\n- dorkpipe\n', manifest)
            self.assertNotIn('depends:', manifest)
            self.assertEqual((self.output / name / 'LICENSE').read_bytes(), self.license)
        self.assertEqual((self.output / 'dorkpipe/config.yml').read_text(),
                         'name: dorkpipe\nnamespace: dockpipeproject\nsteps: []\n')
        profile = self.output / 'dorkpipe/assets/flatpak/package.json'
        self.assertEqual(json.loads(profile.read_text()), {
            'schema': 1, 'artifacts': [{'kind': 'workflow', 'name': 'dorkpipe'}],
            'tools': [], 'host_commands': [], 'required_files': [],
        })
        self.assertEqual([path.relative_to(self.output / 'dorkpipe/assets').as_posix()
                          for path in (self.output / 'dorkpipe/assets').rglob('*') if path.is_file()],
                         ['flatpak/package.json'])

    def test_other_aliases_copy_authored_config_assets_and_executable_mode(self):
        self.generate()
        for name in set(self.ownership['resolvers']) - {'dorkpipe'}:
            for relative in ['config.yml', 'assets/run.sh']:
                self.assertEqual((self.output / name / relative).read_bytes(),
                                 (self.source / name / relative).read_bytes())
            self.assertEqual((self.output / name / 'assets/run.sh').stat().st_mode & 0o777, 0o755)

    def test_version_license_and_dependency_drift_rejected_before_output(self):
        leaf = self.source / 'compliance-handoff'
        manifest = leaf / 'package.yml'
        original = manifest.read_text()
        replacements = [('version: 0.6.5', 'version: 0.6.6'),
                        ('min_dockpipe_version: 0.6.17', 'min_dockpipe_version: 0.6.0'),
                        ('requires_resolvers:\n- dorkpipe\n', 'depends:\n- dorkpipe\n'),
                        ('requires_resolvers:\n- dorkpipe\n', 'requires_resolvers:\n- other\n')]
        for old, new in replacements:
            with self.subTest(new=new):
                manifest.write_text(original.replace(old, new))
                with self.assertRaises(ValueError):
                    self.generate()
                self.assertFalse(self.output.exists())
        manifest.write_text(original)
        (leaf / 'LICENSE').write_text('wrong notice')
        with self.assertRaises(ValueError):
            self.generate()
        self.assertFalse(self.output.exists())

    def test_missing_extra_and_linked_source_rejected(self):
        manifest = self.source / 'compliance-handoff/package.yml'
        original = manifest.read_bytes()
        manifest.unlink()
        with self.assertRaises(OSError):
            self.generate()
        manifest.write_bytes(original)
        extra = self.source / 'unowned'
        extra.mkdir()
        with self.assertRaises(ValueError):
            self.generate()
        extra.rmdir()
        for path in [self.source / 'compliance-handoff/assets/link', self.source / 'compliance-handoff/linked-directory']:
            path.symlink_to(self.root)
            with self.assertRaises(ValueError):
                self.generate()
            path.unlink()
        self.assertFalse(self.output.exists())

    def test_output_must_be_fresh_and_unlinked(self):
        self.output.mkdir()
        with self.assertRaises(ValueError):
            self.generate()
        self.output.rmdir()
        self.output.symlink_to(self.root / 'absent')
        with self.assertRaises(ValueError):
            self.generate()

    def test_file_metadata_and_aggregate_capacity_enforced(self):
        for name in ['MAX_FILES', 'MAX_BYTES', 'MAX_METADATA_BYTES']:
            with self.subTest(limit=name), patch.object(generator, name, 1):
                with self.assertRaises(ValueError):
                    self.generate()
                self.assertFalse(self.output.exists())

    def test_ownership_requires_every_legacy_identity(self):
        ownership = copy.deepcopy(self.ownership)
        ownership['workflows'].remove('dorkpipe')
        ownership['workflows'].append('unowned')
        self.lock.write_text(json.dumps(ownership))
        with self.assertRaisesRegex(ValueError, 'public workflow alias'):
            self.generate()


if __name__ == '__main__':
    unittest.main()
