"""Package probe assertions and bounded Docker ownership; runtime checked separately."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from foundry_mcp_server import image_preview_package_probe as probe
from foundry_mcp_server.config import Settings

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('preview_package_check',ROOT/'scripts/image-preview-package-check.py')
runner=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(runner)
COMPOSE_SPEC=importlib.util.spec_from_file_location('preview_compose_check',ROOT/'scripts/image-preview-compose-check.py')
compose=importlib.util.module_from_spec(COMPOSE_SPEC);COMPOSE_SPEC.loader.exec_module(compose)


class PackagingContractTests(unittest.TestCase):
    def test_basic_and_oauth_examples_keep_origin_independent_and_named_private_storage(self):
        for filename in ('compose.yaml','compose.oauth.yaml'):
            source=(ROOT/'deploy'/filename).read_text()
            self.assertIn('FOUNDRY_MCP_IMAGE_PREVIEW_ORIGIN: ${FOUNDRY_MCP_IMAGE_PREVIEW_ORIGIN:-}',source)
            self.assertIn('FOUNDRY_MCP_IMAGE_PREVIEW_DATA_DIR: /data/image-previews',source)
            self.assertIn('- image-previews:/data/image-previews',source)
            self.assertIn('\n  image-previews:',source)
        for filename in ('.env.example','.env.oauth.example'):
            self.assertIn('FOUNDRY_MCP_IMAGE_PREVIEW_ORIGIN=\n',(ROOT/'deploy'/filename).read_text())
        self.assertIn('/data/image-previews',(ROOT/'Dockerfile').read_text())

    def test_invalid_configuration_fails_and_missing_origin_remains_disabled(self):
        with patch.dict(os.environ,{},clear=True):
            self.assertFalse(Settings.from_env().image_preview_issuance_enabled)
        for value in ('http://preview.example','https://preview.example/path','https://preview.example?secret=1'):
            with self.subTest(value=value),patch.dict(os.environ,{'FOUNDRY_MCP_IMAGE_PREVIEW_ORIGIN':value},clear=True),self.assertRaises(ValueError):Settings.from_env()
        for value in ('','relative',' /data/private'):
            with self.subTest(value=value),patch.dict(os.environ,{'FOUNDRY_MCP_IMAGE_PREVIEW_DATA_DIR':value},clear=True),self.assertRaises(ValueError):Settings.from_env()

    def test_container_recreation_preserves_volume_and_cleanup_is_exact(self):
        calls=[]
        def fake(*args):
            calls.append(args)
            if args[:2]==('image','inspect'):return 'sha256:fixture'
            if args[0]=='inspect':return 'healthy'
            if args[0]=='exec':return json.dumps(dict(passed=True,uid=10001,sha256='fixture',size_bytes=100))
            return ''
        report=runner.verify('local:fixture',run=fake,sleep=lambda _:None)
        self.assertTrue(report['passed']);self.assertTrue(report['cleanup_complete'])
        starts=[args for args in calls if args[0]=='run'];self.assertEqual(len(starts),2)
        self.assertEqual(starts[0],starts[1])
        volume=next(args[-1] for args in calls if args[:2]==('volume','create'))
        self.assertTrue(volume.startswith('foundry-preview-check-'))
        self.assertEqual(calls[-1],('volume','rm',volume))
        self.assertFalse(any('prune' in args or '--volumes' in args for args in calls))

    def test_failure_redacts_diagnostics_and_still_cleans_owned_resources(self):
        calls=[]
        def fake(*args):
            calls.append(args)
            if args[0]=='run':raise RuntimeError('private receipt sentinel')
            return 'fixture'
        report=runner.verify('local:fixture',run=fake)
        self.assertFalse(report['passed']);self.assertTrue(report['cleanup_complete'])
        self.assertNotIn('sentinel',json.dumps(report));self.assertEqual(calls[-1][:2],('volume','rm'))

    def test_preexisting_inspection_failure_never_removes_any_resource(self):
        calls=[]
        def fake(*args):calls.append(args);raise RuntimeError('Image missing')
        report=runner.verify('missing',run=fake)
        self.assertFalse(report['passed']);self.assertEqual(len(calls),1)

    def test_cleanup_failure_is_explicit_and_identifies_only_owned_marker(self):
        def fake(*args):
            if args[0]=='run' or args[:2]==('volume','rm'):raise RuntimeError('private sentinel')
            return 'fixture'
        report=runner.verify('local:fixture',run=fake)
        self.assertFalse(report['cleanup_complete']);self.assertEqual(report['cleanup_pending'],['volume'])
        self.assertTrue(report['cleanup_marker'].startswith('foundry-preview-check-'))
        self.assertNotIn('sentinel',json.dumps(report))

    def test_compose_validation_uses_only_synthetic_values_and_checks_real_structure(self):
        count=0
        def execute(args,**kwargs):
            nonlocal count
            count+=1
            env=kwargs['env'];self.assertEqual(env['FOUNDRY_MCP_BASIC_PASSWORD'],'synthetic-password')
            self.assertIn('/dev/null',args)
            configuration=dict(services={'foundry-mcp':dict(environment=dict(FOUNDRY_MCP_AUTH_MODE='basic',
                FOUNDRY_MCP_IMAGE_PREVIEW_ORIGIN=env['FOUNDRY_MCP_IMAGE_PREVIEW_ORIGIN'],
                FOUNDRY_MCP_IMAGE_PREVIEW_DATA_DIR='/data/image-previews'),volumes=[dict(type='volume',source='image-previews',target='/data/image-previews')])})
            return type('Result',(),dict(returncode=0,stdout=json.dumps(configuration)))()
        report=compose.verify(execute=execute)
        self.assertTrue(report['passed']);self.assertEqual(report['configurations'],count);self.assertEqual(count,10)
        with patch.object(compose,'examples',return_value=[('fixture','services:\n')]):
            report=compose.verify(execute=lambda *args,**kwargs:type('Result',(),dict(returncode=0,stdout='{}'))())
        self.assertFalse(report['passed'])


class PackagedNativeProbeTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_small_codec_font_annotation_and_private_persistence_probe(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(probe.os,'getuid',return_value=10001):
            report=await probe.seed(Path(directory)/'private')
            self.assertTrue(report['passed']);self.assertEqual(len(report['formats']),9)
            self.assertTrue(report['unsafe_svg_rejected']);self.assertTrue(report['private_permissions'])
            self.assertEqual(report['rendered_keys'],1)
            self.assertNotIn('token',json.dumps(report))

    async def test_fetch_checks_listener_bytes_headers_and_query_without_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            state=dict(token='private-fixture',extension='png',sha256=probe.hashlib.sha256(b'pixels').hexdigest(),size_bytes=6,mime_type='image/png')
            (Path(directory)/'package-receipt.json').write_text(json.dumps(state))
            calls=[]
            class Connection:
                def __init__(self,*args,**kwargs):pass
                def request(self,method,path):self.method=method;calls.append((method,path))
                def getresponse(self):return self
                status=200
                def read(self,_):return b'' if self.method=='HEAD' else b'pixels'
                def getheader(self,name):return {'Content-Type':'image/png','Content-Length':'6','Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'}.get(name)
                def close(self):pass
            with patch.object(probe.http.client,'HTTPConnection',Connection):
                self.assertTrue(probe.fetch(directory)['passed'])
            self.assertEqual(len(calls),3);self.assertEqual(calls[1][1],calls[0][1]+'?probe=1')
            with patch.object(Connection,'status',302),patch.object(probe.http.client,'HTTPConnection',Connection),self.assertRaises(ValueError):probe.fetch(directory)
