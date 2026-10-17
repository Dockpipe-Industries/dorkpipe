"""Boundary checks for the standalone shell fixture inputs."""
from pathlib import Path
from types import SimpleNamespace
import os
import tempfile
import unittest
from unittest.mock import patch

import run_shell_candidate as shell


class ShellFixtureInputTests(unittest.TestCase):
    def test_shell_fixture_excludes_outer_workflow_and_ci_bindings(self):
        injected = {
            'DOCKPIPE_BIN': '/outer/dockpipe',
            'DOCKPIPE_CI_ANALYSIS_DIR': '/outer/analysis',
            'DOCKPIPE_CI_ARTIFACT_SCOPE': 'workflow:sdk.candidate',
            'DOCKPIPE_WORKDIR': '/outer/source',
            'CI': 'true',
            'GOWORK': '/outer/go.work',
            'DORKPIPE_TEST_PIPEON_SOURCE': '/outer/editor',
        }
        with patch.dict(os.environ, injected):
            environment = shell.shell_test_environment(Path('/fixture/dockpipe'))
        self.assertEqual(environment['DOCKPIPE_BIN'], '/fixture/dockpipe')
        self.assertEqual(environment['GOPROXY'], 'off')
        for name in injected.keys() - {'DOCKPIPE_BIN'}:
            self.assertNotIn(name, environment)

    def test_workspace_graph_uses_fixture_root_and_checks_offline_identity(self):
        graph = (b'dockpipe golang.org/x/mod@v0.31.0\n'
                 b'golang.org/x/tools@v0.45.0 github.com/google/go-cmp@v0.6.0\n')
        source = Path('/fixture/source')

        def run_go(arguments, **options):
            self.assertEqual(options['cwd'], source)
            self.assertEqual(options['env']['GOWORK'], 'auto')
            self.assertEqual(options['env']['GOFLAGS'], '-mod=readonly')
            if arguments == ['go', 'mod', 'graph']:
                options['stdout'].write(graph)
            else:
                self.assertEqual(arguments, ['go', 'mod', 'download', 'all'])

        with patch.object(shell.subprocess, 'run', side_effect=run_go) as commands:
            shell.prefetch_shell_workspace_dependencies(source, 'go')
        self.assertEqual(commands.call_count, 4)
        self.assertEqual(commands.call_args_list[0].kwargs['env']['GOPROXY'],
                         'https://proxy.golang.org')
        self.assertEqual(commands.call_args_list[1].kwargs['env']['GOPROXY'],
                         'https://proxy.golang.org')
        self.assertEqual(commands.call_args_list[2].kwargs['env']['GOPROXY'], 'off')
        self.assertEqual(commands.call_args_list[3].kwargs['env']['GOPROXY'], 'off')

    def test_private_paths_cannot_escape_the_fixture(self):
        for name in ('../outside', '/absolute', 'nested/../outside', 'nested\\outside'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'Unsafe private'):
                shell.private_path(name)

    def test_linked_and_oversized_private_files_are_rejected_before_copy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outside = root / 'outside'
            outside.write_bytes(b'outside')
            linked = root / 'linked'
            linked.symlink_to(outside)
            with self.assertRaisesRegex(ValueError, 'Expected regular file'):
                shell.copy_regular(linked, root / 'copied')
            self.assertFalse((root / 'copied').exists())

            with patch.object(shell, 'MAX_FILE_BYTES', 4):
                with self.assertRaisesRegex(ValueError, 'capacity'):
                    shell.copy_regular(outside, root / 'copied')
            self.assertFalse((root / 'copied').exists())

    def test_private_inventory_count_is_bounded(self):
        with patch.object(shell, 'MAX_PRIVATE_FILES', 1), patch.object(shell.subprocess, 'run') as run:
            run.return_value = SimpleNamespace(stdout=b'one\0two\0')
            with self.assertRaisesRegex(ValueError, 'capacity'):
                shell.tracked_paths(Path('/unused'))


if __name__ == '__main__':
    unittest.main()
