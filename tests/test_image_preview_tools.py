"""Actual MCP metadata calls compose real private transfer/cache/native probe."""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from io import BytesIO
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastmcp import Client, FastMCP
from PIL import Image
import httpx2 as httpx

from foundry_mcp_server import main
from foundry_mcp_server.auth.principal import Principal, current_principal
from foundry_mcp_server.auth.metadata import OAuthToolMetadata
from foundry_mcp_server.config import Settings
from foundry_mcp_server.image_preview_source_runtime import SourceRuntime
from foundry_mcp_server.image_preview_sources import SourceSnapshots
from foundry_mcp_server.image_preview_failure import PreviewFailure
from foundry_mcp_server.mcp_server import image_previews as tools
from foundry_mcp_server.mcp_server import tools as registry
from foundry_mcp_server.mcp_server.image_preview_models import ImageInfoResult
from foundry_mcp_server.mcp_server.server import mcp
from foundry_mcp_server.ws.connection import RpcError
from test_image_preview_transfer import Browser, IMAGE
from test_image_preview_identity import call


def png(orientation=None):
    stream = BytesIO()
    image = Image.new('RGB',(31,17),(40,80,120))
    if orientation:
        exif = Image.Exif()
        exif[274] = orientation
        image.save(stream,format='PNG',exif=exif)
    else:image.save(stream,format='PNG')
    return stream.getvalue()


class MetadataBrowser(Browser):
    def __init__(self):
        super().__init__(png())
        self.membership_patch = {}
        self.membership_hook = None

    async def result(self,method,params):
        if method=='validateImagePreviewSource':
            if self.membership_hook:await self.membership_hook()
            return dict(**self.context,image=IMAGE,scope_status='complete',limitations=[],**self.membership_patch)
        return await super().result(method,params)


class ImageInfoToolsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.browser = MetadataBrowser()
        self.identity = Principal('basic','','gm','configured-account')
        self.now = 1000
        self.runtime = SourceRuntime(factory=lambda:SourceSnapshots(
            principal=lambda:self.identity,clock=lambda:self.now))
        await self.runtime.start()
        self.addAsyncCleanup(self.runtime.close)
        self.enterContext(patch.object(tools,'source_runtime',self.runtime))
        self.enterContext(patch.object(registry,'_foundry_manager',self.browser))

    async def invoke(self,request):
        async with Client(mcp) as client:
            return await client.call_tool('get_foundry_image_info',{'request':request},raise_on_error=False)

    def assert_empty(self):
        self.assertEqual(self.runtime.cache.used_bytes,0)
        self.assertEqual(list(self.runtime.cache.directory.iterdir()),[])
        self.assertFalse(self.browser.browser_active)

    async def test_discovery_strict_schemas_guidance_and_oauth_metadata(self):
        async with Client(mcp) as client:
            tool = next(t for t in await client.list_tools() if t.name=='get_foundry_image_info')
        request = tool.input_schema['$defs']['ImageInfoRequest']
        self.assertFalse(request['additionalProperties'])
        self.assertEqual(set(request['properties']),{'image','src'})
        self.assertFalse(tool.output_schema['additionalProperties'])
        self.assertEqual(set(tool.output_schema['properties']),set(ImageInfoResult.model_fields))
        for term in ('next_cursor','get_foundry_image_url','30 minutes','128 MiB','frame_policy'):
            self.assertIn(term,tool.description)
        oauth = FastMCP('metadata-discovery')
        oauth.add_middleware(OAuthToolMetadata())
        oauth.add_tool(await mcp.get_tool('get_foundry_image_info'))
        async with Client(oauth) as client:
            published = (await client.list_tools())[0]
            self.assertEqual(published.meta['securitySchemes'],[{'type':'oauth2','scopes':['foundry:gm']}])
        print('IMAGE_INFO_DISCOVERY_BYTES',len(json.dumps(tool.model_dump(by_alias=True),ensure_ascii=False,separators=(',',':')).encode()))

    async def test_canonical_and_bare_native_probe_no_origin_and_expiring_snapshot(self):
        self.browser.data = png(6)
        with patch.object(main,'settings',Settings()):
            for selector in ({'image':IMAGE},{'src':IMAGE['src']}):
                result = await self.invoke(selector)
                self.assertFalse(result.is_error)
                data = result.structured_content
                metadata = ImageInfoResult.model_validate(data)
                self.assertEqual((metadata.width,metadata.height),(17,31))
                self.assertEqual(metadata.size_bytes,len(self.browser.data))
                self.assertEqual(metadata.mime_type,'image/png')
                self.assertEqual(metadata.frame_policy,'still')
                self.assertEqual(datetime.fromisoformat(metadata.source_expires_at).timestamp(),2800)
                self.assertEqual(set(data),set(ImageInfoResult.model_fields))
                self.assertLess(len(json.dumps(data,separators=(',',':')).encode()),512)
                async with self.runtime.cache.lease(self.browser,metadata.source_id) as lease:
                    self.assertEqual(lease.original.path.read_bytes(),self.browser.data)
        self.assertEqual(sum(method=='beginImagePreviewTransfer' for _,method,*_ in self.browser.calls),2)
        self.now = 2800
        await self.runtime.cache.prune()
        self.assert_empty()

    async def test_strict_mcp_request_rejection_precedes_browser_reads(self):
        for request in ({},{'src':IMAGE['src'],'image':IMAGE},{'src':None},{'src':IMAGE['src'],'extra':'private'},
                {'source_id':'forged'},{'src':True},{'src':IMAGE['src'],'crop':{'x':0}}):
            result = await self.invoke(request)
            self.assertTrue(result.is_error)
        self.assertEqual(self.browser.calls,[])

    async def test_missing_authority_missing_gm_and_denied_browser_are_sanitized(self):
        self.identity = None
        result = await self.invoke({'image':IMAGE})
        self.assertTrue(result.is_error)
        self.assertIn('AuthenticatedContextRequired',str(result.content))
        self.assertEqual(self.browser.calls,[])
        self.identity = Principal('basic','','gm','configured-account')
        self.browser.websockets.clear()
        result = await self.invoke({'image':IMAGE})
        self.assertIn('BridgeUnavailable',str(result.content))
        self.browser.websockets['gm'] = self.browser.socket
        async def denied(_):raise RpcError({'code':'PermissionDenied','message':'private diagnostic sentinel'})
        self.browser.begin_hook = denied
        result = await self.invoke({'image':IMAGE})
        self.assertIn('PermissionDenied',str(result.content))
        self.assertNotIn('private diagnostic sentinel',str(result.content))
        self.assert_empty()

    async def test_probe_failure_malformed_worker_and_browser_never_publish_handles(self):
        for failure in (PreviewFailure('UnsupportedImage'),PreviewFailure('ImageTooLarge',40000,20)):
            with patch.object(tools,'probe_image',side_effect=failure):
                result = await self.invoke({'image':IMAGE})
                self.assertTrue(result.is_error)
                self.assertIn(failure.code,str(result.content))
                self.assert_empty()
        with patch.object(tools,'probe_image',return_value={'width':31,'height':17,'mime_type':'image/png',
                'size_bytes':len(self.browser.data),'frame_policy':'still','path':'private diagnostic sentinel'}):
            result = await self.invoke({'image':IMAGE})
            self.assertIn('ImageProcessingFailed',str(result.content))
            self.assertNotIn('private diagnostic sentinel',str(result.content))
            self.assert_empty()
        self.browser.begin_patch = {'private_field':'private diagnostic sentinel'}
        result = await self.invoke({'image':IMAGE})
        self.assertIn('InvalidFoundryResponse',str(result.content))
        self.assertNotIn('private diagnostic sentinel',str(result.content))
        self.assert_empty()

    async def test_world_user_socket_and_membership_changes_during_probe_reject_handle(self):
        real_probe = tools.probe_image
        for change in ('world','user','socket','denied'):
            browser = MetadataBrowser()
            with patch.object(registry,'_foundry_manager',browser):
                async def probe(path):
                    metadata = await real_probe(path)
                    if change=='world':browser.context['world_id']='other'
                    elif change=='user':browser.context['user_id']='other'
                    elif change=='socket':browser.websockets['gm']=object()
                    else:
                        async def denied():raise RpcError({'code':'PermissionDenied'})
                        browser.membership_hook=denied
                    return metadata
                with patch.object(tools,'probe_image',side_effect=probe):
                    result = await self.invoke({'image':IMAGE})
                    self.assertTrue(result.is_error)
                    self.assertIn('SourceContextLost',str(result.content))
                    self.assert_empty()

    async def test_cancellation_during_probe_releases_original_reservation_before_handle(self):
        started = asyncio.Event()
        async def wait(_):
            started.set()
            await asyncio.Event().wait()
        with patch.object(tools,'probe_image',side_effect=wait):
            operation = asyncio.create_task(tools.get_foundry_image_info(tools.ImageInfoRequest(image=IMAGE)))
            await started.wait()
            self.assertGreater(self.runtime.cache.used_bytes,0)
            operation.cancel()
            with self.assertRaises(asyncio.CancelledError):await operation
        self.assert_empty()

    async def test_actual_http_basic_authority_and_anonymous_cannot_stage(self):
        config = Settings(auth_mode='basic',basic_username='gm',basic_password='password',bridge_token='browser')
        runtime = SourceRuntime(factory=lambda:SourceSnapshots(principal=lambda:current_principal(config)))
        with patch.object(main,'settings',config),patch.object(main,'source_runtime',runtime),patch.object(tools,'source_runtime',runtime):
            async with main.app.router.lifespan_context(main.app),httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=main.app,client=('127.0.0.1',1234)),base_url='https://mcp.example.com') as client:
                response = await call(client,'get_foundry_image_info',{'request':{'image':IMAGE}},'Basic Z206cGFzc3dvcmQ=')
                self.assertEqual(response.status_code,200)
                self.assertFalse(response.json()['result'].get('isError'))
                ImageInfoResult.model_validate(response.json()['result']['structuredContent'])
                before = len(self.browser.calls)
                self.assertEqual((await call(client,'get_foundry_image_info',{'request':{'image':IMAGE}})).status_code,401)
                self.assertEqual(before,len(self.browser.calls))

    async def test_runtime_periodic_prune_close_and_restart_do_not_retain_originals(self):
        await self.runtime.close()
        self.runtime._prune_seconds = .005
        await self.runtime.start()
        await self.invoke({'image':IMAGE})
        cache = self.runtime.cache
        self.now = 2800
        for _ in range(100):
            if cache.used_bytes==0:break
            await asyncio.sleep(.005)
        self.assertEqual(cache.used_bytes,0)
        await self.runtime.close()
        self.assertFalse(cache.directory.exists())
        await self.runtime.start()
        self.assertIsNot(self.runtime.cache,cache)
        self.assertIsNotNone(self.runtime._pruner)

    async def test_cancelled_runtime_close_finishes_owned_cache_cleanup(self):
        await self.invoke({'image':IMAGE})
        cache = self.runtime.cache
        started,release = asyncio.Event(),asyncio.Event()
        close = cache.close
        async def delayed_close():
            started.set()
            await release.wait()
            await close()
        with patch.object(cache,'close',side_effect=delayed_close):
            operation = asyncio.create_task(self.runtime.close())
            await started.wait()
            operation.cancel()
            await asyncio.sleep(0)
            operation.cancel()
            release.set()
            with self.assertRaises(asyncio.CancelledError):await operation
        self.assertFalse(cache.directory.exists(),'Cancelled lifecycle left private originals on disk')
        self.assertIsNone(self.runtime.cache)

    async def test_live_checker_assertions_are_bounded_and_do_not_return_handles(self):
        from foundry_mcp_server.image_preview_info_check import verify
        class CheckClient:
            def __init__(self):self.calls=0;self.bad=False
            async def list_tools(self,**_):
                return [SimpleNamespace(name='get_foundry_image_info',model_dump=lambda **_: {})]
            async def call_tool(self,name,args,**_):
                self.calls+=1
                data = {'value':True} if name=='execute_javascript' else dict(source_id='secret-handle-'+str(self.calls),
                    source_expires_at='2030-01-01T00:00:00Z',width=31,height=17,mime_type='image/svg+xml',
                    size_bytes=100,frame_policy='still',**({'private':'secret'} if self.bad else {}))
                return SimpleNamespace(is_error=False,structured_content=data)
        client = CheckClient()
        report = await verify(client)
        self.assertTrue(report['passed'])
        self.assertEqual(report['calls'],4)
        self.assertNotIn('secret',json.dumps(report))
        client.bad=True
        report = await verify(client)
        self.assertFalse(report['passed'])
        self.assertNotIn('secret',json.dumps(report))
