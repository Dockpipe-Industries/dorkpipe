"""Offline authenticated delivery, capacity and committed-input rejection checks."""
import copy
import hashlib
import io
import json
from pathlib import Path
import tarfile
import time
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

import fetch_sdk_release as delivery


class Response(io.BytesIO):
    status = 200

    def __init__(self, payload, length=None):
        super().__init__(payload)
        self.headers = {} if length is None else {'Content-Length': str(length)}


class Opener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def redirect(location):
    return urllib.error.HTTPError('https://api.github.com/asset', 302, 'Found', {'Location': location}, io.BytesIO())


class ReleaseDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / 'release').mkdir()
        raw = b'module dockpipe\n'
        files = [{'path': 'go.mod', 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}]
        source_digest = hashlib.sha256(json.dumps(files, separators=(',', ':')).encode()).hexdigest()
        archive_buffer = io.BytesIO()
        with tarfile.open(fileobj=archive_buffer, mode='w:gz') as archive:
            member = tarfile.TarInfo('dockpipe-go-sdk/go.mod')
            member.size = len(raw)
            archive.addfile(member, io.BytesIO(raw))
        self.archive = archive_buffer.getvalue()
        manifest = {
            'schema': 1, 'module': 'dockpipe', 'files': files,
            'sdk_version': '0.1.0-source.' + source_digest[:16],
            'source_commit': 'a' * 40, 'source_digest': source_digest,
            'sha256': hashlib.sha256(self.archive).hexdigest(), 'bytes': len(self.archive),
        }
        self.manifest = json.dumps(manifest).encode()
        self.lock = {
            'schema': 1, 'dockpipe_go_sdk': {
                'version': manifest['sdk_version'], 'source_commit': manifest['source_commit'],
                'source_digest': source_digest, 'archive_sha256': manifest['sha256'],
                'manifest_sha256': hashlib.sha256(self.manifest).hexdigest(),
            },
        }
        stem = 'dockpipe-go-sdk-' + source_digest[:16]
        self.source = {'schema': 1, 'repository': 'fixture/private-sdk',
                       'tag': 'dockpipe-go-sdk-' + manifest['sdk_version'],
                       'manifest_asset': stem + '.json', 'archive_asset': stem + '.tar.gz'}
        self.release = {'tag_name': self.source['tag'], 'draft': False, 'assets': [
            {'id': 11, 'name': self.source['manifest_asset'], 'state': 'uploaded', 'size': len(self.manifest)},
            {'id': 12, 'name': self.source['archive_asset'], 'state': 'uploaded', 'size': len(self.archive)},
        ]}
        self.write_locks()
        self.output = self.root / 'download'

    def write_locks(self):
        (self.root / 'release/dependencies.lock.json').write_text(json.dumps(self.lock))
        (self.root / 'release/sdk-source.lock.json').write_text(json.dumps(self.source))

    def client(self, release=None, manifest=None, archive=None):
        opener = Opener([Response(json.dumps(release or self.release).encode()),
                         Response(self.manifest if manifest is None else manifest),
                         Response(self.archive if archive is None else archive)])
        return delivery.GitHubDownload('test-token', opener), opener

    def test_locked_release_assets_verified_without_go(self):
        client, opener = self.client()
        with patch.object(delivery.go_candidate.subprocess, 'run') as go:
            delivery.fetch(self.root, self.output, 'test-token', client)
            go.assert_not_called()
        self.assertEqual((self.output / 'sdk.json').read_bytes(), self.manifest)
        self.assertEqual((self.output / 'sdk.tar.gz').read_bytes(), self.archive)
        self.assertEqual({path.name for path in self.output.iterdir()}, {'sdk.json', 'sdk.tar.gz'})
        self.assertEqual([request.full_url for request, _ in opener.requests], [
            f"https://api.github.com/repos/fixture/private-sdk/releases/tags/{self.source['tag']}",
            'https://api.github.com/repos/fixture/private-sdk/releases/assets/11',
            'https://api.github.com/repos/fixture/private-sdk/releases/assets/12',
        ])

    def test_public_release_download_without_token(self):
        _, opener = self.client()
        client = delivery.GitHubDownload('', opener)
        delivery.fetch(self.root, self.output, '', client)
        self.assertEqual((self.output / 'sdk.json').read_bytes(), self.manifest)
        self.assertEqual((self.output / 'sdk.tar.gz').read_bytes(), self.archive)
        self.assertTrue(opener.requests)
        self.assertTrue(all(request.get_header('Authorization') is None
                            for request, _ in opener.requests))
        redirect_opener = Opener([
            redirect('https://release-assets.githubusercontent.com/signed?sig=opaque'),
            Response(b'asset')])
        public = delivery.GitHubDownload('', redirect_opener)
        self.assertEqual(public.get('https://api.github.com/asset', 100, asset=True), b'asset')
        self.assertTrue(all(request.get_header('Authorization') is None
                            for request, _ in redirect_opener.requests))

    def test_authentication_stops_at_asset_redirect(self):
        opener = Opener([redirect('https://release-assets.githubusercontent.com/signed?sig=opaque'), Response(b'asset')])
        client = delivery.GitHubDownload('private-token', opener)
        self.assertEqual(client.get('https://api.github.com/asset', 100, asset=True), b'asset')
        initial, redirected = [request for request, _ in opener.requests]
        self.assertEqual(initial.get_header('Authorization'), 'Bearer private-token')
        self.assertIsNone(redirected.get_header('Authorization'))
        self.assertTrue(all(0 < timeout <= delivery.REQUEST_TIMEOUT for _, timeout in opener.requests))

    def test_wrong_redirect_hosts_schemes_and_metadata_redirects_rejected(self):
        for location in ['http://release-assets.githubusercontent.com/file', 'https://evil.example/file',
                         'https://api.github.com/file', 'https://user:pass@release-assets.githubusercontent.com/file',
                         'https://release-assets.githubusercontent.com:444/file']:
            with self.subTest(location=location):
                opener = Opener([redirect(location)])
                with self.assertRaises(ValueError):
                    delivery.GitHubDownload('token', opener).get('https://api.github.com/asset', 100, asset=True)
                self.assertEqual(len(opener.requests), 1)
        with self.assertRaises(ValueError):
            delivery.GitHubDownload('token', Opener([redirect('https://release-assets.githubusercontent.com/file')])).get('https://api.github.com/meta', 100)

    def test_credentials_never_sent_to_arbitrary_initial_host(self):
        opener = Opener([])
        with self.assertRaises(ValueError):
            delivery.GitHubDownload('token', opener).get('https://evil.example/file', 100)
        self.assertEqual(opener.requests, [])

    def test_response_size_and_truncation_bounds(self):
        for response in [Response(b'abcde'), Response(b'a', length=5), Response(b'a', length=3)]:
            with self.subTest(headers=response.headers):
                with self.assertRaises(ValueError):
                    delivery.GitHubDownload('token', Opener([response])).get('https://api.github.com/meta', 4)

    def test_process_deadline_interrupts_blocking_io(self):
        stderr = io.StringIO()
        started = time.monotonic()
        with patch.object(delivery, 'TOTAL_SECONDS', 1):
            with patch.object(delivery, 'fetch', side_effect=lambda *args: time.sleep(3)):
                with patch('sys.argv', ['fetch_sdk_release.py', '--output', str(self.output)]):
                    with patch('sys.stderr', stderr), self.assertRaises(SystemExit) as outcome:
                        delivery.main()
        self.assertEqual(outcome.exception.code, 1)
        self.assertLess(time.monotonic() - started, 2)
        self.assertIn('Locked SDK release fetch failed', stderr.getvalue())

    def test_cli_errors_do_not_log_signed_urls_or_credentials(self):
        stderr = io.StringIO()
        failure = OSError('https://release-assets.githubusercontent.com/file?sig=private-token')
        with patch.object(delivery, 'fetch', side_effect=failure):
            with patch('sys.argv', ['fetch_sdk_release.py', '--output', str(self.output)]):
                with patch('sys.stderr', stderr), self.assertRaises(SystemExit):
                    delivery.main()
        self.assertIn('Locked SDK release fetch failed', stderr.getvalue())
        self.assertNotIn('private-token', stderr.getvalue())
        self.assertNotIn('https://', stderr.getvalue())

    def test_total_time_and_redirect_count_bounds(self):
        opener = Opener([])
        client = delivery.GitHubDownload('token', opener, clock=iter([0, 121]).__next__)
        with self.assertRaisesRegex(ValueError, 'time limit'):
            client.get('https://api.github.com/meta', 4)
        self.assertEqual(opener.requests, [])
        opener = Opener([redirect('https://release-assets.githubusercontent.com/file') for _ in range(4)])
        with self.assertRaisesRegex(ValueError, 'redirect limit'):
            delivery.GitHubDownload('token', opener).get('https://api.github.com/asset', 4, asset=True)
        self.assertTrue(all(request.get_header('Authorization') is None for request, _ in opener.requests[1:]))

    def test_missing_wrong_duplicate_and_oversized_assets_rejected_before_download(self):
        for scenario in ['missing', 'wrong-name', 'duplicate', 'oversized', 'wrong-tag', 'draft']:
            with self.subTest(scenario=scenario):
                release = copy.deepcopy(self.release)
                if scenario == 'missing':
                    release['assets'].pop()
                elif scenario == 'wrong-name':
                    release['assets'][0]['name'] = 'latest.json'
                elif scenario == 'duplicate':
                    release['assets'].append(release['assets'][0])
                elif scenario == 'oversized':
                    release['assets'][1]['size'] = delivery.go_candidate.MAX_ARCHIVE_BYTES + 1
                elif scenario == 'wrong-tag':
                    release['tag_name'] = 'latest'
                else:
                    release['draft'] = True
                client, opener = self.client(release=release)
                with self.assertRaises(ValueError):
                    delivery.fetch(self.root, self.output, 'token', client)
                self.assertEqual(len(opener.requests), 1)
                self.assertFalse(self.output.exists())

    def test_asset_digest_rejection_precedes_unpack_and_go(self):
        for manifest, archive in [(b'x' + self.manifest[1:], None), (None, b'x' + self.archive[1:])]:
            with self.subTest(manifest=manifest):
                client, _ = self.client(manifest=manifest, archive=archive)
                with patch.object(delivery.go_candidate, 'unpack_sdk') as unpack:
                    with patch.object(delivery.go_candidate.subprocess, 'run') as go:
                        with self.assertRaises(ValueError):
                            delivery.fetch(self.root, self.output, 'token', client)
                        unpack.assert_not_called()
                        go.assert_not_called()
                self.assertFalse(self.output.exists())

    def test_descriptor_drift_and_malformed_token_rejected(self):
        for key, value in [('repository', '../private'), ('tag', 'latest'), ('manifest_asset', 'arbitrary.json')]:
            with self.subTest(key=key):
                original = self.source.copy()
                self.source[key] = value
                self.write_locks()
                with self.assertRaises(ValueError):
                    delivery.load_source(self.root)
                self.source = original
        with self.assertRaises(ValueError):
            delivery.GitHubDownload('token\nwith-control')


if __name__ == '__main__':
    unittest.main()
