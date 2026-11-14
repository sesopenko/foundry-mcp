"""Map-aware image contracts and actual MCP/cache/native/HTTP workflows."""
import copy
from dataclasses import replace
import asyncio
import base64
import io
import itertools
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastmcp import Client,FastMCP
from fastapi import FastAPI
from mcp.types import CallToolResult as ProtocolResult
import httpx2 as httpx
from PIL import Image,PngImagePlugin

from foundry_mcp_server import main
from foundry_mcp_server.auth.principal import Principal,current_principal
from foundry_mcp_server.config import Settings
from foundry_mcp_server.image_preview_runtime import PreviewRuntime
from foundry_mcp_server.image_preview_source_runtime import SourceRuntime
from foundry_mcp_server.image_preview_sources import SourceSnapshots
from foundry_mcp_server.image_preview_store import PreviewStore
from foundry_mcp_server.map_context import MapContextService
from foundry_mcp_server.map_image_audit import verify as verify_native
from foundry_mcp_server.mcp_server import image_previews as tools,map_info
from foundry_mcp_server.mcp_server import tools as registry
from foundry_mcp_server.mcp_server.server import mcp
from foundry_mcp_server.ws.connection import RpcError
import test_image_preview_transfer as transfer_helpers
import test_image_preview_identity as identity_helpers

from foundry_mcp_server.mcp_server.image_preview_models import ImageInfoRequest,ImageUrlRequest,ImageInfoResult,ImageUrlResult
from foundry_mcp_server.mcp_server.map_image_models import MapNotesResult
from foundry_mcp_server.mcp_server.map_models import MapSelector
from foundry_mcp_server.mcp_server.map_info_models import MapSelector as ExistingMapSelector

MAP=dict(scene_uuid='Scene.scene',level_id='floor',role='background')
IMAGE=dict(source='data',directory='assets',src='assets/a.png')


class MapImageContractTests(unittest.TestCase):
    def test_exclusive_inputs_strict_map_and_url_only_boolean_flag(self):
        selectors=dict(image=IMAGE,src=IMAGE['src'],map=MAP,source_id='returned-handle')
        for cls,names in [(ImageInfoRequest,('image','src','map')),(ImageUrlRequest,tuple(selectors))]:
            for name in names:
                self.assertIsNotNone(cls.model_validate({name:selectors[name]}))
            for left,right in itertools.combinations(names,2):
                with self.subTest(cls=cls,left=left,right=right),self.assertRaises(ValueError):
                    cls.model_validate({left:selectors[left],right:selectors[right]})
            for invalid in ({},{'map':None},{'map':{**MAP,'extra':True}},{'map':{k:v for k,v in MAP.items() if k!='level_id'}},
                            {'map':{**MAP,'role':'tiles'}},{'map':{**MAP,'scene_uuid':'scene'}}):
                with self.subTest(invalid=invalid),self.assertRaises(ValueError):cls.model_validate(invalid)
        for flag in (False,True):self.assertIs(ImageUrlRequest(map=MAP,map_notes=flag).map_notes,flag)
        for flag in (None,0,1,'true'):
            with self.subTest(flag=flag),self.assertRaises(ValueError):ImageUrlRequest(map=MAP,map_notes=flag)
        with self.assertRaises(ValueError):ImageInfoRequest(map=MAP,map_notes=True)
        self.assertIs(MapSelector,ExistingMapSelector)

    def test_annotated_summary_has_exact_revision_identity_keys_and_null_empty_followup(self):
        summary=dict(map=MAP,revision='a'*64,total_in_region=1,rendered_count=1,omitted_count=0,complete=True,
            keys=['N2'],omission_reasons={},scope_status='complete',limitations=[],legend_next_call=dict(tool='get_map_info',
                arguments=dict(scene_uuid=MAP['scene_uuid'],level_id=MAP['level_id'],section='notes',expected_revision='a'*64,note_keys=['N2'])))
        self.assertEqual(MapNotesResult.model_validate(summary).model_dump(),summary)
        for field,value in [('scene_uuid','Scene.other'),('level_id','other'),('expected_revision','b'*64),('note_keys',['N3'])]:
            broken=copy.deepcopy(summary);broken['legend_next_call']['arguments'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):MapNotesResult.model_validate(broken)
        empty={**summary,'total_in_region':0,'rendered_count':0,'keys':[],'legend_next_call':None}
        self.assertTrue(MapNotesResult.model_validate(empty).complete)
        with self.assertRaises(ValueError):MapNotesResult.model_validate({**empty,'scope_status':'partial'})
        with self.assertRaises(ValueError):MapNotesResult.model_validate({**summary,'map':{**MAP,'role':'foreground'}})

    def test_default_image_result_omits_map_notes_in_both_json_and_python_serialization(self):
        data=dict(source_id='opaque',source_expires_at='2050-01-01T00:00:00Z',url='https://preview.example/image-previews/00000000-0000-4000-8000-000000000000.png',
            expires_at='2050-01-08T00:00:00Z',source_width=500,source_height=500,region=dict(x=0,y=0,width=500,height=500),
            width=500,height=500,mime_type='image/png',size_bytes=1000)
        result=ImageUrlResult.model_validate(data)
        self.assertEqual(result.model_dump(),data)
        self.assertNotIn('map_notes',result.model_dump_json())
        self.assertEqual(set(ImageInfoResult.model_fields),{'source_id','source_expires_at','width','height','mime_type','size_bytes','frame_policy'})


class MapToolBackend(transfer_helpers.Browser):
    """Real Python transfer protocol and production Node metadata RPC handlers."""
    def __init__(self):
        stream=io.BytesIO();source=Image.new('RGB',(500,500),(30,60,90))
        metadata=PngImagePlugin.PngInfo();metadata.add_text('Fixture','transfer-fixture-'*4000)
        source.save(stream,format='PNG',pnginfo=metadata)
        super().__init__(stream.getvalue())
        self.image=copy.deepcopy(IMAGE);self.sources={'data':{}}
        self.folders=[]
        self.scene=dict(id='scene',name='Map',folder=None,width=500,height=500,grid=dict(size=100),
            rectangle=dict(sceneX=20,sceneY=40,sceneWidth=500,sceneHeight=500),
            levels=[dict(id='floor',name='Floor',sort=0,textures=dict(default_placement=True),background=dict(src=IMAGE['src']),foreground=dict(src=IMAGE['src']))],
            notes=[dict(id='note01',x=270,y=290,text='Plain note',levels=[],entryId='journal',pageId='page')])
        self.journals=[dict(id='journal',name='Journal',pages=[dict(id='page',name='Page')])]
        self.map_hook=None

    async def result(self,method,params):
        if method=='validateImagePreviewSource':return dict(**self.context,image=self.image,scope_status='complete',limitations=[])
        if method not in ('getMapInfo','getMapImageContext','getMapRegionCandidates'):
            value=await super().result(method,params)
            return {**value,'image':self.image} if method=='beginImagePreviewTransfer' else value
        process=await asyncio.create_subprocess_exec('node',str(Path(__file__).parent/'js/fixtures/map-context-rpc.js'),
            stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
        try:
            output,_=await asyncio.wait_for(process.communicate(json.dumps(dict(method=method,params=params,scene=self.scene,folders=self.folders,journals=self.journals,
                files=[self.image['src']],sources=self.sources)).encode()),5)
        except BaseException:
            if process.returncode is None:process.kill()
            await process.wait();raise
        if process.returncode:raise RuntimeError('Map fixture failed')
        response=json.loads(output)
        if response.get('error'):raise RpcError(response['error'])
        value=response['result']
        if self.map_hook:value=await self.map_hook(method,params,value)
        return value


class MapToolFixture:
    backend_factory=MapToolBackend

    async def asyncSetUp(self):
        self.browser=self.backend_factory();self.now=1000;self.public_now=2000
        # Exact legacy annotation pixels remain a separate regression contract.
        self.enterContext(patch.object(tools,'settings',replace(tools.settings,image_preview_jpeg=False)))
        self.measurements=[]
        self.identity=Principal('basic','','gm','configured-account')
        self.runtime=SourceRuntime(factory=lambda:SourceSnapshots(principal=lambda:self.identity,clock=lambda:self.now))
        await self.runtime.start();self.addAsyncCleanup(self.runtime.close)
        self.maps=MapContextService(principal=lambda:self.identity,clock=lambda:self.now)
        self.storage=tempfile.TemporaryDirectory();self.addCleanup(self.storage.cleanup)
        self.delivery=PreviewRuntime(store_factory=lambda path:PreviewStore(path,clock=lambda:self.public_now))
        await self.delivery.start(Settings(auth_mode='basic',basic_username='gm',basic_password='password',bridge_token='browser',
            image_preview_origin='https://previews.example.com',image_preview_data_dir=self.storage.name))
        self.addAsyncCleanup(self.delivery.close)
        for owner,name,value in [(tools,'source_runtime',self.runtime),(tools,'preview_runtime',self.delivery),
                (main,'preview_runtime',self.delivery),(registry,'_foundry_manager',self.browser),
                (tools,'MapContextService',lambda **_:self.maps),(map_info,'current_principal',lambda:self.identity)]:
            self.enterContext(patch.object(owner,name,value))

    async def call(self,name,request):
        async with Client(mcp) as client:
            result=await client.call_tool(name,request if name in ('get_map_info','browse_maps') else {'request':request},raise_on_error=False)
        if not result.is_error:
            raw=result.structured_content
            protocol=ProtocolResult(content=result.content,structured_content=raw,is_error=False,meta=result.meta).model_dump(mode='json',by_alias=True,exclude_none=True)
            compact=lambda value:len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())
            label=name+(':'+request.get('section','assets') if name=='get_map_info' else ':annotated' if request.get('map_notes') else '')
            self.measurements.append(dict(label=label,json_bytes=compact(raw),mcp_bytes=compact(protocol),complete=raw.get('complete',True)))
        return result

    async def info(self,selector=None):
        response=await self.call('get_foundry_image_info',selector or {'map':MAP})
        self.assertFalse(response.is_error,str(response.content))
        self.assertEqual(set(response.structured_content),set(ImageInfoResult.model_fields))
        return ImageInfoResult.model_validate(response.structured_content)

    async def url(self,request):
        response=await self.call('get_foundry_image_url',request)
        self.assertFalse(response.is_error,str(response.content))
        return ImageUrlResult.model_validate(response.structured_content)

    async def fetch(self,value):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='https://previews.example.com') as client:
            response=await client.get(value.url)
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.content),value.size_bytes)
        return response.content

    def transfers(self):return sum(method=='beginImagePreviewTransfer' for _,method,*_ in self.browser.calls)


class MapImageToolsTests(MapToolFixture,unittest.IsolatedAsyncioTestCase):
    async def test_jpeg_map_overview_crop_and_annotations_through_actual_mcp(self):
        info=await self.info()
        self.assertEqual(info.mime_type,'image/png')
        for enabled in (False,True):
            with patch.object(tools,'settings',replace(tools.settings,image_preview_jpeg=enabled)):
                for crop,annotated in ((None,False),(None,True),(dict(x=200,y=200,width=200,height=200),True)):
                    request=dict(source_id=info.source_id,map_notes=annotated)
                    if crop:request['crop']=crop
                    value=await self.url(request)
                    self.assertEqual(value.mime_type,'image/jpeg' if enabled else 'image/png')
                    data=await self.fetch(value)
                    self.measurements[-1].update(jpeg=enabled,image_bytes=len(data))
                    with Image.open(io.BytesIO(data)) as image:
                        image.load()
                        self.assertEqual(image.format,'JPEG' if enabled else 'PNG')
                    if annotated:
                        self.assertEqual(value.map_notes.keys,['N1'])
                        self.assertTrue(value.map_notes.complete)
                        follow=value.map_notes.legend_next_call
                        legend=await self.call(follow.tool,follow.arguments.model_dump())
                        self.assertFalse(legend.is_error)
        self.assertEqual(self.transfers(),1)
        print('JPEG_MAP_BUDGET',json.dumps(dict(calls=len(self.measurements),transfers=self.transfers(),rows=self.measurements),separators=(',',':')))

    async def test_actual_discovery_map_flag_typed_summary_and_invalid_calls_precede_reads(self):
        async with Client(mcp) as client:
            catalog={tool.name:tool for tool in await client.list_tools()}
        info=catalog['get_foundry_image_info'];url=catalog['get_foundry_image_url']
        self.assertEqual(set(info.input_schema['$defs']['MapSelector']['properties']),{'scene_uuid','level_id','role'})
        self.assertFalse(info.input_schema['$defs']['MapSelector']['additionalProperties'])
        flag=url.input_schema['$defs']['ImageUrlRequest']['properties']['map_notes']
        self.assertEqual((flag['type'],flag['default']),('boolean',False))
        self.assertIn('MapNotesResult',url.output_schema['$defs']);self.assertNotIn('MapNoteEntry',url.output_schema['$defs'])
        for private in ('BoundMapContext','ResolvedMapContext','private_context','reference_digest','source_digest'):
            self.assertNotIn(private,json.dumps(url.model_dump()))
        for name,request in [('get_foundry_image_info',dict(map=MAP,src=IMAGE['src'])),
                ('get_foundry_image_info',dict(map=MAP,map_notes=False)),('get_foundry_image_url',dict(map=MAP,map_notes=1)),
                ('get_foundry_image_url',dict(map={**MAP,'extra':True})),('get_foundry_image_url',dict(map=MAP,source_id='forged'))]:
            response=await self.call(name,request);self.assertTrue(response.is_error)
        self.assertEqual(self.browser.calls,[])

    async def test_disabled_map_issuance_fails_before_resolution_or_transfer(self):
        self.delivery.issuance_enabled=False
        for request in (dict(map=MAP),dict(map=MAP,map_notes=True),dict(source_id='missing',map_notes=True)):
            response=await self.call('get_foundry_image_url',request)
            self.assertTrue(response.is_error);self.assertIn('PreviewNotConfigured',str(response.content))
        self.assertEqual(self.browser.calls,[])

    async def test_actual_returned_map_next_call_to_bound_image_annotated_crop_and_exact_legend(self):
        config=await self.call('get_map_info',dict(scene_uuid='Scene.scene',level_id='floor'))
        self.assertFalse(config.is_error,str(config.content))
        next_call=config.structured_content['entries'][0]['background']['info_next_call']
        self.assertEqual(next_call['arguments'],{'request':{'map':MAP}})
        info=await self.info(next_call['arguments']['request'])
        self.assertEqual((info.width,info.height),(500,500));self.assertEqual(self.transfers(),1)
        self.assertGreater(len(self.browser.finished),1)
        overview=await self.url(dict(source_id=info.source_id,map_notes=True))
        crop=await self.url(dict(source_id=info.source_id,map_notes=True,crop=dict(x=200,y=200,width=200,height=200)))
        self.assertEqual(self.transfers(),1);self.assertNotEqual(overview.url,crop.url)
        for result in (overview,crop):
            self.assertEqual(result.map_notes.keys,['N1']);self.assertTrue(result.map_notes.complete)
            self.assertEqual(result.map_notes.revision,config.structured_content['revision'])
            follow=result.map_notes.legend_next_call
            legend=await self.call(follow.tool,follow.arguments.model_dump())
            self.assertFalse(legend.is_error,str(legend.content))
            note=legend.structured_content['entries'][0]
            self.assertEqual(note['note_uuid'],'Scene.scene.Note.note01')
            self.assertEqual(note['journal']['journal_uuid'],'JournalEntry.journal')
            self.assertEqual(note['page']['page_uuid'],'JournalEntry.journal.JournalEntryPage.page')
            decoded=Image.open(io.BytesIO(await self.fetch(result)))
            pin=(250,250) if result is overview else (50,50)
            self.assertEqual(decoded.convert('RGB').getpixel(pin),(255,255,255))
            serialized=json.dumps(result.model_dump())
            for private in ('assets/a.png','Scene.scene.Note.','Plain note','transfer-fixture-','JournalEntry.'):
                self.assertNotIn(private,serialized)
        plain=await self.call('get_foundry_image_url',dict(source_id=info.source_id))
        self.assertFalse(plain.is_error);self.assertNotIn('map_notes',plain.structured_content)
        self.assertEqual(self.transfers(),1)
        self.assertEqual(len(self.measurements),7)
        print('MAP_IMAGE_WORKFLOW',json.dumps(dict(calls=len(self.measurements),transfers=self.transfers(),chunks=len(self.browser.finished),rows=self.measurements),separators=(',',':')))

    async def test_raw_file_and_unbound_handle_annotation_fail_without_extra_transfer(self):
        for selector in ({'image':IMAGE},{'src':IMAGE['src']}):
            result=await self.call('get_foundry_image_url',{**selector,'map_notes':True})
            self.assertTrue(result.is_error);self.assertIn('MapContextRequired',str(result.content))
        self.assertEqual(self.transfers(),0)
        info=await self.info({'src':IMAGE['src']})
        result=await self.call('get_foundry_image_url',dict(source_id=info.source_id,map_notes=True))
        self.assertTrue(result.is_error);self.assertIn('MapContextRequired',str(result.content));self.assertEqual(self.transfers(),1)

    async def test_stale_notes_reject_annotation_plain_snapshot_remains_and_issued_bytes_immutable(self):
        info=await self.info();issued=await self.url(dict(source_id=info.source_id,map_notes=True));before=await self.fetch(issued)
        self.browser.scene['notes'][0]['text']='Changed'
        response=await self.call('get_foundry_image_url',dict(source_id=info.source_id,map_notes=True))
        self.assertTrue(response.is_error);self.assertIn('MapContextChanged',str(response.content))
        await self.url(dict(source_id=info.source_id))
        self.assertEqual(await self.fetch(issued),before);self.assertEqual(self.transfers(),1)

    async def test_foreground_raw_fallback_signed_reference_and_exact_owner_validation(self):
        foreground={**MAP,'role':'foreground'}
        plain=await self.url({'map':foreground});self.assertIsNone(plain.map_notes)
        response=await self.call('get_foundry_image_url',dict(source_id=plain.source_id,map_notes=True))
        self.assertTrue(response.is_error);self.assertIn('UnsupportedMapMapping',str(response.content))
        for selector in ({**MAP,'level_id':'foreign'},{**MAP,'scene_uuid':'Scene.other'}):
            response=await self.call('get_foundry_image_info',{'map':selector})
            self.assertTrue(response.is_error)
        signed_src='https://test-bucket.s3.example/assets/a.png?signature=private-signature'
        self.browser.scene['levels'][0]['background']['src']=signed_src
        self.browser.image=dict(source='s3',bucket='test-bucket',directory='assets',src=signed_src)
        self.browser.sources={'s3':{'buckets':['test-bucket']}}
        config=await self.call('get_map_info',dict(scene_uuid='Scene.scene',level_id='floor'))
        self.assertFalse(config.is_error,str(config.content));self.assertNotIn('private-signature',json.dumps(config.structured_content))
        self.assertEqual(config.structured_content['entries'][0]['background']['info_next_call']['arguments'],{'request':{'map':MAP}})
        signed=await self.info();await self.url(dict(source_id=signed.source_id,map_notes=True))

    async def test_zero_and_denied_note_scope_are_independent_of_annotation_completeness(self):
        self.browser.scene['notes']=[]
        empty=await self.url({'map':MAP,'map_notes':True})
        self.assertEqual((empty.map_notes.total_in_region,empty.map_notes.rendered_count,empty.map_notes.omitted_count),(0,0,0))
        self.assertTrue(empty.map_notes.complete);self.assertIsNone(empty.map_notes.legend_next_call)
        self.browser.scene['notes']=[dict(id='note01',x=270,y=290,text='Private label',levels=[],entryId='journal',pageId='page')]
        self.browser.journals[0]['allowed']=False
        denied=await self.url({'map':MAP,'map_notes':True})
        self.assertTrue(denied.map_notes.complete);self.assertEqual(denied.map_notes.scope_status,'partial')
        self.assertTrue(denied.map_notes.limitations);self.assertNotIn('Private label',denied.model_dump_json())
        legend=await self.call('get_map_info',denied.map_notes.legend_next_call.arguments.model_dump())
        self.assertFalse(legend.is_error,str(legend.content))
        self.assertIsNone(legend.structured_content['entries'][0]['label'])
        self.assertIsNone(legend.structured_content['entries'][0]['journal'])

    async def test_dense_render_and_rendered_key_legend_paginate_to_exact_completion(self):
        self.browser.scene['notes']=[dict(id='n'+str(i).zfill(3),x=45+i%10*45,y=65+i//10*45,text='Note',levels=[],entryId='journal',pageId='page') for i in range(100)]
        result=await self.url({'map':MAP,'map_notes':True})
        notes=result.map_notes
        self.assertGreater(len(notes.keys),10);self.assertFalse(notes.complete)
        self.assertEqual(notes.total_in_region,100);self.assertEqual(notes.rendered_count+notes.omitted_count,100)
        self.assertEqual(sum(notes.omission_reasons.values()),notes.omitted_count)
        args=notes.legend_next_call.arguments.model_dump();seen=[];pages=0
        while True:
            page=await self.call('get_map_info',args);self.assertFalse(page.is_error,str(page.content))
            payload=page.structured_content;seen.extend(e['key'] for e in payload['entries']);pages+=1
            self.assertLess(pages,12)
            if payload['complete']:break
            args={**args,'cursor':payload['next_cursor']}
        self.assertEqual(seen,notes.keys);self.assertGreater(pages,1);self.assertEqual(self.transfers(),1)

    async def test_replacement_bytes_keep_pinned_map_and_principal_expiry_socket_isolation(self):
        info=await self.info()
        stream=io.BytesIO();Image.new('RGB',(500,500),(200,30,40)).save(stream,format='PNG');self.browser.data=stream.getvalue()
        pinned=await self.url(dict(source_id=info.source_id,map_notes=True))
        fresh=await self.url(dict(map=MAP,map_notes=True))
        for result,color in [(pinned,(30,60,90)),(fresh,(200,30,40))]:
            self.assertEqual(Image.open(io.BytesIO(await self.fetch(result))).convert('RGB').getpixel((0,0)),color)
        before=len(self.browser.calls);self.identity=Principal('basic','','other','configured-account')
        response=await self.call('get_foundry_image_url',dict(source_id=info.source_id,map_notes=True))
        self.assertIn('SourceUnavailable',str(response.content));self.assertEqual(len(self.browser.calls),before)
        self.identity=Principal('basic','','gm','configured-account');self.now=2800
        response=await self.call('get_foundry_image_url',dict(source_id=info.source_id,map_notes=True))
        self.assertIn('SourceUnavailable',str(response.content));self.assertEqual(len(self.browser.calls),before)
        self.now=3000;latest=await self.info();self.browser.websockets['gm']=object()
        response=await self.call('get_foundry_image_url',dict(source_id=latest.source_id,map_notes=True))
        self.assertTrue(response.is_error);self.assertIn('SourceContextLost',str(response.content))

    async def test_map_mutation_across_render_and_publication_returns_no_url(self):
        info=await self.info();render=tools.render_annotated;publish=self.delivery.publish
        def rows():
            with self.delivery.store.connection() as database:return database.execute('SELECT COUNT(*) FROM previews').fetchone()[0]
        for phase in ('render','publish'):
            baseline=rows()
            async def rendering(*args,**kwargs):
                value=await render(*args,**kwargs);self.browser.scene['notes'][0]['text']='Changed '+phase;return value
            async def publishing(*args,**kwargs):
                value=await publish(*args,**kwargs);self.browser.scene['notes'][0]['text']='Changed '+phase;return value
            with patch.object(tools,'render_annotated',side_effect=rendering if phase=='render' else render),patch.object(self.delivery,'publish',side_effect=publishing if phase=='publish' else publish):
                response=await self.call('get_foundry_image_url',dict(source_id=info.source_id,map_notes=True))
            self.assertTrue(response.is_error);self.assertIn('MapContextChanged',str(response.content))
            self.assertNotIn('https://previews.example.com',str(response.content))
            self.assertEqual(rows(),baseline+(phase=='publish'))
            info=await self.info()

    async def test_annotation_quota_and_cancellation_preserve_issued_pixels_and_source(self):
        info=await self.info();first=await self.url(dict(source_id=info.source_id,map_notes=True));pixels=await self.fetch(first)
        self.delivery.store.max_rows=1
        response=await self.call('get_foundry_image_url',dict(source_id=info.source_id,map_notes=True))
        self.assertIn('PreviewQuotaExceeded',str(response.content));self.assertEqual(await self.fetch(first),pixels)
        started=asyncio.Event()
        async def wait(*_,jpeg):
            self.assertIs(jpeg,False)
            started.set();await asyncio.Event().wait()
        with patch.object(tools,'render_annotated',side_effect=wait):
            task=asyncio.create_task(tools.get_foundry_image_url(ImageUrlRequest(source_id=info.source_id,map_notes=True)))
            await asyncio.wait_for(started.wait(),5);task.cancel()
            with self.assertRaises(asyncio.CancelledError):await task
        self.assertTrue(all(record.leases==0 for record in self.runtime.cache._entries.values()))
        self.assertEqual(self.transfers(),1)

    async def test_real_http_basic_context_is_required_for_map_staging_and_annotation(self):
        config=Settings(auth_mode='basic',basic_username='gm',basic_password='password',bridge_token='browser')
        self.runtime.cache._principal_provider=lambda:current_principal(config)
        self.maps.principal=lambda:current_principal(config)
        server=FastMCP('map-http')
        for name in ('get_foundry_image_info','get_foundry_image_url'):server.add_tool(await mcp.get_tool(name))
        transport=server.http_app(path='/mcp/mcp');app=FastAPI(lifespan=transport.lifespan)
        app.add_middleware(main.MCPAccessControl);app.mount('/',transport)
        with patch.object(main,'settings',config):
            async with app.router.lifespan_context(app),httpx.AsyncClient(transport=httpx.ASGITransport(app=app,client=('127.0.0.1',1234)),base_url='https://mcp.example') as client:
                rejected=await identity_helpers.call(client,'get_foundry_image_info',{'request':{'map':MAP}})
                self.assertEqual(rejected.status_code,401);self.assertEqual(self.transfers(),0)
                credential='Basic '+base64.b64encode(b'gm:password').decode()
                response=await identity_helpers.call(client,'get_foundry_image_info',{'request':{'map':MAP}},credential)
                data=response.json()['result'];self.assertFalse(data.get('isError'),data)
                info=data['structuredContent']
                response=await identity_helpers.call(client,'get_foundry_image_url',{'request':dict(source_id=info['source_id'],map_notes=True)},credential)
                data=response.json()['result'];self.assertFalse(data.get('isError'),data)
                result=ImageUrlResult.model_validate(data['structuredContent'])
                self.assertEqual(result.map_notes.keys,['N1']);await self.fetch(result)
        self.assertEqual(self.transfers(),1)

    async def test_bounded_native_audit_counts_calls_reports_configuration_gap_and_redacts_identity(self):
        outer=self
        class AuditClient:
            calls=0
            async def list_tools(inner,**kwargs):
                inner.calls+=1
                async with Client(mcp) as client:return await client.list_tools(**kwargs)
            async def call_tool(inner,name,args,**kwargs):
                inner.calls+=1
                if name=='execute_javascript':
                    value={'map':MAP,'active':'private-active'} if 'Representative map unavailable' in args['code'] else {'active':'private-active'}
                    return SimpleNamespace(content=[],meta=None,is_error=False,structured_content={'value':json.dumps(value)})
                return await outer.call(name,args['request'] if name!='get_map_info' else args)
        self.delivery.issuance_enabled=False
        client=AuditClient();report=await verify_native(client)
        self.assertTrue(report['passed'],report);self.assertEqual((report['calls'],client.calls),(7,7))
        self.assertTrue(report['map_info_bound']);self.assertFalse(report['annotation_issuance_verified'])
        self.assertTrue(report['pending']);self.assertEqual(report['persisted_fixtures'],0)
        for private in ('Scene.scene','private-active','assets/a.png','source_id','JournalEntry.'):
            self.assertNotIn(private,json.dumps(report))

    async def test_native_audit_failure_never_exposes_browser_error_text(self):
        class FailedClient:
            async def list_tools(inner,**_):raise RuntimeError('private source sentinel')
        report=await verify_native(FailedClient())
        self.assertFalse(report['passed']);self.assertEqual(report['calls'],1)
        self.assertNotIn('sentinel',json.dumps(report))
