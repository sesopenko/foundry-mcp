"""Exercise the repository release helper without touching Git or publishing."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / '.agents/skills/foundry-release/scripts/bump-version.py'
FILES = ('pyproject.toml', 'uv.lock', 'foundry_mcp_server/main.py', 'Dockerfile',
         'deploy/compose.local.yaml', 'tests/test_packaging.py', 'README.md',
         'deploy/.env.example', 'docs/operations.md', 'docs/docker-repository-overview.md')


class ReleaseSkillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in FILES:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        shutil.copytree(ROOT / 'foundry-module', self.root / 'foundry-module')
        current = tomllib.loads((self.root / 'pyproject.toml').read_text())['project']['version']
        major, minor, patch = map(int, current.split('.'))
        self.target = f'{major}.{minor + 1}.0'

    def snapshot(self):
        return {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def run_helper(self, *args):
        import sys
        return subprocess.run([sys.executable, str(SCRIPT), '--root', str(self.root), *args],
                              capture_output=True, text=True)

    def test_dry_run_requires_llm_selected_version_and_changes_nothing(self):
        before = self.snapshot()
        self.assertNotEqual(self.run_helper('--dry-run').returncode, 0)
        result = self.run_helper('--version', self.target, '--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(self.target, result.stdout)
        self.assertEqual(self.snapshot(), before)

    def test_bump_preserves_dependencies_and_stable_manifest_and_packages(self):
        before = tomllib.loads((self.root / 'uv.lock').read_text())
        result = self.run_helper('--version', self.target)
        self.assertEqual(result.returncode, 0, result.stderr)
        after = tomllib.loads((self.root / 'uv.lock').read_text())
        self.assertEqual([p for p in before['package'] if p['name'] != 'foundry-mcp'],
                         [p for p in after['package'] if p['name'] != 'foundry-mcp'])
        self.assertEqual(next(p for p in after['package'] if p['name'] == 'foundry-mcp')['version'], self.target)
        manifest = json.loads((self.root / 'foundry-module/module.json').read_text())
        self.assertEqual(manifest['version'], self.target)
        self.assertTrue(manifest['manifest'].endswith('/releases/latest/download/module.json'))
        self.assertTrue(manifest['download'].endswith(f'/releases/download/v{self.target}/foundry-mcp.zip'))
        import importlib.util
        spec = importlib.util.spec_from_file_location('release_skill_packager', ROOT / 'scripts/package-module.py')
        packager = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(packager)
        self.assertEqual(packager.package(self.root / 'dist', root=self.root, tag='v' + self.target), self.target)
        self.assertIn('ARG VERSION=' + self.target, (self.root / 'Dockerfile').read_text())
        self.assertIn('VERSION: ' + self.target, (self.root / 'deploy/compose.local.yaml').read_text())
        self.assertIn('version="' + self.target + '"', (self.root / 'foundry_mcp_server/main.py').read_text())

    def test_invalid_or_nonincreasing_version_does_not_edit(self):
        before = self.snapshot()
        for version in ['0.0.0', 'v2.0.0', '2.0.0-beta', '2.00.0']:
            with self.subTest(version=version):
                self.assertNotEqual(self.run_helper('--version', version).returncode, 0)
                self.assertEqual(self.snapshot(), before)

    def test_inconsistent_manifest_fails_before_any_edits(self):
        path = self.root / 'foundry-module/module.json'
        manifest = json.loads(path.read_text())
        manifest['download'] = 'https://example.com/wrong.zip'
        path.write_text(json.dumps(manifest))
        before = self.snapshot()
        result = self.run_helper('--version', self.target)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.snapshot(), before)
