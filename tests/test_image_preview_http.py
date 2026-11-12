"""Production app routes/config/lifecycle with private fixture capabilities."""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
from io import BytesIO
import logging
import os
from pathlib import Path
import tempfile
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

import httpx2 as httpx
from PIL import Image

from foundry_mcp_server import main
from foundry_mcp_server.config import Settings
from foundry_mcp_server.image_preview_failure import PreviewFailure
from foundry_mcp_server.image_preview_runtime import PreviewRuntime
from foundry_mcp_server.image_preview_store import PreviewStore,StoreFailure


class HttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.instant = 1794432000.25
        self.settings = Settings(auth_mode='basic',basic_username='user',basic_password='pass',bridge_token='bridge',
            image_preview_origin='https://previews.example.com',image_preview_data_dir=self.temp.name)
        self.runtime = self.make_runtime()
        stream = BytesIO()
        Image.new('RGB',(17,11),(20,40,60)).save(stream,format='PNG')
        self.data = stream.getvalue()

    def make_runtime(self,**options):
        return PreviewRuntime(store_factory=lambda directory:PreviewStore(directory,clock=lambda:self.instant),**options)

    @asynccontextmanager
    async def serve(self,*,settings=None,runtime=None):
        # HTTP client diagnostics must not print fixture bearer paths, including
        # on assertion failure. Production logger redaction belongs to09b.
        with patch.object(main,'settings',settings or self.settings),patch.object(main,'preview_runtime',runtime or self.runtime), \
                patch.object(logging.getLogger('httpx2'),'disabled',True):
            async with main.app.router.lifespan_context(main.app),httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=main.app),base_url='https://untrusted-host.example') as client:
                yield client

    def path(self,receipt):
        return f'/image-previews/{receipt.token}.{receipt.extension}'

    async def test_get_head_query_and_headers_without_reader_authentication(self):
        async with self.serve() as client:
            receipt = await self.runtime.publish(self.data,'image/png')
            path = self.path(receipt)
            exact = await client.get(path)
            query = await client.get(path+'?probe=1&source_id=ignored&crop=ignored')
            head = await client.head(path)
            for response in (exact,query,head):
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.headers['content-type'],'image/png')
                self.assertEqual(response.headers['content-length'],str(len(self.data)))
                self.assertEqual(response.headers['cache-control'],'private, no-store')
                self.assertEqual(response.headers['x-content-type-options'],'nosniff')
                for name in ('location','set-cookie','www-authenticate'):self.assertNotIn(name,response.headers)
                self.assertEqual(len(response.history),0)
            self.assertEqual(exact.content,self.data)
            self.assertEqual(query.content,self.data)
            self.assertEqual(head.content,b'')
            self.assertEqual(head.headers,exact.headers)
            with Image.open(BytesIO(exact.content)) as image:self.assertEqual(image.size,(17,11))

    async def test_webp_delivery_has_actual_mime_and_empty_matching_head(self):
        stream = BytesIO()
        Image.new('RGBA',(17,11),(20,40,60,100)).save(stream,format='WEBP',lossless=True)
        data = stream.getvalue()
        async with self.serve() as client:
            receipt = await self.runtime.publish(data,'image/webp')
            get,head = await client.get(self.path(receipt)),await client.head(self.path(receipt))
            self.assertEqual(get.status_code,200)
            self.assertEqual(get.content,data)
            self.assertEqual(get.headers['content-type'],'image/webp')
            self.assertEqual(get.headers,head.headers)
            self.assertEqual(head.content,b'')

    async def test_generic_unknown_malformed_extension_and_expired_not_found(self):
        async with self.serve() as client:
            receipt = await self.runtime.publish(self.data,'image/png')
            for path in ('/image-previews','/image-previews/','/image-previews/not-a-token',
                    '/image-previews/nested/path.png','/image-previews/'+str(uuid.uuid4())+'.png',
                    self.path(receipt).replace('.png','.webp'),self.path(receipt)+'/'):
                for method in ('GET','HEAD'):
                    response = await client.request(method,path)
                    self.assertEqual(response.status_code,404)
                    self.assertEqual(response.headers['cache-control'],'no-store')
                    self.assertEqual(response.content,b'')
                    self.assertNotIn('location',response.headers)
            # Pause only pruning; HTTP retrieval itself must enforce expiry.
            self.runtime.pruner.cancel()
            await asyncio.gather(self.runtime.pruner,return_exceptions=True)
            self.instant = receipt.expires_at-0.001
            self.assertEqual((await client.get(self.path(receipt))).status_code,200)
            self.instant = receipt.expires_at
            self.assertEqual((await client.get(self.path(receipt))).status_code,404)
            self.assertEqual((await client.head(self.path(receipt))).status_code,404)

    async def test_reader_survives_gm_disconnect_and_uses_trusted_url_origin(self):
        async with self.serve() as client:
            receipt = await self.runtime.publish(self.data,'image/png')
            with patch.object(main.foundry_manager,'websockets',{}):
                response = await client.get(self.path(receipt),headers={'Host':'evil.example','Forwarded':'host=evil.example;proto=http'})
                self.assertEqual(response.status_code,200)
            url = self.runtime.url(receipt)
            self.assertTrue(url.startswith('https://previews.example.com/image-previews/'))
            self.assertFalse('?' in url or '#' in url or 'evil.example' in url)

    async def test_root_filename_query_cannot_select_a_capability(self):
        async with self.serve() as client:
            receipt = await self.runtime.publish(self.data,'image/png')
            response = await client.get('/image-previews',params={'filename':receipt.token+'.png'})
            self.assertEqual(response.status_code,404)
            self.assertEqual(response.content,b'')

    async def test_disabled_store_does_not_touch_storage_and_issuance_fails_early(self):
        settings = replace(self.settings,image_preview_origin='')
        runtime = PreviewRuntime(store_factory=lambda directory:self.fail('disabled store created'))
        async with self.serve(settings=settings,runtime=runtime) as client:
            with self.assertRaises(PreviewFailure) as caught:await runtime.publish(self.data,'image/png')
            self.assertEqual(caught.exception.code,'PreviewNotConfigured')
            self.assertEqual((await client.get('/image-previews/'+str(uuid.uuid4())+'.png')).status_code,404)
            self.assertEqual((await client.get('/health')).status_code,200)
        self.assertIsNone(runtime.pruner)

    async def test_lifespan_shutdown_and_reopen_preserve_unexpired_bytes(self):
        async with self.serve():
            receipt = await self.runtime.publish(self.data,'image/png')
            store,pruner = self.runtime.store,self.runtime.pruner
        self.assertTrue(store.closed)
        self.assertTrue(pruner.done())
        self.assertEqual(self.runtime.pending,set())
        self.assertIsNone(self.runtime.store)
        async with self.serve() as client:
            response = await client.get(self.path(receipt))
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.content,self.data)

    async def test_periodic_prune_runs_and_shutdown_leaves_no_task(self):
        runtime = self.make_runtime(prune_interval=0.01)
        async with self.serve(runtime=runtime):
            receipt = await runtime.publish(self.data,'image/png')
            self.instant = receipt.expires_at
            reached = asyncio.Event()
            loop = asyncio.get_running_loop()
            original = runtime.store.prune
            def prune():
                count = original()
                loop.call_soon_threadsafe(reached.set)
                return count
            with patch.object(runtime.store,'prune',side_effect=prune):
                await asyncio.wait_for(reached.wait(),2)
            self.assertIsNone(await runtime.lookup(receipt.token,'png'))
            pruner = runtime.pruner
        self.assertTrue(pruner.done())

    async def test_enabled_unwritable_storage_fails_application_startup(self):
        bad = Path(self.temp.name)/'not-a-directory'
        bad.write_bytes(b'fixture')
        with self.assertRaises(StoreFailure) as caught:
            async with self.serve(settings=replace(self.settings,image_preview_data_dir=str(bad))):pass
        self.assertEqual(str(caught.exception),'PreviewStorageUnavailable')
        self.assertIsNone(self.runtime.store)

    async def test_storage_errors_are_fixed_service_unavailable_without_details(self):
        async with self.serve() as client:
            receipt = await self.runtime.publish(self.data,'image/png')
            with patch.object(self.runtime.store,'lookup',side_effect=StoreFailure()),self.assertLogs('foundry_mcp',level='ERROR') as recorded:
                response = await client.get(self.path(receipt))
            self.assertEqual(response.status_code,503)
            self.assertEqual(response.content,b'')
            self.assertEqual(response.headers['cache-control'],'no-store')
            self.assertTrue(all(receipt.token not in line for line in recorded.output))

    async def test_framework_startup_failure_also_closes_owned_preview_store(self):
        owned = []
        def factory(directory):
            result = PreviewStore(directory)
            owned.append(result)
            return result
        runtime = PreviewRuntime(store_factory=factory)
        @asynccontextmanager
        async def broken(app):
            raise RuntimeError('fixture startup failure')
            yield
        with patch.object(main,'mcp_app',SimpleNamespace(lifespan=broken)):
            with self.assertRaisesRegex(RuntimeError,'fixture startup failure'):
                async with self.serve(runtime=runtime):pass
        self.assertTrue(owned[0].closed)
        self.assertIsNone(runtime.store)

    async def test_cancelled_threaded_startup_retains_ownership_until_store_can_close(self):
        loop = asyncio.get_running_loop()
        entered,release = asyncio.Event(),Event()
        owned = []
        def factory(directory):
            loop.call_soon_threadsafe(entered.set)
            if not release.wait(2):raise AssertionError('startup fixture not released')
            result = PreviewStore(directory)
            owned.append(result)
            return result
        runtime = PreviewRuntime(store_factory=factory)
        task = asyncio.create_task(runtime.start(self.settings))
        try:
            await asyncio.wait_for(entered.wait(),1)
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
            self.assertFalse(task.done())
        finally:release.set()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertTrue(owned[0].closed)
        self.assertIsNone(runtime.pruner)
        self.assertIsNone(runtime.store)

    async def test_cancelled_lookup_and_shutdown_drain_thread_before_closing(self):
        runtime = self.make_runtime()
        await runtime.start(self.settings)
        store = runtime.store
        loop = asyncio.get_running_loop()
        entered,release = asyncio.Event(),Event()
        original = store.lookup
        def lookup(*args):
            loop.call_soon_threadsafe(entered.set)
            if not release.wait(2):raise AssertionError('lookup fixture not released')
            self.assertFalse(store.closed)
            return original(*args)
        with patch.object(store,'lookup',side_effect=lookup):
            task = asyncio.create_task(runtime.lookup(str(uuid.uuid4()),'png'))
            try:
                await asyncio.wait_for(entered.wait(),1)
                task.cancel()
                close = asyncio.create_task(runtime.close())
                await asyncio.sleep(0)
                close.cancel()
                self.assertFalse(close.done())
                self.assertFalse(store.closed)
            finally:release.set()
            with self.assertRaises(asyncio.CancelledError):await task
            with self.assertRaises(asyncio.CancelledError):await close
        self.assertTrue(store.closed)
        self.assertFalse(runtime.pending)
        self.assertIsNone(runtime.pruner)


class ConfigurationTests(unittest.TestCase):
    def test_origin_is_independent_of_oauth_public_resource_origin(self):
        env = dict(FOUNDRY_MCP_AUTH_MODE='basic',FOUNDRY_MCP_BASIC_USERNAME='user',
            FOUNDRY_MCP_BASIC_PASSWORD='pass',FOUNDRY_MCP_BRIDGE_TOKEN='bridge',
            FOUNDRY_MCP_IMAGE_PREVIEW_ORIGIN='https://previews.example.com')
        with patch.dict(os.environ,env,clear=True):
            settings = Settings.from_env()
        self.assertTrue(settings.image_preview_issuance_enabled)
        self.assertEqual(settings.image_preview_data_dir,'/data/image-previews')
        self.assertEqual(settings.public_url,'')
        self.assertFalse(Settings(image_preview_origin='https://previews.example.com').image_preview_issuance_enabled)

    def test_invalid_origins_and_data_directories_fail_without_values_in_errors(self):
        for variable,values in (('FOUNDRY_MCP_IMAGE_PREVIEW_ORIGIN',('http://example.com','https://example.com/',
                'https://user:secret@example.com','https://example.com/path','https://example.com?secret=x',
                'https://EXAMPLE.com','https://example.com#fragment')),
                ('FOUNDRY_MCP_IMAGE_PREVIEW_DATA_DIR',('','relative',' /tmp/private'))):
            for value in values:
                with patch.dict(os.environ,{variable:value},clear=True):
                    with self.assertRaises(ValueError) as caught:Settings.from_env()
                self.assertIn(variable,str(caught.exception))
                self.assertNotIn('secret',str(caught.exception))
        # POSIX environ itself rejects NUL before Settings can inspect it.
        with patch.dict(os.environ,{},clear=True),patch('foundry_mcp_server.config.os.getenv',
                side_effect=lambda key,default=None:'/tmp/\x00private' if key=='FOUNDRY_MCP_IMAGE_PREVIEW_DATA_DIR' else default):
            with self.assertRaisesRegex(ValueError,'FOUNDRY_MCP_IMAGE_PREVIEW_DATA_DIR'):Settings.from_env()
