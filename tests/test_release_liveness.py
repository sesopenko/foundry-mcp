"""Fixed runner accepts no URL, curl options, uploads or credential inputs."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/release-liveness.sh'


class ReleaseLivenessTests(unittest.TestCase):
    def test_fixed_operations_and_rejected_extra_arguments(self):
        endpoints = {
            'runs': 'https://api.github.com/repos/sesopenko/foundry-mcp/actions/runs?per_page=5',
            'release': 'https://api.github.com/repos/sesopenko/foundry-mcp/releases/latest',
            'manifest': 'https://github.com/sesopenko/foundry-mcp/releases/latest/download/module.json',
            'module': 'https://github.com/sesopenko/foundry-mcp/releases/latest/download/foundry-mcp.zip',
            'images': 'https://hub.docker.com/v2/repositories/sesopenko/foundry-mcp/tags?page_size=10',
        }
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / 'curl'
            fake.write_text('#!/bin/bash\nprintf "%s\\n" "$@"\n')
            fake.chmod(0o700)
            env = {**os.environ, 'PATH': directory + os.pathsep + os.environ['PATH']}
            for operation, endpoint in endpoints.items():
                result = subprocess.run(['/bin/bash', str(SCRIPT), operation], env=env, capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                expected = ['--disable', '--fail', '--silent', '--show-error', '--location', '--proto', '=https', '--proto-redir', '=https', '--max-time', '20', '--request', 'HEAD' if operation == 'module' else 'GET']
                if operation == 'module': expected += ['--head']
                self.assertEqual(result.stdout.splitlines(), expected + ['--url', endpoint])
            for args in ([], ['arbitrary'], ['https://example.com'], ['runs', '-X', 'DELETE'], ['manifest', '--upload-file', '/tmp/file'], ['images', 'https://example.com']):
                result = subprocess.run(['/bin/bash', str(SCRIPT), *args], env=env, capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, '')
