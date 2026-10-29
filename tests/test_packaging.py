import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('package_module', ROOT / 'scripts/package-module.py')
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / 'foundry-module', self.root / 'foundry-module')
        shutil.copyfile(ROOT / 'pyproject.toml', self.root / 'pyproject.toml')

    def test_archive_root_imports_and_sensitive_exclusions(self):
        for name in ('.env', '.local/private.md', 'scripts/secret.env', 'scripts/debug.js.map', 'scripts/private.js'):
            p = self.root / 'foundry-module' / name
            p.parent.mkdir(exist_ok=True, parents=True)
            p.write_text('private fixture')
        output = self.root / 'output'
        version = packager.package(output, root=self.root, tag='v2.1.0')
        self.assertEqual(version, '2.1.0')
        with zipfile.ZipFile(output / 'foundry-mcp.zip') as archive:
            self.assertIn('module.json', archive.namelist())
            self.assertIn('scripts/connectionConfig.js', archive.namelist())
            self.assertEqual(archive.read('module.json'), (output / 'module.json').read_bytes())
            self.assertFalse(any('private' in n or '.env' in n or n.endswith('.map') for n in archive.namelist()))
            self.assertIn('LICENSE.txt', archive.namelist())
        first = (output / 'foundry-mcp.zip').read_bytes()
        packager.package(output, root=self.root, tag='v' + version)
        self.assertEqual(first, (output / 'foundry-mcp.zip').read_bytes())

    def test_mismatched_versions_mutable_urls_missing_imports_and_symlinks_fail(self):
        with self.assertRaisesRegex(ValueError, 'versions must agree'):
            packager.manifest(self.root, tag='v9.0.0')
        manifest = self.root / 'foundry-module/module.json'
        original = manifest.read_text()
        data = json.loads(original)
        data['download'] = data['manifest'].replace('module.json', 'foundry-mcp.zip')
        manifest.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'pinned'):
            packager.manifest(self.root)
        manifest.write_text(original)
        script = self.root / 'foundry-module/scripts/main.js'
        script.write_text('import "./missing.js";')
        with self.assertRaisesRegex(ValueError, 'import'):
            packager.manifest(self.root)
        script.unlink()
        script.symlink_to(ROOT / 'foundry-module/scripts/main.js')
        with self.assertRaisesRegex(ValueError, 'symlinks'):
            packager.manifest(self.root)

    def test_server_version_agrees_with_release(self):
        from foundry_mcp_server.main import app
        data, _ = packager.manifest()
        self.assertEqual(app.version, data['version'])
        self.assertIn('ARG VERSION=' + data['version'] + '\n', (ROOT / 'Dockerfile').read_text())
        self.assertIn('VERSION: ' + data['version'] + '\n', (ROOT / 'deploy/compose.local.yaml').read_text())
