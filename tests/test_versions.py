import asyncio
import importlib.util
import json
from pathlib import Path
import tempfile
import tomllib
import unittest
from unittest.mock import AsyncMock, patch

from fastmcp import Client
from foundry_mcp_server.build_info import UNKNOWN, compare_builds, load_build_info, make_build_info, validate_build_info
from foundry_mcp_server.mcp_server import tools
from foundry_mcp_server.mcp_server.server import mcp
from foundry_mcp_server.ws.connection import RpcError

ROOT = Path(__file__).resolve().parent.parent
SHA = 'a' * 40
SERVER = make_build_info('1.3.0', 'v1.3.0', SHA)


def load_script(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BuildIdentityTests(unittest.TestCase):
    def test_release_and_unreleased_identity_and_tag_validation(self):
        self.assertEqual(SERVER['release_tag'], 'v1.3.0')
        self.assertEqual(make_build_info('1.3.0', revision=SHA)['build_kind'], 'unreleased')
        for args in [('1.3.0', 'v1.2.0', SHA), ('bad', None, None), ('1.3.0', None, 'short')]:
            with self.assertRaises(ValueError): make_build_info(*args)
        for kind in ['source', 'unreleased', 'unknown']:
            unverified = dict(SERVER, build_kind=kind, release_tag=None)
            if kind == 'unknown': unverified = dict(UNKNOWN)
            self.assertEqual(compare_builds(SERVER, unverified), 'unverified')
        self.assertEqual(compare_builds(SERVER, SERVER), 'match')
        self.assertEqual(compare_builds(SERVER, make_build_info('2.0.0','v2.0.0',SHA)), 'mismatch')

    def test_loader_falls_back_to_unknown_without_reading_environment(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'build-info.json'
            self.assertEqual(load_build_info(p), UNKNOWN)
            for text in ['invalid', '[]', '{"version":"1.3.0"}', 'x'*4097]:
                p.write_text(text)
                self.assertEqual(load_build_info(p), UNKNOWN)
            p.write_text(json.dumps(SERVER))
            with patch.dict('os.environ', {'VERSION':'99.0.0', 'RELEASE_TAG':'v99.0.0'}):
                self.assertEqual(load_build_info(p), SERVER)
            p.write_text(json.dumps(dict(SERVER, build_kind=[])))
            self.assertEqual(load_build_info(p), UNKNOWN)

    def test_tagged_zip_contains_exact_build_identity_and_rejects_wrong_commit(self):
        packager = load_script('package-module')
        metadata = load_script('build-metadata')
        current = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']['version']
        expected = make_build_info(current, 'v'+current, SHA)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            packager.package(output, tag='v'+current, revision=SHA)
            archive = output / 'foundry-mcp.zip'
            first = archive.read_bytes()
            metadata.verify_archive(archive, expected)
            with self.assertRaises(ValueError): metadata.verify_archive(archive, dict(expected, revision='b'*40))
            packager.package(output, tag='v'+current, revision=SHA)
            self.assertEqual(archive.read_bytes(), first)
            packager.package(output, revision=SHA)
            metadata.verify_archive(archive, make_build_info(current, revision=SHA))
            self.assertNotEqual(archive.read_bytes(), first)
        with self.assertRaises(ValueError): metadata.resolve(ROOT, 'tag', 'v99.0.0', SHA)
        self.assertEqual(metadata.resolve(ROOT, 'branch', 'main', SHA)['release_tag'], None)

    def test_source_identity_stays_synchronized(self):
        current = tomllib.loads((ROOT/'pyproject.toml').read_text())['project']['version']
        self.assertEqual(load_build_info()['version'], current)
        self.assertEqual(load_build_info()['build_kind'], 'source')


class VersionToolTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager = AsyncMock()
        self.manager.websockets = {'gm': object()}
        self.patches = [patch.object(tools, '_foundry_manager', self.manager, create=True),
                        patch('foundry_mcp_server.build_info.SERVER_BUILD', SERVER)]
        for p in self.patches: p.start(); self.addCleanup(p.stop)

    async def test_no_browser_preserves_server_identity(self):
        self.manager.websockets = {}
        result = await tools.get_bridge_versions.fn()
        self.assertEqual(result['server'], SERVER)
        self.assertEqual(result['comparison'], 'unavailable')
        self.assertEqual(result['module_status'], 'not_connected')
        self.assertIsNone(result['module'])
        self.manager.call.assert_not_awaited()

    async def test_exact_comparison_and_unreleased_not_a_verified_match(self):
        for module, expected in [(SERVER,'match'), (make_build_info('1.3.1','v1.3.1',SHA),'mismatch'),
                                 (make_build_info('1.3.0',revision=SHA),'unverified'), (dict(UNKNOWN),'unverified')]:
            self.manager.call.return_value = module
            result = await tools.get_bridge_versions.fn()
            self.assertEqual(result['comparison'], expected)
            self.assertEqual(result['module'], module)
            self.assertEqual(result['module_status'], 'connected')
        self.manager.call.assert_awaited_with('gm','getModuleBuildInfo',{},timeout=5.0)

    async def test_legacy_timeout_disconnect_and_malformed_metadata_are_diagnostic(self):
        for error, status in [(RpcError({'message': "Unknown method 'getModuleBuildInfo'"}),'unsupported'),
                              (RpcError({'message':'query failed'}),'invalid_metadata'),
                              (asyncio.TimeoutError(),'timed_out'), (ConnectionError(),'disconnected'),
                              (RuntimeError(),'disconnected')]:
            self.manager.call.side_effect = error
            result = await tools.get_bridge_versions.fn()
            self.assertEqual(result['module_status'],status)
            self.assertEqual(result['server'],SERVER)
            self.assertIsNone(result['module'])
        self.manager.call.side_effect = None
        for raw in [None, [], {'version':'fake'}, dict(SERVER,release_tag='vwrong'), dict(SERVER,build_kind=[])]:
            self.manager.call.return_value = raw
            self.assertEqual((await tools.get_bridge_versions.fn())['module_status'],'invalid_metadata')

    async def test_fresh_mcp_discovery_schema_and_real_no_browser_call(self):
        self.manager.websockets = {}
        async with Client(mcp) as client:
            catalog = {t.name:t for t in await client.list_tools()}
            tool = catalog['get_bridge_versions']
            self.assertEqual(tool.inputSchema.get('properties',{}),{})
            self.assertTrue(tool.annotations.readOnlyHint)
            for field in ['module_status','release_tag','unverified','get_player_names','five-second']:
                self.assertIn(field,tool.description)
            self.assertEqual(set(tool.outputSchema['required']), {'server','module','comparison','module_status','message'})
            result = await client.call_tool('get_bridge_versions', {})
            self.assertFalse(result.is_error)
            self.assertEqual(result.structured_content['server'],SERVER)
            self.assertEqual(result.structured_content['comparison'],'unavailable')
