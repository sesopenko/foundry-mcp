"""Actual MCP metadata calls compose real private transfer/cache/native probe."""
import asyncio
from dataclasses import replace
from contextlib import asynccontextmanager
from datetime import datetime
from io import BytesIO
import json
import unittest
from types import SimpleNamespace
import tempfile
from threading import Event
from pathlib import Path
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
from foundry_mcp_server.mcp_server.image_preview_models import ImageInfoResult,ImageUrlResult
from foundry_mcp_server.image_preview_runtime import PreviewRuntime
from foundry_mcp_server.image_preview_store import PreviewStore,StoreFailure
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
        self.assertEqual(set(request['properties']),{'image','src','map'})
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


class ImageUrlToolsTests(unittest.IsolatedAsyncioTestCase):
    assert_empty = ImageInfoToolsTests.assert_empty

    async def asyncSetUp(self):
        await ImageInfoToolsTests.asyncSetUp(self)
        # Existing exact-pixel regressions explicitly exercise legacy mode.
        self.enterContext(patch.object(tools,'settings',replace(tools.settings,image_preview_jpeg=False)))
        self.storage = tempfile.TemporaryDirectory()
        self.addCleanup(self.storage.cleanup)
        self.public_now = 2000
        self.delivery = PreviewRuntime(store_factory=lambda path:PreviewStore(path,clock=lambda:self.public_now))
        await self.delivery.start(Settings(auth_mode='basic',basic_username='gm',basic_password='password',
            bridge_token='browser',image_preview_origin='https://previews.example.com',image_preview_data_dir=self.storage.name))
        self.addAsyncCleanup(self.delivery.close)
        self.enterContext(patch.object(tools,'preview_runtime',self.delivery))
        self.enterContext(patch.object(main,'preview_runtime',self.delivery))
        image = Image.new('RGB',(31,17))
        image.putdata([(x*7,y*11,(x+y)*5) for y in range(17) for x in range(31)])
        stream = BytesIO()
        image.save(stream,format='PNG')
        self.browser.data = stream.getvalue()

    async def invoke(self,request):
        async with Client(mcp) as client:
            return await client.call_tool('get_foundry_image_url',{'request':request},raise_on_error=False)

    async def info(self):
        return await tools.get_foundry_image_info(tools.ImageInfoRequest(image=IMAGE))

    def published_rows(self):
        with self.delivery.store.connection() as database:
            return database.execute('SELECT COUNT(*) FROM previews').fetchone()[0]

    async def fetched(self,result):
        # Production route, no Authorization, with source/crop-looking query
        # values that must not select any pixels beyond this capability.
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='https://previews.example.com') as client:
            response = await client.get(result.url)
            query = await client.get(result.url+'?x=0&width=9999&src=original')
            head = await client.head(result.url)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.content,query.content)
        self.assertEqual(int(head.headers['content-length']),len(response.content))
        self.assertEqual(head.content,b'')
        return response.content

    async def test_discovery_three_inputs_strict_output_oauth_and_link_guidance(self):
        async with Client(mcp) as client:
            tool = next(t for t in await client.list_tools() if t.name=='get_foundry_image_url')
        request = tool.input_schema['$defs']['ImageUrlRequest']
        self.assertEqual(set(request['properties']),{'image','src','map','source_id','crop','map_notes'})
        self.assertFalse(request['additionalProperties'])
        self.assertEqual(set(tool.output_schema['properties']),set(ImageUrlResult.model_fields))
        self.assertFalse(tool.output_schema['additionalProperties'])
        self.assertIn('image/jpeg',tool.output_schema['properties']['mime_type']['enum'])
        self.assertIn('FOUNDRY_MCP_IMAGE_PREVIEW_JPEG',tool.description)
        for term in ('seven days','604800','anyone','floor','ceil','PreviewNotConfigured','first displayable'):
            self.assertIn(term,tool.description)
        oauth = FastMCP('url-discovery')
        oauth.add_middleware(OAuthToolMetadata())
        oauth.add_tool(await mcp.get_tool('get_foundry_image_url'))
        async with Client(oauth) as client:
            self.assertEqual((await client.list_tools())[0].meta['securitySchemes'][0]['scopes'],['foundry:gm'])
        print('IMAGE_URL_DISCOVERY_BYTES',len(json.dumps(tool.model_dump(by_alias=True),ensure_ascii=False,separators=(',',':')).encode()))

    async def test_default_jpeg_and_disabled_policy_actual_mcp_and_anonymous_headers(self):
        self.assertTrue(Settings().image_preview_jpeg)
        rows=[]
        async with Client(mcp) as client:
            catalog=await client.list_tools()
            catalog_bytes=len(json.dumps([t.model_dump(by_alias=True) for t in catalog],ensure_ascii=False,separators=(',',':')).encode())
            result=await client.call_tool('get_foundry_image_info',{'request':{'image':IMAGE}})
            info=ImageInfoResult.model_validate(result.structured_content)
        calls=1
        for enabled,mime,suffix in ((False,'image/png','.png'),(True,'image/jpeg','.jpg')):
            with patch.object(tools,'settings',replace(tools.settings,image_preview_jpeg=enabled)):
                for name,request in [('default',{'image':IMAGE}),('crop',{'source_id':info.source_id,'crop':dict(x=7,y=4,width=11,height=9)})]:
                    result=await self.invoke(request)
                    calls+=1
                    self.assertFalse(result.is_error,str(result.content))
                    value=ImageUrlResult.model_validate(result.structured_content)
                    self.assertEqual(value.mime_type,mime)
                    self.assertTrue(value.url.endswith(suffix))
                    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='https://previews.example.com') as client:
                        get=await client.get(value.url);head=await client.head(value.url)
                        wrong=await client.get(value.url[:-len(suffix)]+('.png' if enabled else '.jpg'))
                    self.assertEqual((get.status_code,head.status_code,wrong.status_code),(200,200,404))
                    self.assertEqual(get.headers['content-type'],mime)
                    self.assertEqual(get.headers,head.headers)
                    self.assertEqual(head.content,b'')
                    with Image.open(BytesIO(get.content)) as actual:
                        actual.load()
                        self.assertEqual(actual.format,'JPEG' if enabled else 'PNG')
                        self.assertEqual(actual.size,(value.width,value.height))
                    rows.append(dict(jpeg=enabled,scenario=name,json_bytes=len(json.dumps(result.structured_content,separators=(',',':')).encode()),
                        image_bytes=len(get.content),complete=True))
        self.assertEqual(self.published_rows(),4)
        self.assertEqual(calls,5)
        print('JPEG_MCP_BUDGET',json.dumps(dict(calls=calls,discovery_calls=1,catalog_count=len(catalog),catalog_bytes=catalog_bytes,rows=rows),separators=(',',':')))

    async def test_all_inputs_reuse_native_crop_pixels_distinct_links_and_capability_scope(self):
        info = await self.info()
        before = sum(method=='beginImagePreviewTransfer' for _,method,*_ in self.browser.calls)
        urls = []
        for selector in ({'source_id':info.source_id},{'source_id':info.source_id},{'src':IMAGE['src']},{'image':IMAGE}):
            result = await self.invoke({**selector,'crop':{'x':7,'y':4,'width':11,'height':9}})
            self.assertFalse(result.is_error)
            value = ImageUrlResult.model_validate(result.structured_content)
            urls.append(value.url)
            self.assertEqual((value.source_width,value.source_height),(31,17))
            self.assertEqual(value.region.model_dump(),dict(x=7,y=4,width=11,height=9))
            self.assertEqual((value.width,value.height),(11,9))
            self.assertEqual(datetime.fromisoformat(value.expires_at).timestamp(),606800)
            self.assertEqual(datetime.fromisoformat(value.source_expires_at).timestamp(),2800)
            data = await self.fetched(value)
            self.assertEqual(value.size_bytes,len(data))
            with Image.open(BytesIO(data)) as actual,Image.open(BytesIO(self.browser.data)) as source:
                self.assertEqual(actual.convert('RGB').tobytes(),source.crop((7,4,18,13)).tobytes())
            if 'source_id' in selector:
                self.assertEqual(sum(method=='beginImagePreviewTransfer' for _,method,*_ in self.browser.calls),before)
            self.assertLess(len(json.dumps(result.structured_content,separators=(',',':')).encode()),800)
        self.assertEqual(len(set(urls)),4)
        self.assertEqual(self.published_rows(),4)
        self.assertEqual(sum(method=='beginImagePreviewTransfer' for _,method,*_ in self.browser.calls),3)

    async def test_overview_omitted_crop_and_replaced_source_old_handle_keeps_original(self):
        info = await self.info()
        original = self.browser.data
        self.browser.data = png()
        first = await self.invoke({'source_id':info.source_id})
        second = await self.invoke({'image':IMAGE})
        self.assertFalse(first.is_error)
        self.assertFalse(second.is_error)
        left,right = (ImageUrlResult.model_validate(r.structured_content) for r in (first,second))
        self.assertEqual(left.region.model_dump(),dict(x=0,y=0,width=31,height=17))
        self.assertNotEqual(left.source_id,right.source_id)
        with Image.open(BytesIO(await self.fetched(left))) as old,Image.open(BytesIO(original)) as oracle:
            self.assertEqual(old.convert('RGB').tobytes(),oracle.tobytes())
        self.assertNotEqual(await self.fetched(left),await self.fetched(right))

    async def test_disabled_issuance_precedes_all_source_processing_and_missing_principal(self):
        self.delivery.issuance_enabled=False
        for selector in ({'image':IMAGE},{'src':IMAGE['src']},{'source_id':'unknown'}):
            result = await self.invoke(selector)
            self.assertTrue(result.is_error)
            self.assertIn('PreviewNotConfigured',str(result.content))
        self.assertEqual(self.browser.calls,[])
        self.assert_empty()
        self.delivery.issuance_enabled=True
        self.identity=None
        result = await self.invoke({'image':IMAGE})
        self.assertIn('AuthenticatedContextRequired',str(result.content))
        self.assertEqual(self.browser.calls,[])
        self.assertEqual(self.published_rows(),0)

    async def test_disabled_runtime_checker_uses_discovery_and_real_mcp_error(self):
        from foundry_mcp_server.image_preview_info_check import verify_disabled_url
        self.delivery.issuance_enabled=False
        async with Client(mcp) as client:
            report=await verify_disabled_url(client)
        self.assertTrue(report['passed'])
        self.assertEqual(report['calls'],2)
        self.assertTrue(report['disabled_issuance'])
        self.assertEqual(self.browser.calls,[])

    async def test_invalid_crop_geometry_rejected_without_publication(self):
        info = await self.info()
        for crop in ({'x':True,'y':0,'width':1,'height':1},{'x':0.1,'y':0,'width':1,'height':1},
                {'x':-1,'y':0,'width':1,'height':1},{'x':0,'y':0,'width':0,'height':1},
                {'x':30,'y':16,'width':2,'height':1}):
            result = await self.invoke({'source_id':info.source_id,'crop':crop})
            self.assertTrue(result.is_error)
            self.assertIn('InvalidCrop',str(result.content))
        self.assertEqual(self.published_rows(),0)
        self.assertEqual(self.runtime.cache.used_bytes,len(self.browser.data))

    async def test_expired_cross_principal_and_denied_handles_cannot_issue(self):
        info = await self.info()
        self.identity=Principal('oauth','issuer','other','client')
        before=len(self.browser.calls)
        result=await self.invoke({'source_id':info.source_id})
        self.assertIn('SourceUnavailable',str(result.content))
        self.assertEqual(len(self.browser.calls),before)
        self.identity=Principal('basic','','gm','configured-account')
        async def denied():raise RpcError({'code':'PermissionDenied','message':'private sentinel'})
        self.browser.membership_hook=denied
        result=await self.invoke({'source_id':info.source_id})
        self.assertIn('SourceContextLost',str(result.content))
        self.assertNotIn('private sentinel',str(result.content))
        self.browser.membership_hook=None
        self.now=2800
        result=await self.invoke({'source_id':info.source_id})
        self.assertIn('SourceUnavailable',str(result.content))
        self.assert_empty()
        self.assertEqual(self.published_rows(),0)

    async def test_context_changes_during_render_and_publication_never_return_url(self):
        real_render=tools.render_preview
        real_publish=self.delivery.publish
        for change in ('socket','world','user','principal','publish'):
            self.identity=Principal('basic','','gm','configured-account')
            self.browser.context=dict(world_id='test',user_id='gm')
            self.browser.websockets['gm']=self.browser.socket
            info=await self.info()
            async def render(*args,**kwargs):
                value=await real_render(*args,**kwargs)
                if change=='socket':self.browser.websockets['gm']=object()
                elif change=='world':self.browser.context['world_id']='other'
                elif change=='user':self.browser.context['user_id']='other'
                elif change=='principal':self.identity=Principal('basic','','other','configured-account')
                return value
            async def publish(*args):
                value=await real_publish(*args)
                self.browser.context['world_id']='other'
                return value
            rows=self.published_rows()
            with patch.object(tools,'render_preview',side_effect=render),patch.object(self.delivery,'publish',
                    side_effect=publish if change=='publish' else real_publish):
                result=await self.invoke({'source_id':info.source_id})
            self.assertTrue(result.is_error)
            self.assertNotIn('https://previews.example.com',str(result.content))
            self.assertEqual(self.published_rows(),rows+(change=='publish'))
        self.identity=Principal('basic','','gm','configured-account')
        self.assertTrue(all(record.leases==0 for record in self.runtime.cache._entries.values()))

    async def test_invalid_worker_output_storage_error_and_quota_preserve_existing_links(self):
        info=await self.info()
        good=await self.invoke({'source_id':info.source_id})
        value=ImageUrlResult.model_validate(good.structured_content)
        expected=await self.fetched(value)
        with patch.object(tools,'render_preview',return_value={'path':'private sentinel'}):
            result=await self.invoke({'source_id':info.source_id})
            self.assertIn('ImageProcessingFailed',str(result.content))
            self.assertNotIn('private sentinel',str(result.content))
        for failure in (StoreFailure(),StoreFailure('PreviewQuotaExceeded')):
            with patch.object(self.delivery.store,'publish',side_effect=failure):
                result=await self.invoke({'source_id':info.source_id})
                self.assertTrue(result.is_error)
                self.assertIn(failure.code,str(result.content))
        self.delivery.store.max_rows=1
        result=await self.invoke({'source_id':info.source_id})
        self.assertIn('PreviewQuotaExceeded',str(result.content))
        self.assertEqual(self.published_rows(),1)
        self.assertEqual(await self.fetched(value),expected)

    async def test_worker_region_must_match_requested_pixels_before_publication(self):
        info=await self.info()
        async with self.runtime.cache.lease(self.browser,info.source_id) as lease:
            wrong=await tools.render_preview(lease.original.path)
        with patch.object(tools,'render_preview',return_value=wrong):
            result=await self.invoke({'source_id':info.source_id,'crop':dict(x=7,y=4,width=11,height=9)})
        self.assertTrue(result.is_error,'Worker silently substituted a different source region')
        self.assertIn('ImageProcessingFailed',str(result.content))
        self.assertEqual(self.published_rows(),0)

    async def test_cancelled_render_releases_lease_and_retains_valid_original(self):
        info=await self.info()
        started=asyncio.Event()
        async def wait(*_,jpeg):
            self.assertIs(jpeg,False)
            started.set()
            await asyncio.Event().wait()
        with patch.object(tools,'render_preview',side_effect=wait):
            task=asyncio.create_task(tools.get_foundry_image_url(tools.ImageUrlRequest(source_id=info.source_id)))
            await asyncio.wait_for(started.wait(),5)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):await task
        async with self.runtime.cache.lease(self.browser,info.source_id) as lease:
            self.assertTrue(lease.original.path.is_file())
        self.assertEqual(self.published_rows(),0)
        self.assertTrue(all(record.leases==0 for record in self.runtime.cache._entries.values()))

    async def test_cancelled_publication_drains_atomic_store_and_returns_no_partial_success(self):
        info=await self.info()
        started,release=Event(),Event()
        publish=self.delivery.store.publish
        def delayed(*args):
            started.set()
            if not release.wait(5):raise RuntimeError('TestGateTimeout')
            return publish(*args)
        with patch.object(self.delivery.store,'publish',side_effect=delayed):
            task=asyncio.create_task(tools.get_foundry_image_url(tools.ImageUrlRequest(source_id=info.source_id)))
            try:
                self.assertTrue(await asyncio.to_thread(started.wait,3))
                task.cancel()
                await asyncio.sleep(0)
                task.cancel()
            finally:release.set()
            with self.assertRaises(asyncio.CancelledError):await task
        self.assertFalse(self.delivery.pending)
        self.assertEqual(self.published_rows(),1)
        with self.delivery.store.connection() as database:
            pixels,mime,size=database.execute('SELECT pixels,mime_type,size_bytes FROM previews').fetchone()
        self.assertEqual(len(pixels),size)
        self.assertEqual(mime,'image/png')
        with Image.open(BytesIO(pixels)) as actual:self.assertEqual(actual.size,(31,17))
        self.assertTrue(all(record.leases==0 for record in self.runtime.cache._entries.values()))

    async def test_production_http_issuance_requires_real_basic_context(self):
        config=Settings(auth_mode='basic',basic_username='gm',basic_password='password',bridge_token='browser',
            image_preview_origin='https://previews.example.com',image_preview_data_dir=str(Path(self.storage.name)/'http'))
        source=SourceRuntime(factory=lambda:SourceSnapshots(principal=lambda:current_principal(config)))
        delivery=PreviewRuntime()
        with patch.object(main,'settings',config),patch.object(main,'source_runtime',source), \
                patch.object(main,'preview_runtime',delivery),patch.object(tools,'preview_runtime',delivery), \
                patch.object(tools,'source_runtime',source),patch.object(tools,'settings',config):
            async with main.app.router.lifespan_context(main.app),httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=main.app,client=('127.0.0.1',1234)),base_url='https://previews.example.com') as client:
                response=await call(client,'get_foundry_image_url',{'request':{'image':IMAGE}},'Basic Z206cGFzc3dvcmQ=')
                self.assertEqual(response.status_code,200)
                self.assertFalse(response.json()['result'].get('isError'))
                value=ImageUrlResult.model_validate(response.json()['result']['structuredContent'])
                pixels=await client.get(value.url)
                self.assertEqual(pixels.status_code,200)
                self.assertEqual(len(pixels.content),value.size_bytes)
                before=len(self.browser.calls)
                denied=await call(client,'get_foundry_image_url',{'request':{'image':IMAGE}})
                self.assertEqual(denied.status_code,401)
                self.assertEqual(len(self.browser.calls),before)
