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
            launcher = root / "scripts/codex.sh"
            launcher.write_text(Path("scripts/codex.sh").read_text())
            launcher.chmod(0o755)
            server = root / "scripts/server.sh"
            server.write_text("#!/bin/sh\nexit 0\n")
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
