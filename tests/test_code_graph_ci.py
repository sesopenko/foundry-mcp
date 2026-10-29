"""Exercise Git trust setup in the Debian container job with real Git."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]


class DebianCheckoutTests(unittest.TestCase):
    def test_container_checkout_trust_precedes_local_configuration(self):
        job = yaml.safe_load((ROOT / '.github/workflows/ci.yml').read_text())['jobs']['code-graph-debian']
        with tempfile.TemporaryDirectory(prefix='container checkout ') as directory:
            root = Path(directory)
            checkout = root / 'workspace'
            checkout.mkdir()
            home = root / 'home'
            home.mkdir()
            environment = {key: value for key, value in os.environ.items()
                           if not key.startswith('GIT_')}
            environment.update(HOME=str(home), GIT_CONFIG_NOSYSTEM='1',
                               GITHUB_WORKSPACE=str(checkout),
                               GIT_TEST_ASSUME_DIFFERENT_OWNER='1')
            subprocess.run(['git', 'init', '-q', str(checkout)], check=True,
                           env=environment, capture_output=True)
            # Reproduce the exact setup failure before any trust configuration.
            command = ['git', 'config', '--local', 'core.hooksPath', '.githooks']
            rejected = subprocess.run(command, cwd=checkout, env=environment,
                                      capture_output=True, text=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn('--local can only be used inside a git repository', rejected.stderr)
            checked_out = False
            for step in job['steps']:
                if step.get('uses', '').startswith('actions/checkout@'):
                    checked_out = True
                if 'dev-setup.sh' in step.get('run', ''):
                    break
                if checked_out and 'run' in step:
                    result = subprocess.run(['bash', '-e', '-c', step['run']],
                                            cwd=checkout, env=environment,
                                            capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
            configured = subprocess.run(command, cwd=checkout, env=environment,
                                        capture_output=True, text=True)
            self.assertEqual(configured.returncode, 0, configured.stderr)
            trusted = subprocess.check_output(
                ['git', 'config', '--global', '--get-all', 'safe.directory'],
                env=environment, text=True).splitlines()
            self.assertEqual(trusted, [str(checkout)])
