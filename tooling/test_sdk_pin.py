"""Committed SDK source snapshot pins reject drift before executing Go."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location('pinned_go_candidate', Path(__file__).with_name('go_candidate.py'))
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)


class SDKPinTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / 'release').mkdir()
        self.path = self.root / 'release/dependencies.lock.json'
        self.manifest = {
            'sdk_version': '0.1.0-source.' + 'a' * 16,
            'source_commit': 'b' * 40,
            'source_digest': 'a' * 64,
            'sha256': 'c' * 64,
        }
        self.digest = hashlib.sha256(json.dumps(self.manifest).encode()).hexdigest()
        self.lock = {
            'schema': 1,
            'dockpipe_go_sdk': {
                'version': self.manifest['sdk_version'],
                'source_commit': self.manifest['source_commit'],
                'source_digest': self.manifest['source_digest'],
                'manifest_sha256': self.digest,
                'archive_sha256': self.manifest['sha256'],
            },
        }
        self.write_lock()

    def write_lock(self):
        self.path.write_text(json.dumps(self.lock))

    def test_valid_committed_source_snapshot(self):
        before = copy.deepcopy(self.manifest)
        candidate.validate_sdk_pin(self.root, self.manifest, self.digest)
        self.assertEqual(self.manifest, before)

    def test_approved_redistribution_version_preserves_exact_source_pin(self):
        self.manifest['sdk_version'] = '0.1.1-source.' + 'a' * 16
        self.lock['dockpipe_go_sdk']['version'] = self.manifest['sdk_version']
        self.digest = hashlib.sha256(json.dumps(self.manifest).encode()).hexdigest()
        self.lock['dockpipe_go_sdk']['manifest_sha256'] = self.digest
        self.write_lock()
        candidate.validate_sdk_pin(self.root, self.manifest, self.digest)
        self.lock['dockpipe_go_sdk']['version'] = '0.1.1-source.' + 'd' * 16
        self.write_lock()
        with self.assertRaisesRegex(ValueError, 'version does not identify'):
            candidate.validate_sdk_pin(self.root, self.manifest, self.digest)

    def test_manifest_identity_drift(self):
        for field, value in [
            ('sdk_version', '0.1.0-source.' + 'd' * 16),
            ('source_commit', 'd' * 40),
            ('source_digest', 'd' * 64),
            ('sha256', 'd' * 64),
        ]:
            with self.subTest(field=field):
                manifest = dict(self.manifest, **{field: value})
                with self.assertRaisesRegex(ValueError, 'manifest identity'):
                    candidate.validate_sdk_pin(self.root, manifest, self.digest)

    def test_manifest_digest_drift(self):
        with self.assertRaisesRegex(ValueError, 'manifest digest'):
            candidate.validate_sdk_pin(self.root, self.manifest, 'd' * 64)

    def test_missing_identity_fields_rejected(self):
        for field in self.manifest:
            with self.subTest(field=field):
                manifest = self.manifest.copy()
                del manifest[field]
                with self.assertRaises(ValueError):
                    candidate.validate_sdk_pin(self.root, manifest, self.digest)

    def test_missing_and_oversized_lock(self):
        self.path.unlink()
        with self.assertRaises(FileNotFoundError):
            candidate.validate_sdk_pin(self.root, self.manifest, self.digest)
        self.path.write_bytes(b' ' * (candidate.MAX_LOCK_BYTES + 1))
        with self.assertRaisesRegex(ValueError, 'exceeds'):
            candidate.validate_sdk_pin(self.root, self.manifest, self.digest)

    def test_malformed_and_duplicate_lock_fields(self):
        for field, value in [
            ('source_commit', 'branch'), ('source_digest', 'z' * 64),
            ('manifest_sha256', None), ('archive_sha256', 'c' * 63),
            ('version', 'stable'),
        ]:
            with self.subTest(field=field):
                lock = copy.deepcopy(self.lock)
                lock['dockpipe_go_sdk'][field] = value
                self.path.write_text(json.dumps(lock))
                with self.assertRaises(ValueError):
                    candidate.validate_sdk_pin(self.root, self.manifest, self.digest)
        self.path.write_text('{"schema": 1, "schema": 1}')
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            candidate.validate_sdk_pin(self.root, self.manifest, self.digest)

    def test_build_rejects_pin_before_any_go_operation(self):
        args = argparse.Namespace(
            source=self.root, output=self.root / 'candidate', manifest=self.root / 'sdk.json',
            archive=self.root / 'sdk.tar.gz', manifest_sha256='d' * 64,
            go='go-must-never-run', tests=True, download_dependencies=True,
        )
        with patch.object(candidate, 'unpack_sdk', return_value=self.manifest):
            with patch.object(candidate.subprocess, 'run') as process:
                with self.assertRaisesRegex(ValueError, 'manifest digest'):
                    candidate.build(args)
                process.assert_not_called()


if __name__ == '__main__':
    unittest.main()
