"""Exercise the launch wrappers without Docker or network access."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DocsStartupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        docker = self.directory / "docker"
        docker.write_text('''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ["DOCKER_CALLS"], "a") as stream:
    stream.write(json.dumps(args) + "\\n")
if args == ["info"] and os.environ.get("DAEMON_DOWN"):
    print("Docker daemon unavailable", file=sys.stderr)
    sys.exit(1)
if args[:2] == ["image", "inspect"]:
    sys.exit(1 if os.environ.get("IMAGE_MISSING") else 0)
if "config" in args:
    print("example/docs:fixed")
if "pull" in args:
    print("download progress")
    sys.exit(1 if os.environ.get("PULL_FAIL") else 0)
if "run" in args:
    print('{"jsonrpc":"2.0"}')
''')
        docker.chmod(0o755)
        self.calls_path = self.directory / "calls"
        self.env = dict(os.environ, PATH=f"{self.directory}:{os.environ['PATH']}",
                        DOCKER_CALLS=str(self.calls_path), COMPOSE_PROJECT_NAME="test-checkout")
        for name in ("IMAGE_MISSING", "PULL_FAIL", "DAEMON_DOWN"):
            self.env.pop(name, None)

    def run_script(self, name, *args):
        return subprocess.run(["bash", str(ROOT / "scripts" / name), *args],
                              cwd=self.directory, env=self.env, text=True,
                              capture_output=True)

    def calls(self):
        import json
        return [json.loads(line) for line in self.calls_path.read_text().splitlines()]

    def test_cached_startup_from_another_directory_preserves_protocol(self):
        result = self.run_script("docs-mcp.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '{"jsonrpc":"2.0"}\n')
        calls = self.calls()
        self.assertFalse(any("pull" in call for call in calls))
        run = calls[-1]
        self.assertIn(str(ROOT / "compose.docs.yml"), run)
        self.assertIn("test-checkout-docs", run)
        self.assertEqual(run[-6:], ["--rm", "--no-deps", "-T", "grounded-docs", "--protocol", "stdio"])

    def test_missing_image_download_goes_to_stderr(self):
        self.env["IMAGE_MISSING"] = "1"
        result = self.run_script("docs-mcp.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("download progress", result.stderr)
        self.assertNotIn("download progress", result.stdout)
        self.assertTrue(any("pull" in call for call in self.calls()))

    def test_failed_download_does_not_launch_server(self):
        self.env.update(IMAGE_MISSING="1", PULL_FAIL="1")
        result = self.run_script("docs-mcp.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any("run" in call for call in self.calls()))

    def test_daemon_failure_does_not_attempt_download(self):
        self.env["DAEMON_DOWN"] = "1"
        result = self.run_script("docs-setup.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Docker daemon unavailable", result.stderr)
        self.assertFalse(any("pull" in call for call in self.calls()))

    def test_cli_preserves_query_as_one_argument(self):
        result = self.run_script("docs-cli.sh", "search", "foundry-vtt", "Actor createDocuments")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls()[-1][-3:], ["search", "foundry-vtt", "Actor createDocuments"])
