import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("browser_dev", Path("scripts/browser_dev.py"))


class BrowserConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def test_requires_explicit_local_development_opt_in(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env.mcp"
            self.assertFalse(self.module.development_enabled(path))
            path.write_text("FOUNDRY_MCP_DEV_EXECUTION=false\n")
            self.assertFalse(self.module.development_enabled(path))
            path.write_text("# ignored\nFOUNDRY_MCP_DEV_EXECUTION=true\n")
            self.assertTrue(self.module.development_enabled(path))

    def test_debug_endpoint_comes_from_dedicated_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory)
            self.assertIsNone(self.module.debug_endpoint(profile))
            (profile / "DevToolsActivePort").write_text("12345\n/devtools/browser/test-id\n")
            self.assertEqual(self.module.debug_endpoint(profile), ("http://127.0.0.1:12345", "/devtools/browser/test-id"))
            for invalid in ["0\n/devtools/browser/test", "70000\n/devtools/browser/test", "12345\nwrong", "bad"]:
                (profile / "DevToolsActivePort").write_text(invalid)
                self.assertIsNone(self.module.debug_endpoint(profile))

    def test_disabled_mode_does_not_launch_a_browser(self):
        with patch.object(self.module, "development_enabled", return_value=False), patch.object(self.module.subprocess, "Popen") as launch:
            with self.assertRaisesRegex(SystemExit, "requires"):
                self.module.ensure_browser()
            launch.assert_not_called()

    def test_reuses_live_profile_without_starting_another_browser(self):
        endpoint = ("http://127.0.0.1:12345", "/devtools/browser/test-id")
        with patch.object(self.module, "development_enabled", return_value=True), patch.object(self.module, "debug_endpoint", return_value=endpoint), patch.object(self.module, "browser_alive", return_value=True), patch.object(self.module.subprocess, "Popen") as launch:
            self.assertEqual(self.module.ensure_browser(), endpoint[0])
            launch.assert_not_called()

    def test_development_launcher_opens_browser_and_forwards_resume_arguments(self):
        import subprocess
        with tempfile.TemporaryDirectory() as directory:
            scripts = Path(directory) / "scripts"
            scripts.mkdir()
            launcher = scripts / "codex-dev.sh"
            launcher.write_text(Path("scripts/codex-dev.sh").read_text())
            launcher.chmod(0o755)
            browser = scripts / "browser-dev.sh"
            browser.write_text('#!/bin/sh\ntouch "' + str(Path(directory) / 'browser-opened') + '"\n')
            browser.chmod(0o755)
            codex = scripts / "codex.sh"
            codex.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
            codex.chmod(0o755)
            result = subprocess.run([str(launcher), "resume", "--last"], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((Path(directory) / "browser-opened").exists())
            self.assertEqual(result.stdout.splitlines(), ["--config", "mcp_servers.chrome-devtools.enabled=true", "resume", "--last"])
