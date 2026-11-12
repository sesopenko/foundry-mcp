"""Deterministic local acceptance ownership, budgets, curl and TLS boundaries."""
import asyncio
import hashlib
import http.client
import importlib.util
import io
import json
from pathlib import Path
import ssl
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image
from foundry_mcp_server import image_preview_live_support as support

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('preview_live_check',ROOT/'scripts/image-preview-live-check.py')
live=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(live)


class LiveSupportTests(unittest.TestCase):
    def test_budget_reserves_cleanup_time_after_operation_deadline(self):
        now=[0];budget=support.Budget(limit=3,seconds=10,clock=lambda:now[0])
        budget.admit();now[0]=10
        with self.assertRaises(ValueError):budget.admit()
        budget.admit(cleanup=True)
        self.assertEqual(budget.calls,2)
        now[0]=40
        with self.assertRaises(ValueError):budget.admit(cleanup=True)

    def test_budget_rejects_calls_beyond_fixed_ceiling(self):
        budget=support.Budget(limit=2)
        budget.admit();budget.admit()
        with self.assertRaises(ValueError):budget.admit()
        self.assertEqual(budget.calls,2)

    def test_asset_creation_and_exact_cleanup_preserve_neighbor_and_unknown_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);neighbor=root/'existing.png';neighbor.write_bytes(b'existing')
            asset=support.AssetFixture(root,'a'*32)
            with asset:
                self.assertGreater((asset.path/asset.filename).stat().st_size,65536)
                with Image.open(asset.path/asset.filename) as decoded:self.assertEqual(decoded.size,(512,384))
            self.assertFalse(asset.path.exists());self.assertEqual(neighbor.read_bytes(),b'existing')
            with self.assertRaises(ValueError):support.AssetFixture(root,'../foreign')
            asset=support.AssetFixture(root,'b'*32);asset.__enter__()
            unknown=asset.path/'user-added';unknown.write_text('preserve')
            with self.assertRaises(ValueError):asset.cleanup()
            self.assertTrue(unknown.exists());unknown.unlink();asset.cleanup()

    def test_asset_cleanup_refuses_changed_marker_or_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            asset=support.AssetFixture(directory,'a'*32);asset.__enter__()
            marker=asset.path/'.preview-owner';marker.write_text('foreign')
            with self.assertRaises(ValueError):asset.cleanup()
            marker.write_text(asset.marker)
            path=asset.path/asset.filename;path.unlink();path.symlink_to('/etc/hosts')
            with self.assertRaises(ValueError):asset.cleanup()
            path.unlink();asset.cleanup()

    def test_private_settings_restore_exact_bytes_even_when_work_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'.env';original=b'FOUNDRY_MCP_CALLER_TOKEN=private-fixture\n'
            path.write_bytes(original)
            with self.assertRaisesRegex(RuntimeError,'fixture'):
                with support.preview_settings(path,'https://localhost:18443',Path(directory)/'store'):
                    self.assertIn(b'FOUNDRY_MCP_IMAGE_PREVIEW_ORIGIN=',path.read_bytes());raise RuntimeError('fixture')
            self.assertEqual(path.read_bytes(),original)
            path.write_bytes(b'FOUNDRY_MCP_IMAGE_PREVIEW_ORIGIN=https://existing.example\n')
            with self.assertRaises(ValueError):
                with support.preview_settings(path,'https://localhost:18443',Path(directory)/'store'):pass
            self.assertIn(b'existing.example',path.read_bytes())

    def test_concurrent_private_settings_edit_is_preserved_and_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'.env';path.write_bytes(b'original\n')
            with self.assertRaises(ValueError):
                with support.preview_settings(path,'https://localhost:18443',Path(directory)/'store'):
                    path.write_bytes(b'concurrent private edit\n')
            self.assertEqual(path.read_bytes(),b'concurrent private edit\n')

    def test_actual_loopback_tls_rejects_nonpreview_and_noncanonical_routes(self):
        with tempfile.TemporaryDirectory() as directory,support.PreviewTLS(directory) as tls:
            self.assertEqual(tls.server.server_address[0],'127.0.0.1')
            context=ssl.create_default_context(cafile=tls.certificate)
            connection=http.client.HTTPSConnection('localhost',tls.server.server_port,context=context,timeout=5)
            for path in ('/health','/mcp/mcp','/image-previews/not-a-capability','/image-previews/../health'):
                connection.request('GET',path);response=connection.getresponse()
                self.assertEqual(response.status,404);response.read()
            connection.close()

    def test_curl_uses_private_stdin_and_verifies_bytes_queries_head_and_headers(self):
        stream=io.BytesIO();Image.new('RGB',(7,5),(40,80,120)).save(stream,format='PNG');pixels=stream.getvalue()
        expected=dict(width=7,height=5,size_bytes=len(pixels),mime_type='image/png')
        origin='https://localhost:18443';url=origin+'/image-previews/00000000-0000-4000-8000-000000000000.png'
        calls=[]
        def execute(args,**kwargs):
            calls.append((args,kwargs));self.assertNotIn(url,' '.join(args));self.assertIn(url,kwargs['input'])
            head=args[args.index('--request')+1]=='HEAD'
            Path(args[args.index('--dump-header')+1]).write_text('HTTP/1.0 200 OK\nContent-Type: image/png\nContent-Length: '+str(len(pixels))+'\nCache-Control: private, no-store\nX-Content-Type-Options: nosniff\n')
            Path(args[args.index('--output')+1]).write_bytes(b'' if head else pixels)
            return SimpleNamespace(returncode=0,stdout=json.dumps(dict(status=200,redirects=0,downloaded=0 if head else len(pixels))))
        with tempfile.TemporaryDirectory() as directory:
            report=support.curl_delivery(url,expected,origin,'private-cert',directory,execute=execute)
            self.assertTrue(report['passed']);self.assertEqual(report['sha256'],hashlib.sha256(pixels).hexdigest())
            self.assertNotIn('00000000',json.dumps(report));self.assertEqual(len(calls),3)
            self.assertIn('?probe=1',calls[1][1]['input'])
            with self.assertRaises(ValueError):support.curl_delivery(url,expected,'https://other.example','cert',directory,execute=execute)

    def test_delivery_assertions_reject_redirects_wrong_headers_pixels_and_head_body(self):
        headers={'content-type':'image/png','content-length':'6','cache-control':'private, no-store','x-content-type-options':'nosniff'}
        expected=dict(width=1,height=1,size_bytes=6,mime_type='image/png')
        status=dict(status=200,redirects=0,downloaded=0)
        for changed in ({'status':302},{'redirects':1}):
            with self.assertRaises(ValueError):support.assert_delivery({**status,**changed},headers,b'',expected,head=True)
        for changed in ({'cache-control':'public'},{'content-type':'text/html'},{'content-length':'1'}, {'location':'private capability'}):
            with self.assertRaises(ValueError):support.assert_delivery(status,{**headers,**changed},b'',expected,head=True)
        with self.assertRaises(ValueError):support.assert_delivery(status,headers,b'pixels',expected,head=True)
        with self.assertRaises(Exception):support.assert_delivery(status,headers,b'pixels',expected)

    def test_real_curl_exact_query_and_head_through_local_tls(self):
        stream=io.BytesIO();Image.new('RGB',(7,5),(40,80,120)).save(stream,format='PNG');pixels=stream.getvalue()
        expected=dict(width=7,height=5,size_bytes=len(pixels),mime_type='image/png')
        methods=[]
        class Upstream:
            def __init__(self,*_,**__):pass
            def request(self,method,path):self.method=method;methods.append((method,path))
            def getresponse(self):return self
            status=200
            def read(self,_):return b'' if self.method=='HEAD' else pixels
            def getheader(self,name):return {'Content-Type':'image/png','Content-Length':str(len(pixels)),
                'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'}.get(name)
            def close(self):pass
        with tempfile.TemporaryDirectory() as directory,patch.object(support.http.client,'HTTPConnection',Upstream),support.PreviewTLS(directory) as tls:
            report=support.curl_delivery(tls.origin+'/image-previews/00000000-0000-4000-8000-000000000000.png',expected,tls.origin,tls.certificate,directory)
        self.assertTrue(report['passed']);self.assertEqual([row[0] for row in methods],['GET','GET','HEAD'])
        self.assertEqual(methods[1][1],methods[0][1]+'?probe=1')


class LiveWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_operation_deadline_still_dispatches_reserved_marker_cleanup(self):
        now=[0];budget=support.Budget(seconds=10,clock=lambda:now[0])
        class Client:
            async def list_tools(self,**_):now[0]=10;return []
            async def call_tool(self,name,args,**_):
                return SimpleNamespace(is_error=False,structured_content={'value':json.dumps(dict(journals_remaining=0,folders_remaining=0))},content=[],meta=None)
        report=await live.verify(Client(),SimpleNamespace(marker='a'*32),lambda _:None,budget=budget)
        self.assertFalse(report['passed']);self.assertTrue(report['journal_cleanup']);self.assertEqual(report['calls'],2)

    async def test_discovery_failure_redacts_error_and_still_attempts_marked_cleanup(self):
        class Client:
            async def list_tools(self,**_):raise RuntimeError('private capability sentinel')
            async def call_tool(self,name,args,**_):
                self.name=name;self.code=args['code']
                return SimpleNamespace(is_error=False,structured_content={'value':json.dumps(dict(journals_remaining=0,folders_remaining=0))},content=[],meta=None)
        client=Client();asset=SimpleNamespace(marker='a'*32)
        report=await live.verify(client,asset,lambda _:None)
        self.assertFalse(report['passed']);self.assertTrue(report['journal_cleanup']);self.assertEqual(report['calls'],2)
        self.assertNotIn('sentinel',json.dumps(report));self.assertEqual(client.name,'execute_javascript')
        self.assertIn('Wrong development runtime',client.code);self.assertIn('a'*32,client.code)
