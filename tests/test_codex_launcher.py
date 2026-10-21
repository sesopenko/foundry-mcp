"""Verify credentials reach Codex without exporting the browser credential."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class LauncherTests(unittest.TestCase):
    def test_loads_only_caller_token_from_local_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scripts").mkdir()
            graph = root / "scripts/code-graph-setup.sh"
            graph.write_text('#!/bin/sh\n[ "$1" = --check ]\n')
            graph.chmod(0o755)
            launcher = root / "scripts/codex.sh"
            launcher.write_text(Path("scripts/codex.sh").read_text())
            launcher.chmod(0o755)
            setup = root / "scripts/docs-setup.sh"
            setup.write_text('#!/bin/sh\ntouch "' + str(root / 'docs-ready') + '"\n')
            setup.chmod(0o755)
            server = root / "scripts/server.sh"
            server.write_text('#!/bin/sh\ntest -f "' + str(root / 'docs-ready') + '"\n')
            server.chmod(0o755)
            (root / ".venv/bin").mkdir(parents=True)
            (root / ".venv/bin/python").symlink_to(sys.executable)
            fake_codex = root / "codex"
            fake_codex.write_text('#!/bin/sh\n[ "$FOUNDRY_MCP_CALLER_TOKEN" = "test-caller" ] || exit 1\n[ -z "${FOUNDRY_MCP_BROWSER_TOKEN:-}" ] || exit 2\n')
            fake_codex.chmod(0o755)
            (root / ".env.mcp").write_text("FOUNDRY_MCP_CALLER_TOKEN=test-caller\nFOUNDRY_MCP_BROWSER_TOKEN=test-browser\n")
            environment = {key: value for key, value in os.environ.items() if not key.startswith("FOUNDRY_MCP_")}
            environment["PATH"] = str(root) + os.pathsep + environment["PATH"]
            result = subprocess.run([str(launcher), "--help"], env=environment, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("test-caller", result.stdout + result.stderr)
            self.assertNotIn("test-browser", result.stdout + result.stderr)

    def test_failed_documentation_setup_stops_before_codex_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scripts = root / "scripts"
            scripts.mkdir()
            graph = scripts / "code-graph-setup.sh"
            graph.write_text('#!/bin/sh\nexit 0\n')
            graph.chmod(0o755)
            launcher = scripts / "codex.sh"
            launcher.write_text(Path("scripts/codex.sh").read_text())
            setup = scripts / "docs-setup.sh"
            setup.write_text("#!/bin/sh\nexit 42\n")
            setup.chmod(0o755)
            result = subprocess.run(["bash", str(launcher)], capture_output=True,
                                    text=True, timeout=5)
            self.assertEqual(result.returncode, 42)

    def test_code_only_from_outside_root_preserves_arguments_and_skips_stack(self):
        import json
        with tempfile.TemporaryDirectory(prefix='graph path ') as directory:
            root = Path(directory)
            scripts = root / 'scripts'
            scripts.mkdir()
            launcher = scripts / 'codex.sh'
            launcher.write_text(Path('scripts/codex.sh').read_text())
            graph = scripts / 'code-graph-setup.sh'
            graph.write_text('#!/bin/sh\n[ "$1" = --check ]\n')
            graph.chmod(0o755)
            codex = root / 'codex'
            codex.write_text('#!' + sys.executable + '\nimport json, os, sys\nprint(json.dumps([os.getcwd(), sys.argv[1:]]))\n')
            codex.chmod(0o755)
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ['PATH'])
            result = subprocess.run(['bash', str(launcher), '--code-only', 'resume', 'two words'], cwd='/tmp', env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            cwd, args = json.loads(result.stdout)
            self.assertEqual(cwd, str(root))
            self.assertEqual(args[-2:], ['resume', 'two words'])
            self.assertIn('workspace-write', args)
            self.assertIn('on-request', args)
            for server in ('grounded-docs', 'foundry-vtt', 'chrome-devtools'):
                self.assertIn(f'mcp_servers.{server}.enabled=false', args)

    def test_browser_launcher_rejects_code_only_before_starting_browser(self):
        result = subprocess.run(['bash', 'scripts/codex-dev.sh', '--code-only'], text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('codex.sh --code-only', result.stderr)
