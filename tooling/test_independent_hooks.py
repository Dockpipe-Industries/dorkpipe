"""Offline fixed-location preparation receipt and package hook verification."""
import argparse
import copy
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
from unittest.mock import patch

import candidate_contract as contract
import go_candidate
import install_package_candidate as installer


STAGED_ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = STAGED_ROOT / '.github/scripts/bootstrap-dockpipe.py'


class IndependentHookTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.environment = dict(os.environ)
        for variable in ['DOCKPIPE_CLI_URL', 'DOCKPIPE_CLI_SHA256', 'DOCKPIPE_PACKAGE_ROOT',
                         'GOOS', 'GOARCH', 'DORKPIPE_STACK_GOARCH']:
            self.environment.pop(variable, None)
        dockpipe = self.root / 'fixture-dockpipe'
        dockpipe.write_text('''#!/usr/bin/env python3
from pathlib import Path
import sys
if sys.argv[1] == 'sdk':
    print('dockpipe_sdk() { [ "$*" = "path state tooling bin" ] || return 1; printf "%s\\n" "$FIXTURE_TOOLING_OUTPUT"; }')
else:
    assert sys.argv[1:5] == ['scope', 'workflow', 'package.candidate', 'prepared']
    assert sys.argv[5] == '--workdir'
    print(Path(sys.argv[6]) / 'prepared-workflow-scope')
''')
        dockpipe.chmod(0o755)
        self.environment['DOCKPIPE_BIN'] = str(dockpipe)
        environment_patch = patch.dict(os.environ, self.environment, clear=True)
        environment_patch.start()
        self.addCleanup(environment_patch.stop)
        for module in contract.MODULES:
            directory = self.root / module
            directory.mkdir(parents=True)
            (directory / 'go.mod').write_text('module fixture\n')
            (directory / 'go.sum').write_text('')
            (directory / 'main.go').write_text('package main\n')
            (directory / 'rules.json').write_text('{"embedded":true}')
        for manifest in contract.MANIFESTS:
            (self.root / manifest).write_text('schema: 1\nversion: 0.6.2\n')
        (self.root / 'release').mkdir()
        self.sdk_lock = {
            'schema': 1, 'dockpipe_go_sdk': {
                'version': '0.1.0-source.' + 'a' * 16, 'source_digest': 'a' * 64,
                'source_commit': 'b' * 40, 'manifest_sha256': 'c' * 64, 'archive_sha256': 'd' * 64,
            },
        }
        (self.root / 'release/dependencies.lock.json').write_text(json.dumps(self.sdk_lock))
        self.archive = self.root / 'engine.tar.gz'
        with tarfile.open(self.archive, 'w:gz', format=tarfile.USTAR_FORMAT) as archive:
            executable = b'#!/bin/sh\nexit 0\n'
            member = tarfile.TarInfo('dockpipe')
            member.size = len(executable)
            archive.addfile(member, io.BytesIO(executable))
        toolchain = {
            'schema': 1, 'dockpipe': {
                'version': '0.6.11', 'platform': 'linux-amd64', 'format': 'tar.gz',
                'url': 'https://github.com/Dockpipe-Industries/dockpipe/releases/download/v0.6.11/dockpipe_0.6.11_linux_amd64.tar.gz',
                'sha256': hashlib.sha256(self.archive.read_bytes()).hexdigest(),
            },
        }
        (self.root / 'release/toolchains.lock.json').write_text(json.dumps(toolchain))
        fixture_files = (*contract.PREPARATION_CODE, 'packages/dorkpipe-mcp/assets/scripts/build-source.sh')
        for relative in fixture_files:
            source = STAGED_ROOT / relative
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        self.candidate = contract.prepared_directory(self.root)
        binaries = self.candidate / 'bin'
        binaries.mkdir(parents=True)
        entries = []
        for name in contract.TOOLS:
            path = binaries / name
            path.write_bytes(f'prepared {name}'.encode())
            size, digest = contract.file_digest(path, contract.MAX_BINARY_BYTES)
            entries.append({'name': name, 'bytes': size, 'sha256': digest})
        self.receipt = {
            'schema': 1, 'sdk_source_digest': 'a' * 64, 'sdk_manifest_sha256': 'c' * 64,
            'distribution_approved': False, 'tests_requested': True,
            'target': {'os': 'linux', 'arch': 'amd64'}, 'source': contract.source_identity(self.root),
            'sdk_lock': self.sdk_lock, 'binaries': entries,
        }
        self.write_receipt()

    def write_receipt(self):
        (self.candidate / 'candidate.json').write_text(json.dumps(self.receipt))

    def test_valid_contract_and_all_output_adapters(self):
        with patch.dict(os.environ, self.environment, clear=True):
            installer.verify_candidate(self.root)
            for operation, expected in [
                ('source-dorkpipe', set(contract.TOOLS) - {'mcpd'}),
                ('source-mcp', {'mcpd'}),
                ('consumer', set(contract.TOOLS) | {'dockpipe'}),
            ]:
                output = self.root / operation
                installer.install(self.root, output, operation, self.archive)
                self.assertEqual({path.name for path in output.iterdir()}, expected)
                for path in output.iterdir():
                    self.assertTrue(os.access(path, os.X_OK))

    def test_source_module_embed_version_and_lock_drift(self):
        for relative in ['packages/dorkpipe/lib/main.go', 'packages/dorkpipe/lib/rules.json',
                         'packages/dorkpipe-mcp/go.mod', 'packages/dorkpipe/package.yml',
                         'release/toolchains.lock.json', 'tooling/go_candidate.py']:
            with self.subTest(path=relative):
                path = self.root / relative
                before = path.read_bytes()
                path.write_bytes(before + b'\nchanged')
                with self.assertRaises(ValueError):
                    installer.verify_candidate(self.root)
                path.write_bytes(before)

    def test_receipt_target_sdk_and_missing_test_proof_rejected(self):
        for field, value in [
            ('target', {'os': 'linux', 'arch': 'arm64'}), ('sdk_manifest_sha256', '0' * 64),
            ('sdk_lock', {}), ('source', {}), ('tests_requested', False),
        ]:
            with self.subTest(field=field):
                before = copy.deepcopy(self.receipt)
                self.receipt[field] = value
                self.write_receipt()
                with self.assertRaises(ValueError):
                    installer.verify_candidate(self.root)
                self.receipt = before
                self.write_receipt()

    def test_missing_extra_linked_and_changed_binaries_fail_before_output(self):
        binary = self.candidate / 'bin/dorkpipe'
        original = binary.read_bytes()
        for scenario in ['missing', 'extra', 'linked', 'changed']:
            with self.subTest(scenario=scenario):
                if scenario == 'missing':
                    binary.unlink()
                elif scenario == 'extra':
                    (binary.parent / 'extra').write_bytes(b'extra')
                elif scenario == 'linked':
                    binary.unlink()
                    binary.symlink_to(self.archive)
                else:
                    binary.write_bytes(b'changed')
                output = self.root / 'rejected'
                with self.assertRaises((ValueError, FileNotFoundError)):
                    installer.install(self.root, output, 'consumer', self.archive)
                self.assertFalse(output.exists())
                if binary.exists() or binary.is_symlink():
                    binary.unlink()
                binary.write_bytes(original)
                (binary.parent / 'extra').unlink(missing_ok=True)

    def test_missing_fixed_receipt_and_arbitrary_receipt_not_accepted(self):
        (self.root / 'external-receipt.json').write_text(json.dumps(self.receipt))
        (self.candidate / 'candidate.json').unlink()
        with self.assertRaises(FileNotFoundError):
            installer.verify_candidate(self.root)

    def test_environment_target_drift_and_linked_source_rejected(self):
        for variable in ['GOOS', 'GOARCH', 'DORKPIPE_STACK_GOARCH']:
            with patch.dict(os.environ, {variable: 'wrong'}), self.assertRaises(ValueError):
                installer.verify_candidate(self.root)
        source = self.root / 'packages/dorkpipe/lib/main.go'
        source.unlink()
        source.symlink_to(self.archive)
        with self.assertRaises(ValueError):
            installer.verify_candidate(self.root)

    def test_shell_proof_code_drift_rejects_prepared_candidate(self):
        for relative in ['tooling/run_shell_candidate.py', 'workflows/sdk.candidate/assets/run.sh']:
            with self.subTest(relative=relative):
                path = self.root / relative
                original = path.read_bytes()
                path.write_bytes(original + b'\n# changed after preparation\n')
                with self.assertRaisesRegex(ValueError, 'source or version drift'):
                    installer.verify_candidate(self.root)
                path.write_bytes(original)

    def test_engine_digest_failure_publishes_no_outputs(self):
        self.archive.write_bytes(b'corrupt')
        output = self.root / 'consumer'
        with self.assertRaisesRegex(ValueError, 'engine archive'):
            installer.install(self.root, output, 'consumer', self.archive)
        self.assertFalse(output.exists())

    def test_inventory_and_receipt_capacity_rejections(self):
        with patch.object(contract, 'MAX_FILES', 1), self.assertRaisesRegex(ValueError, 'capacity'):
            contract.source_identity(self.root)
        with patch.object(contract, 'MAX_SOURCE_BYTES', 1), self.assertRaises(ValueError):
            contract.source_identity(self.root)
        with patch.object(contract, 'MAX_RECEIPT_BYTES', 1), self.assertRaises(ValueError):
            installer.verify_candidate(self.root)

    def test_fixed_workflow_scope_rejects_malformed_and_oversized_output(self):
        for value in [b'relative/path\n', b'/tmp/path\n/tmp/extra\n', b'a' * 4097]:
            with self.subTest(value=value[:30]):
                def write_scope(*arguments, **options):
                    options['stdout'].write(value)
                with patch.object(contract.subprocess, 'run', side_effect=write_scope):
                    with self.assertRaises(ValueError):
                        contract.prepared_directory(self.root)

    def assert_source_hook_contract(self, package, expected_tools):
        script = self.root / f'packages/{package}/assets/scripts/build-source.sh'
        for explicit_output in [False, True]:
            with self.subTest(explicit_output=explicit_output):
                output = self.root / f'{package}-output-{explicit_output}'
                environment = dict(self.environment, FIXTURE_TOOLING_OUTPUT=str(output))
                environment.pop('DOCKPIPE_SDK_SH', None)
                environment.pop('DOCKPIPE_SOURCE_BUILD_OUT_DIR', None)
                if explicit_output:
                    environment['DOCKPIPE_SOURCE_BUILD_OUT_DIR'] = str(output)
                result = subprocess.run(['bash', str(script)], env=environment,
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual({path.name for path in output.iterdir()}, expected_tools)
                for name in expected_tools:
                    self.assertEqual((output / name).read_bytes(), (self.candidate / 'bin' / name).read_bytes())
                    self.assertTrue(os.access(output / name, os.X_OK))

        for scenario in ['missing-receipt', 'changed-binary']:
            with self.subTest(scenario=scenario):
                output = self.root / f'{package}-rejected-{scenario}'
                output.mkdir()
                sentinel = output / 'unrelated'
                sentinel.write_bytes(b'preserve')
                binary = self.candidate / 'bin' / sorted(expected_tools)[0]
                original_binary = binary.read_bytes()
                if scenario == 'missing-receipt':
                    (self.candidate / 'candidate.json').unlink()
                else:
                    binary.write_bytes(b'corrupt prepared tool')
                environment = dict(self.environment, DOCKPIPE_SOURCE_BUILD_OUT_DIR=str(output))
                result = subprocess.run(['bash', str(script)], env=environment,
                                        capture_output=True, text=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Prepared package installation failed:', result.stderr)
                self.assertEqual({path.name for path in output.iterdir()}, {'unrelated'})
                self.assertEqual(sentinel.read_bytes(), b'preserve')
                binary.write_bytes(original_binary)
                self.write_receipt()

    def test_dorkpipe_source_hook_contract(self):
        self.assert_source_hook_contract('dorkpipe', {'dorkpipe', 'skills-render', 'orchestrate-helper'})

    def test_mcp_source_hook_contract(self):
        self.assert_source_hook_contract('dorkpipe-mcp', {'mcpd'})

    def test_source_hooks_use_public_sdk_without_internal_sdk_path_variable(self):
        output = self.root / 'sdk-owned-tooling'
        environment = dict(self.environment, FIXTURE_TOOLING_OUTPUT=str(output))
        environment.pop('DOCKPIPE_SDK_SH', None)
        environment.pop('DOCKPIPE_SOURCE_BUILD_OUT_DIR', None)
        for package in ['dorkpipe', 'dorkpipe-mcp']:
            result = subprocess.run(['bash', str(self.root / f'packages/{package}/assets/scripts/build-source.sh')],
                                    env=environment, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual({path.name for path in output.iterdir()}, set(contract.TOOLS))

    def test_source_and_compile_shell_hooks_use_owned_verifier(self):
        with patch.dict(os.environ, self.environment, clear=True):
            output = self.root / 'source-output'
            for package in ['dorkpipe', 'dorkpipe-mcp']:
                environment = dict(self.environment, DOCKPIPE_SOURCE_BUILD_OUT_DIR=str(output))
                result = subprocess.run(['bash', str(self.root / f'packages/{package}/assets/scripts/build-source.sh')],
                                        env=environment, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual({path.name for path in output.iterdir()}, set(contract.TOOLS))
            resolver = self.root / 'packages/dorkpipe/resolvers/dorkpipe'
            environment = dict(self.environment, DOCKPIPE_COMPILE_SOURCE_DIR=str(resolver),
                               DOCKPIPE_COMPILE_STAGING_DIR=str(self.root / 'stage'),
                               DOCKPIPE_COMPILE_WORKDIR=str(self.root), DOCKPIPE_RELEASE_ARCHIVE=str(self.archive))
            result = subprocess.run(['bash', str(resolver / 'assets/scripts/package-consumer-artifacts.sh')],
                                    env=environment, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual({path.name for path in (self.root / 'stage/assets/tooling/bin/linux').iterdir()}, set(contract.TOOLS) | {'dockpipe'})

    def test_build_enforces_linux_target_and_emits_source_bound_receipt(self):
        output = self.root / 'built'
        sdk_manifest = {
            'sdk_version': '0.1.0-source.' + 'a' * 16, 'source_digest': 'a' * 64,
            'source_commit': 'b' * 40, 'sha256': 'd' * 64,
        }
        args = argparse.Namespace(source=self.root, output=output, manifest=Path('unused'), archive=Path('unused'),
                                  manifest_sha256='c' * 64, go='fixture-go', tests=True, download_dependencies=False)

        def unpack(*arguments):
            sdk = arguments[-1]
            sdk.mkdir()
            (sdk / 'go.sum').write_text('')
            return sdk_manifest

        def run_go(go, module, modfile, arguments, environment):
            self.assertEqual(environment['GOOS'], 'linux')
            self.assertEqual(environment['GOARCH'], 'amd64')
            if arguments[0] == 'build':
                path = Path(arguments[arguments.index('-o') + 1])
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(b'fixture tool')

        with patch.dict(os.environ, self.environment, clear=True):
            with patch.object(go_candidate, 'unpack_sdk', side_effect=unpack):
                with patch.object(go_candidate, 'run_go', side_effect=run_go):
                    with patch.object(go_candidate.subprocess, 'run'):
                        go_candidate.build(args)
        receipt = json.loads((output / 'candidate.json').read_text())
        self.assertEqual(receipt['target'], {'os': 'linux', 'arch': 'amd64'})
        self.assertEqual(receipt['source'], contract.source_identity(self.root))
        self.assertEqual(receipt['sdk_lock'], self.sdk_lock)



if __name__ == '__main__':
    unittest.main()
