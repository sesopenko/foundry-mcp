"""Offline wrapper contracts; native integration is opt-in and runs in Debian CI."""
import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parent.parent


class WrapperTests(unittest.TestCase):
    def test_verification_uses_fixed_log_and_stops_at_first_failure(self):
        with tempfile.TemporaryDirectory(prefix='verify path ') as d:
            root = Path(d)
            (root / 'scripts').mkdir()
            shutil.copy(ROOT / 'scripts/code-graph-verify.sh', root / 'scripts')
            setup = root / 'scripts/code-graph-setup.sh'
            setup.write_text('#!/bin/sh\necho intentional-first-check-failure\nexit 42\n')
            setup.chmod(0o755)
            r = subprocess.run(['bash', str(root / 'scripts/code-graph-verify.sh')], cwd='/tmp', capture_output=True, text=True)
            self.assertEqual(r.returncode, 42, r.stderr)
            log = root / '.local/code-graph/verification.log'
            self.assertIn('intentional-first-check-failure', log.read_text())
            self.assertNotIn('No such file', log.read_text())
            self.assertIn(str(log), r.stdout)

    def test_no_worktree_fallback_or_symlinked_graph(self):
        with tempfile.TemporaryDirectory(prefix='graph worktree ') as d:
            root = Path(d)
            (root / 'scripts').mkdir()
            shutil.copy(ROOT / 'scripts/code-graph.sh', root / 'scripts')
            for command in ('serve', 'show', 'health-check'):
                r = subprocess.run(['bash', str(root / 'scripts/code-graph.sh'), command], cwd='/tmp', capture_output=True, text=True)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn('missing local index', r.stderr)
            (root / '.code-graph').symlink_to(ROOT / '.code-graph', target_is_directory=True)
            r = subprocess.run(['bash', str(root / 'scripts/code-graph.sh'), 'incremental-index'], capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('not a symlink', r.stderr)


@unittest.skipUnless(os.environ.get('CODE_GRAPH_INTEGRATION') == '1', 'native engine tests: CODE_GRAPH_INTEGRATION=1')
class NativeTests(unittest.IsolatedAsyncioTestCase):
    async def test_pins_repeatability_exclusions_relationships_and_freshness(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        with tempfile.TemporaryDirectory(prefix='graph fixture ') as d:
            root = Path(d)
            (root / 'scripts').mkdir()
            subprocess.run(['git', 'init', '-q', d], check=True)
            for name in ('code-graph.sh', 'resolve-code-graph.cjs', 'code-graph-setup.sh', 'code-graph-doctor.sh'):
                shutil.copy(ROOT / 'scripts' / name, root / 'scripts')
            for name in ('package.json', 'package-lock.json', '.gitignore', '.ignore', '.code-graph.toml'):
                shutil.copy(ROOT / name, root / name)
            shutil.copytree(ROOT / 'node_modules', root / 'node_modules')
            def run(script, *args, ok=True, env=None):
                r = subprocess.run(['bash', str(root / 'scripts' / script), *args], cwd='/tmp', capture_output=True, text=True, timeout=130, env=env)
                if ok:
                    self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
                else:
                    self.assertNotEqual(r.returncode, 0, r.stderr)
                return r
            run('code-graph-setup.sh', '--check', ok=False)
            # An existing installation needs a verified fingerprint, supplied by explicit setup.
            (root / 'leaf.py').write_text('def graph_leaf():\n    return 1\n')
            (root / 'caller.py').write_text('from leaf import graph_leaf\ndef graph_caller():\n    return graph_leaf()\n')
            (root / 'leaf.js').write_text('export function jsLeaf() { return 1; }\n')
            (root / 'caller.js').write_text('import {jsLeaf} from "./leaf.js";\nexport function jsCaller() { return jsLeaf(); }\n')
            (root / 'tests').mkdir()
            (root / 'tests/test_fixture.py').write_text('def test_graph_fixture():\n    return True\n')
            for directory in ('data', 'foundry-data', '.local', '.venv', 'node_modules/ignored', 'pdf-library', 'pdf-state', 'dist', 'build', '.browser-dev'):
                path = root / directory
                path.mkdir(exist_ok=True, parents=True)
                (path / 'excluded.py').write_text('def excluded_python_sentinel(): pass\n')
                (path / 'excluded.js').write_text('function excludedJavascriptSentinel() {}\n')
            original = (root / 'package-lock.json').read_bytes()
            run('code-graph-setup.sh')
            ignored = root / 'node_modules/ignored'
            ignored.mkdir()
            (ignored / 'sentinel.py').write_text('def excluded_python_sentinel(): pass\n')
            (ignored / 'sentinel.js').write_text('function excludedJavascriptSentinel() {}\n')
            r = run('code-graph-setup.sh', '--check')
            self.assertIn('skipping npm', r.stderr)
            self.assertEqual(original, (root / 'package-lock.json').read_bytes())
            # Exact local resolution ignores an unrelated shared cache executable.
            env = dict(os.environ, HOME=str(root / 'fake-home'))
            cache = Path(env['HOME']) / '.cache/code-graph'
            cache.mkdir(parents=True)
            (cache / 'code-graph-mcp').write_text('#!/bin/sh\necho 99.0.0\n')
            (cache / 'code-graph-mcp').chmod(0o755)
            r = subprocess.run(['node', str(root / 'scripts/resolve-code-graph.cjs')], env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(r.stdout.strip().startswith(str(root / 'node_modules') + '/'))
            async with stdio_client(StdioServerParameters(command='bash', args=[str(root / 'scripts/code-graph.sh'), 'serve'], cwd=d)) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    async def query(tool, **args):
                        r = await session.call_tool(tool, args)
                        self.assertFalse(r.isError, r)
                        return '\n'.join(c.text for c in r.content if c.type == 'text')
                    for symbol, file in (('graph_leaf', 'leaf.py'), ('jsLeaf', 'leaf.js'), ('test_graph_fixture', 'tests/test_fixture.py')):
                        text = await query('get_ast_node', symbol_name=symbol, file_path=file, compact=True)
                        self.assertIn(file, text)
                        self.assertIn(symbol, text)
                    for symbol, file, caller in (('graph_leaf', 'leaf.py', 'graph_caller'), ('jsLeaf', 'leaf.js', 'jsCaller')):
                        text = await query('get_call_graph', symbol_name=symbol, file_path=file, direction='both', depth=2, compact=True, include_tests=True)
                        self.assertIn(caller, text)
                    text = await query('ast_search', query='excluded', limit=100)
                    self.assertNotIn('excluded_python_sentinel', text)
                    self.assertNotIn('excludedJavascriptSentinel', text)
                    # The primary lock is genuinely owned; warm setup must not wait or index.
                    start = time.monotonic()
                    r = run('code-graph-setup.sh', '--check')
                    self.assertIn('active server owns freshness', r.stderr)
                    self.assertLess(time.monotonic() - start, 10)
                    async def eventually(symbol, file, present):
                        deadline = time.monotonic() + 15
                        while True:
                            r = await session.call_tool('get_ast_node', {'symbol_name': symbol, 'file_path': file, 'compact': False})
                            text = '\n'.join(c.text for c in r.content if c.type == 'text')
                            found = not r.isError and 'code_content' in text and symbol in text and file in text
                            if found == present:
                                return text
                            if time.monotonic() > deadline:
                                self.fail(text)
                            await asyncio.sleep(.3)
                    created = root / 'fresh.py'
                    created.write_text('def fresh_one():\n    return 123\n')
                    await eventually('fresh_one', 'fresh.py', True)
                    created.write_text('def fresh_two():\n    return 456\n')
                    await eventually('fresh_two', 'fresh.py', True)
                    await eventually('fresh_one', 'fresh.py', False)
                    created.rename(root / 'renamed.py')
                    await eventually('fresh_two', 'renamed.py', True)
                    (root / 'renamed.py').unlink()
                    await eventually('fresh_two', 'renamed.py', False)
            # A real linked worktree must never borrow the main checkout graph.
            def git(*args):
                return subprocess.run(
                    ['git', '-c', 'user.name=Graph Fixture', '-c',
                     'user.email=fixture@example.invalid', '-c', 'commit.gpgsign=false',
                     '-c', 'core.hooksPath=/dev/null', *args],
                    cwd=root, check=True, capture_output=True, text=True, timeout=15,
                )
            git('add', '--', 'scripts', 'package.json', 'package-lock.json',
                '.gitignore', '.ignore', '.code-graph.toml', 'leaf.py', 'caller.py',
                'leaf.js', 'caller.js', 'tests')
            git('commit', '-qm', 'Disposable graph fixture')
            linked = root / '.local/linked worktree'
            git('worktree', 'add', '--detach', str(linked))
            r = subprocess.run(['bash', str(linked / 'scripts/code-graph.sh'),
                                'show', 'graph_leaf', '--json'], cwd='/tmp',
                               capture_output=True, text=True, timeout=10)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('missing local index', r.stderr)
            r = subprocess.run(['bash', str(linked / 'scripts/code-graph-setup.sh')],
                               cwd='/tmp', capture_output=True, text=True, timeout=130)
            self.assertEqual(r.returncode, 0, r.stderr)
            main_db = root / '.code-graph/index.db'
            linked_db = linked / '.code-graph/index.db'
            self.assertTrue(linked_db.is_file())
            self.assertFalse(main_db.samefile(linked_db))
            r = subprocess.run(['bash', str(linked / 'scripts/code-graph.sh'),
                                'show', 'graph_leaf', '--file', 'leaf.py', '--json'],
                               cwd='/tmp', capture_output=True, text=True, timeout=10)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout)[0]['file_path'], 'leaf.py')
            marker = root / '.local/code-graph/dependencies.sha256'
            marker.write_text('stale\n')
            r = run('code-graph-setup.sh', '--check', ok=False)
            self.assertIn('run ./scripts/dev-setup.sh', r.stderr)
            self.assertEqual(marker.read_text(), 'stale\n')
            # Interrupted/failed npm reconciliation cannot leave a readiness marker.
            fake_bin = root / 'fake-bin'
            fake_bin.mkdir()
            npm_version = subprocess.check_output(['npm', '--version'], text=True).strip()
            npm = fake_bin / 'npm'
            npm.write_text('#!/bin/sh\nif [ "$1" = --version ]; then echo ' + npm_version + '; else exit 31; fi\n')
            npm.chmod(0o755)
            env = dict(os.environ, PATH=str(fake_bin) + os.pathsep + os.environ['PATH'])
            run('code-graph-setup.sh', ok=False, env=env)
            self.assertEqual(marker.read_text(), '')
            self.assertEqual(original, (root / 'package-lock.json').read_bytes())
            binary = next((root / 'node_modules/@sdsrs').glob('code-graph-linux-*/code-graph-mcp'))
            binary.rename(binary.with_suffix('.missing'))
            run('code-graph-setup.sh', '--check', ok=False)
