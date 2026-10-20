import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('go_candidate', Path(__file__).with_name('go_candidate.py'))
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)


class SDKImportTests(unittest.TestCase):
    def fixture(self, directory, name='go.mod', payload=b'module dockpipe\n', extra=None, link=False):
        archive_path = directory / 'sdk.tar.gz'
        with tarfile.open(archive_path, 'w:gz') as archive:
            member = tarfile.TarInfo('dockpipe-go-sdk/' + name)
            member.size = len(payload)
            if link:
                member.type = tarfile.SYMTYPE
                member.linkname = '/etc/passwd'
                member.size = 0
            archive.addfile(member, None if link else io.BytesIO(payload))
            if extra:
                member = tarfile.TarInfo('dockpipe-go-sdk/' + extra)
                archive.addfile(member, io.BytesIO(b''))
        inventory = [{'path': name, 'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}]
        manifest = {'schema': 1, 'module': 'dockpipe', 'files': inventory,
                    'source_digest': hashlib.sha256(json.dumps(inventory, separators=(',', ':')).encode()).hexdigest(),
                    'sha256': hashlib.sha256(archive_path.read_bytes()).hexdigest(), 'bytes': archive_path.stat().st_size}
        manifest_path = directory / 'sdk.json'
        manifest_path.write_text(json.dumps(manifest))
        return manifest_path, archive_path, hashlib.sha256(manifest_path.read_bytes()).hexdigest()

    def test_valid_and_immutable_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            args = self.fixture(directory)
            destination = directory / 'sdk'
            candidate.unpack_sdk(*args, destination)
            self.assertEqual((destination / 'go.mod').read_bytes(), b'module dockpipe\n')
            with self.assertRaisesRegex(ValueError, 'fresh SDK destination'):
                candidate.unpack_sdk(*args, destination)

    def test_rejected_inputs_leave_no_published_tree(self):
        cases = ['untrusted_manifest', 'corrupt_archive', 'traversal', 'private', 'symlink', 'unlisted', 'member_digest', 'missing']
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                name = '../escaped' if case == 'traversal' else 'packages/dorkpipe/source.go' if case == 'private' else 'go.mod'
                manifest, archive, digest = self.fixture(directory, name=name, extra='unexpected' if case == 'unlisted' else None, link=case == 'symlink')
                if case == 'untrusted_manifest':
                    digest = '0' * 64
                elif case == 'corrupt_archive':
                    archive.write_bytes(archive.read_bytes() + b'changed')
                elif case in ['member_digest', 'missing']:
                    metadata = json.loads(manifest.read_text())
                    if case == 'member_digest':
                        metadata['files'][0]['sha256'] = '0' * 64
                    else:
                        metadata['files'][0]['path'] = 'absent'
                    metadata['source_digest'] = hashlib.sha256(json.dumps(metadata['files'], separators=(',', ':')).encode()).hexdigest()
                    manifest.write_text(json.dumps(metadata))
                    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
                destination = directory / 'sdk'
                with self.assertRaises(ValueError):
                    candidate.unpack_sdk(manifest, archive, digest, destination)
                self.assertFalse(destination.exists())
                self.assertFalse((directory / 'escaped').exists())


if __name__ == '__main__':
    unittest.main()
