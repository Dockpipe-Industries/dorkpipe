"""Offline source-lock and single-member archive bootstrap verification."""
import copy
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest


SOURCE_ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((SOURCE_ROOT / "release/toolchains.lock.json").read_text())
EXECUTABLE = b"#!/bin/sh\nexit 0\n"


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        scripts = self.root / ".github/scripts"
        scripts.mkdir(parents=True)
        for name in ["bootstrap-dockpipe.sh", "bootstrap-dockpipe.py"]:
            shutil.copyfile(SOURCE_ROOT / ".github/scripts" / name, scripts / name)
        (self.root / "release").mkdir()
        self.lock_path = self.root / "release/toolchains.lock.json"
        self.archive = self.root / "fixture.tar.gz"
        self.curl = self.root / "curl"
        self.curl.write_text("""#!/usr/bin/env python3
import os
from pathlib import Path
import sys
arguments = sys.argv[1:]
assert arguments[arguments.index('--proto') + 1] == '=https'
assert arguments[arguments.index('--proto-redir') + 1] == '=https'
assert arguments[arguments.index('--max-time') + 1] == '120'
assert arguments[arguments.index('--max-filesize') + 1] == str(128 << 20)
output = arguments[arguments.index('--output') + 1]
Path(output).write_bytes(Path(os.environ['REFERENCE_ARCHIVE']).read_bytes())
Path(os.environ['CURL_CALLED']).touch()
""")
        self.curl.chmod(0o755)
        self.environment = dict(os.environ)
        self.environment.pop("DOCKPIPE_CLI_URL", None)
        self.environment.pop("DOCKPIPE_CLI_SHA256", None)
        self.environment.update(
            PATH=str(self.root) + os.pathsep + os.environ["PATH"],
            RUNNER_TEMP=str(self.root),
            GITHUB_ENV=str(self.root / "github.env"),
            GITHUB_PATH=str(self.root / "github.path"),
            REFERENCE_ARCHIVE=str(self.archive),
            CURL_CALLED=str(self.root / "curl.called"),
        )

    def fixture(self, names=None, member_type=tarfile.REGTYPE):
        with tarfile.open(self.archive, "w:gz", format=tarfile.USTAR_FORMAT) as archive:
            for name in names or ["dockpipe"]:
                member = tarfile.TarInfo(name)
                member.type = member_type
                if member_type == tarfile.REGTYPE:
                    member.size = len(EXECUTABLE)
                    archive.addfile(member, io.BytesIO(EXECUTABLE))
                else:
                    member.linkname = "../../outside"
                    archive.addfile(member)
        lock = copy.deepcopy(LOCK)
        lock["dockpipe"]["sha256"] = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.lock_path.write_text(json.dumps(lock))
        return lock

    def run_bootstrap(self, *arguments):
        return subprocess.run(
            ["bash", str(self.root / ".github/scripts/bootstrap-dockpipe.sh"), *arguments],
            env=self.environment, capture_output=True, text=True, timeout=10,
        )

    def assert_rejected(self):
        result = self.run_bootstrap()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "github.env").exists())
        self.assertFalse((self.root / "github.path").exists())
        self.assertEqual(list(self.root.glob("dockpipe-cli.*")), [])

    def test_locked_archive_exports_verified_executable(self):
        lock = self.fixture()
        self.environment["DOCKPIPE_CLI_URL"] = lock["dockpipe"]["url"]
        self.environment["DOCKPIPE_CLI_SHA256"] = lock["dockpipe"]["sha256"]
        result = self.run_bootstrap()
        self.assertEqual(result.returncode, 0, result.stderr)
        executable = Path((self.root / "github.env").read_text().strip().removeprefix("DOCKPIPE_BIN="))
        self.assertEqual(executable.read_bytes(), EXECUTABLE)
        self.assertTrue(os.access(executable, os.X_OK))
        self.assertEqual((self.root / "github.path").read_text(), f"{executable.parent}\n")
        self.assertFalse((executable.parent / "release.tar.gz").exists())

    def test_retained_archive_is_exported_only_after_verification(self):
        self.fixture()
        result = self.run_bootstrap('--keep-archive')
        self.assertEqual(result.returncode, 0, result.stderr)
        exports = dict(line.split('=', 1) for line in (self.root / 'github.env').read_text().splitlines())
        archive = Path(exports['DOCKPIPE_RELEASE_ARCHIVE'])
        self.assertEqual(archive.read_bytes(), self.archive.read_bytes())
        self.assertEqual(Path(exports['DOCKPIPE_BIN']).parent, archive.parent)

    def test_release_tag_must_match_exact_version_and_url(self):
        for tag in ['latest', 'v9.0.0', 'v0.6.13-staging.bad', 'v0.6.13']:
            with self.subTest(tag=tag):
                lock = self.fixture()
                lock['dockpipe']['release_tag'] = tag
                self.lock_path.write_text(json.dumps(lock))
                self.assert_rejected()

    def test_default_uses_source_lock_without_overrides(self):
        self.fixture()
        result = self.run_bootstrap()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_wrong_archive_digest(self):
        lock = self.fixture()
        lock["dockpipe"]["sha256"] = "0" * 64
        self.lock_path.write_text(json.dumps(lock))
        self.assert_rejected()

    def test_override_drift_rejected_before_download(self):
        self.fixture()
        for variable in ["DOCKPIPE_CLI_URL", "DOCKPIPE_CLI_SHA256"]:
            with self.subTest(variable=variable):
                self.environment[variable] = "drift"
                self.assert_rejected()
                self.assertFalse((self.root / "curl.called").exists())
                del self.environment[variable]

    def test_unsafe_or_extra_members(self):
        for names in [["../dockpipe"], ["/dockpipe"], ["sub/dockpipe"], ["dockpipe", "extra"]]:
            with self.subTest(names=names):
                self.fixture(names)
                self.assert_rejected()
        for kind in [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.DIRTYPE, tarfile.XHDTYPE]:
            with self.subTest(kind=kind):
                self.fixture(member_type=kind)
                self.assert_rejected()

    def test_malformed_lock_and_bound(self):
        lock = self.fixture()
        for key, value in [("version", "latest"), ("platform", "darwin-arm64"),
                           ("format", "binary"), ("sha256", "z" * 64),
                           ("url", "http://example.invalid/cli"), ("url", "https://github.com/mutable")]:
            with self.subTest(key=key):
                malformed = copy.deepcopy(lock)
                malformed["dockpipe"][key] = value
                self.lock_path.write_text(json.dumps(malformed))
                self.assert_rejected()
        self.lock_path.write_text('{"schema":1,"schema":2}')
        self.assert_rejected()
        self.lock_path.write_bytes(b" " * ((64 << 10) + 1))
        self.assert_rejected()

    def test_oversized_executable_header_rejected_without_inflating_payload(self):
        lock = self.fixture()
        member = tarfile.TarInfo("dockpipe")
        member.size = (256 << 20) + 1
        self.archive.write_bytes(gzip.compress(member.tobuf(format=tarfile.USTAR_FORMAT)))
        lock["dockpipe"]["sha256"] = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.lock_path.write_text(json.dumps(lock))
        self.assert_rejected()

    def test_export_destination_failure_keeps_existing_environment(self):
        self.fixture()
        environment = self.root / "github.env"
        environment.write_text("EXISTING=value\n")
        (self.root / "github.path").mkdir()
        result = self.run_bootstrap()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(environment.read_text(), "EXISTING=value\n")
        self.assertEqual(list(self.root.glob("dockpipe-cli.*")), [])


if __name__ == "__main__":
    unittest.main()
