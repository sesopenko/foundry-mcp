"""Exercise service startup without accessing the host service manager."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class ServerLauncherTests(unittest.TestCase):
    def run_start(self, state, action="start"):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scripts = root / "scripts"
            scripts.mkdir()
            for name in ("server.sh", "foundry-mcp.service.in"):
                (scripts / name).write_text(Path("scripts", name).read_text())
            (scripts / "server.sh").chmod(0o755)
            binary = root / "bin"
            binary.mkdir()
            systemctl = binary / "systemctl"
            systemctl.write_text('''#!/bin/bash
printf '%s\\n' "$*" >> "$CALL_LOG"
case "$2" in
show) echo "$UNIT_STATE" ;;
is-failed) [[ "$UNIT_STATE" == failed ]] ;;
reset-failed) [[ "$UNIT_STATE" == failed ]] || exit 1 ;;
esac
''')
            systemctl.chmod(0o755)
            for name in ("uv", "curl"):
                path = binary / name
                path.write_text("#!/bin/sh\nexit 0\n")
                path.chmod(0o755)
            log = root / "calls"
            config = root / "config"
            env = dict(os.environ, PATH=str(binary) + os.pathsep + os.environ["PATH"],
                       UNIT_STATE=state, CALL_LOG=str(log), XDG_CONFIG_HOME=str(config))
            result = subprocess.run([str(scripts / "server.sh"), action], env=env,
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            installed = (config / "systemd/user/foundry-mcp.service").exists()
            return log.read_text(), installed

    def test_inactive_unit_starts_without_reset(self):
        calls, installed = self.run_start("loaded")
        self.assertNotIn("reset-failed", calls)
        self.assertIn("--user start foundry-mcp.service", calls)
        self.assertFalse(installed)

    def test_missing_unit_is_installed_before_start(self):
        calls, installed = self.run_start("not-found")
        self.assertTrue(installed)
        self.assertLess(calls.index("daemon-reload"), calls.index("--user start"))
        self.assertNotIn("reset-failed", calls)

    def test_failed_unit_is_reset_before_restart(self):
        calls, installed = self.run_start("failed", "restart")
        self.assertFalse(installed)
        self.assertLess(calls.index("reset-failed"), calls.index("--user restart"))
