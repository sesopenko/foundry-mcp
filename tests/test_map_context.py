"""Map context and independent coordinate geometry checks."""
import json
import asyncio
import copy
import hashlib
import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock
from PIL import Image,ImageOps
from foundry_mcp_server.map_context import MapContextService
from foundry_mcp_server.auth.principal import Principal
from foundry_mcp_server.image_preview_sources import SourceSnapshots
from foundry_mcp_server.image_preview_process import ProbeMetadata,probe_image,render_region
from foundry_mcp_server.ws.connection import RpcError
import test_image_preview_sources as source_test_helpers

from foundry_mcp_server.map_geometry_audit import measure,verify_context
from foundry_mcp_server.map_geometry import SceneImageMapping
from foundry_mcp_server.mcp_server.image_preview_models import Crop
from fastmcp.exceptions import ToolError


class SceneImageMappingTests(unittest.TestCase):
    def test_independent_measured_padding_shift_and_source_scale_examples(self):
        normal=SceneImageMapping(1800,2400,6800,9000,6800,9000)
        self.assertEqual(normal.source_point(1900,2500),(100,100))
        shifted=SceneImageMapping(1680,2480,6800,9000,6800,9000)
        self.assertEqual(shifted.source_point(1780,2580),(100,100))
        smaller=SceneImageMapping(1800,2400,6800,9000,3400,4500)
        self.assertEqual(smaller.source_point(1900,2500),(50,50))

    def test_original_border_and_one_pixel_crop_centers_are_exclusive(self):
        mapping=SceneImageMapping(1800,2400,6800,9000,6800,9000)
        crop=Crop(x=6799,y=8999,width=1,height=1)
        self.assertTrue(mapping.contains(8599,11399,crop))
        self.assertFalse(mapping.contains(8600,11399,crop));self.assertFalse(mapping.contains(8599,11400,crop))
        self.assertEqual(mapping.output_point(8599,11399,crop,1,1),(0,0))

    def test_scaled_output_point_uses_existing_crop_region_and_delivered_dimensions(self):
        mapping=SceneImageMapping(10,20,1000,500,2000,1000)
        crop=Crop(x=100,y=200,width=400,height=200)
        self.assertEqual(mapping.source_point(160,170),(300,300))
        self.assertEqual(mapping.output_point(160,170,crop,200,100),(100,50))
        with self.assertRaises(ToolError):mapping.output_point(1,2,crop,200,100)

    def test_mapping_is_immutable_and_rejects_nonfinite_boolean_and_source_limits(self):
        for args in ((0,0,0,1,1,1),(0,0,1,1,True,1),(0,0,1,1,32769,1),(0,0,float('nan'),1,1,1)):
            with self.subTest(args=args),self.assertRaises(ToolError):SceneImageMapping(*args)
        mapping=SceneImageMapping(0,0,1,1,1,1)
        with self.assertRaises(AttributeError):mapping.scene_x=10
        with self.assertRaises(ToolError):mapping.source_point(True,0)


class GeometryBaselineTests(unittest.IsolatedAsyncioTestCase):
    async def test_native_context_verifier_counts_calls_and_keeps_source_identity_private(self):
        class Native:
            def __init__(self):self.calls=0
            async def list_tools(self,**_):
                self.calls+=1;return[SimpleNamespace(model_dump=lambda **_:dict(name='get_map_info'))]
            async def call_tool(self,name,args,**_):
                self.calls+=1
                if name=='get_map_info':data=dict(entries=[dict(background=dict(reference_status='safe',media_kind='image',reference='private-source-path.png'))])
                elif name=='get_foundry_image_info':data=dict(source_id='private-handle',source_expires_at='2050-01-01T00:00:00Z',width=6800,height=9000,
                    mime_type='image/png',size_bytes=1000,frame_policy='still')
                elif 'getMapImageContext' in args['code']:
                    data={'value':json.dumps(dict(map=dict(scene_uuid='Scene.s',level_id='level',role='background'),revision='a'*64,alias_digest='b'*64,
                        reference_digest='c'*64,rectangle=dict(sceneX=1800,sceneY=2400,sceneWidth=6800,sceneHeight=9000),supported=True,active='private-active',context_bytes=900))}
                else:data={'value':json.dumps(dict(revision='a'*64,alias_digest='b'*64,total=1,returned=1,complete=True,scope_status='complete',result_bytes=1200,
                    samples=[dict(key='N1',x=1900,y=2500,source_x=100,source_y=100)],active='private-active'))}
                return SimpleNamespace(is_error=False,structured_content=data)
        native=Native();report=await verify_context(native)
        self.assertTrue(report['passed']);self.assertEqual((report['calls'],native.calls),(6,6))
        self.assertTrue(report['mapping_validated']);self.assertTrue(report['detail_alias_preserved'])
        for private in ('private-source-path','private-handle','private-active','Scene.s'):
            self.assertNotIn(private,json.dumps(report))

    async def test_native_context_failure_exposes_only_error_category_and_actual_call_count(self):
        client=AsyncMock();client.list_tools.side_effect=RuntimeError('private source sentinel')
        report=await verify_context(client)
        self.assertFalse(report['passed']);self.assertEqual(report['calls'],1);self.assertNotIn('sentinel',json.dumps(report))

    def fixture(self):
        client=AsyncMock();client.list_tools.return_value=[SimpleNamespace(model_dump=lambda **_:dict(name='get_map_info'))]
        data=dict(version='14.369',levels=50,defaults_matching=50,initial_objects=50,cleaned_objects=50,
            active_unchanged=True,collection_unchanged=True,private='private sentinel',rows=[
                dict(label=k,sceneX=1800,sceneY=2400,sceneWidth=6800,sceneHeight=9000) for k in ('normal','shifted','scaled')])
        client.call_tool.return_value=SimpleNamespace(structured_content={'value':json.dumps(data)})
        return client,data

    async def test_only_verified_aggregate_fields_and_no_persisted_fixtures(self):
        client,_=self.fixture();result=await measure(client)
        self.assertTrue(result['passed']);self.assertEqual(result['calls'],2);self.assertEqual(result['persisted_fixtures'],0)
        self.assertNotIn('sentinel',json.dumps(result));client.call_tool.assert_awaited_once()

    async def test_invalid_context_or_counts_and_errors_never_expose_source(self):
        for change in ({'levels':True},{'defaults_matching':100},{'version':'13'},{'active_unchanged':False},{'collection_unchanged':False}):
            client,data=self.fixture();data.update(change);client.call_tool.return_value.structured_content={'value':json.dumps(data)}
            self.assertFalse((await measure(client))['passed'])
        client,_=self.fixture();client.list_tools.side_effect=RuntimeError('private sentinel')
        result=await measure(client);self.assertFalse(result['passed']);self.assertEqual(result['calls'],1)
        self.assertNotIn('sentinel',json.dumps(result))


class ContextBackend(source_test_helpers.Backend):
    def __init__(self):
        super().__init__();self.map_calls=[];self.map_hook=None
        self.scene=dict(id='scene',name='Map',folder=None,width=6800,height=9000,padding=.25,shiftX=0,shiftY=0,grid=dict(size=200),
            levels=[dict(id='floor',name='Floor',sort=0,textures=dict(default_placement=True),background=dict(src='assets/a.png'),foreground=dict(src='assets/a.png'))],
            notes=[dict(id='n000',x=1900,y=2500,text='Note',levels=[],entryId=None,pageId=None)])
        stream=io.BytesIO();Image.new('RGB',(68,90),(20,80,100)).save(stream,format='PNG');self.data=stream.getvalue()

    async def call(self,client_id,method,params,timeout):
        if method=='validateImagePreviewSource':return await super().call(client_id,method,params,timeout)
        self.map_calls.append((method,params))
        process=await asyncio.create_subprocess_exec('node',str(Path(__file__).parent/'js/fixtures/map-context-rpc.js'),
            stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
        try:output,_=await asyncio.wait_for(process.communicate(json.dumps(dict(method=method,params=params,scene=self.scene)).encode()),5)
        except BaseException:
            if process.returncode is None:process.kill()
            await process.wait();raise
        if process.returncode:raise RuntimeError('Context fixture failed')
        reply=json.loads(output)
        if reply.get('error'):raise RpcError(reply['error'])
        result=reply['result']
        if self.map_hook:result=await self.map_hook(method,params,result)
        return result


class BoundContextTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.backend=ContextBackend();self.time=1000
        self.identity=Principal('oauth','https://issuer.example/','gm','client')
        self.service=MapContextService(principal=lambda:self.identity,clock=lambda:self.time)
        self.cache=SourceSnapshots(principal=lambda:self.identity,clock=lambda:self.time,transfer=self.backend.transfer)
        self.addAsyncCleanup(self.cache.close)
        self.selector=dict(scene_uuid='Scene.scene',level_id='floor',role='background')

    async def bound(self,selector=None):
        resolved=await self.service.resolve(self.backend,selector or self.selector)
        receipt=await self.cache.stage(self.backend,{'image':dict(resolved.image)})
        async with self.cache.lease(self.backend,receipt.source_id) as lease:
            metadata=ProbeMetadata(width=68,height=90,mime_type='image/png',size_bytes=lease.original.size_bytes,frame_policy='still')
            record=await self.service.bind(self.backend,resolved,lease,metadata)
        return record

    async def test_source_bound_context_is_frozen_private_and_reuses_one_original_for_crops(self):
        record=await self.bound()
        self.assertNotIn('assets',repr(record));self.assertNotIn('Scene.scene',repr(record.resolved))
        with self.assertRaises(AttributeError):record.source_id='different'
        async with self.cache.lease(self.backend,record.source_id) as lease:
            pins=await self.service.region_pins(self.backend,record,lease)
            self.assertEqual((pins.total_in_region,len(pins.pins),pins.omitted_for_limit),(1,1,0))
            self.assertEqual((pins.pins[0].key,pins.pins[0].source_x,pins.pins[0].source_y),('N1',1,1))
            packet=json.dumps(pins.worker_pins())
            self.assertNotIn('Scene.',packet);self.assertNotIn('note_uuid',packet);self.assertNotIn('Journal',packet)
            self.assertEqual(json.loads(packet),[['N1',1,1]])
            detail=await self.service.region_pins(self.backend,record,lease,dict(x=1,y=1,width=1,height=1))
            self.assertEqual(detail.pins,pins.pins)
            outside=await self.service.region_pins(self.backend,record,lease,dict(x=0,y=0,width=1,height=1))
            self.assertEqual(outside.total_in_region,0)
        self.assertEqual(self.backend.transfers,1)

    async def test_note_mutation_rejects_annotation_but_preserves_ordinary_pinned_preview(self):
        record=await self.bound();self.backend.scene['notes'][0]['text']='Changed note'
        async with self.cache.lease(self.backend,record.source_id) as lease:
            await self.service.revalidate(self.backend,record,lease,annotated=False)
            with self.assertRaisesRegex(ToolError,'MapContextChanged'):
                await self.service.revalidate(self.backend,record,lease,annotated=True)

    async def test_replacement_bytes_at_unchanged_path_keep_original_snapshot_and_context(self):
        record=await self.bound();digest=record.source_digest
        stream=io.BytesIO();Image.new('RGB',(68,90),(200,30,10)).save(stream,format='PNG');self.backend.data=stream.getvalue()
        async with self.cache.lease(self.backend,record.source_id) as lease:
            await self.service.revalidate(self.backend,record,lease)
            self.assertEqual(hashlib.sha256(lease.original.path.read_bytes()).hexdigest(),digest)
        fresh=await self.bound();self.assertNotEqual(fresh.source_digest,digest)
        self.assertEqual(fresh.resolved.revision,record.resolved.revision)

    async def test_foreground_nondefault_or_changed_asset_scope_cannot_annotate(self):
        foreground=await self.bound({**self.selector,'role':'foreground'})
        async with self.cache.lease(self.backend,foreground.source_id) as lease:
            await self.service.revalidate(self.backend,foreground,lease,annotated=False)
            with self.assertRaisesRegex(ToolError,'UnsupportedMapMapping'):
                await self.service.region_pins(self.backend,foreground,lease)
        record=await self.bound();self.backend.scene['levels'][0]['background']['src']='assets/other.png'
        async with self.cache.lease(self.backend,record.source_id) as lease:
            with self.assertRaisesRegex(ToolError,'MapContextChanged'):
                await self.service.revalidate(self.backend,record,lease,annotated=False)

    async def test_expired_caller_or_socket_context_fails_before_metadata_rpc(self):
        record=await self.bound()
        async with self.cache.lease(self.backend,record.source_id) as lease:
            prior=self.identity;before=len(self.backend.map_calls)
            self.identity=Principal('oauth',prior.issuer,'other',prior.client_id)
            try:
                with self.assertRaisesRegex(ToolError,'SourceUnavailable'):await self.service.revalidate(self.backend,record,lease)
            finally:self.identity=prior
            socket=self.backend.websockets['gm'];self.backend.websockets['gm']=object()
            try:
                with self.assertRaisesRegex(ToolError,'SourceContextLost'):await self.service.revalidate(self.backend,record,lease)
            finally:self.backend.websockets['gm']=socket
            self.time=2800
            with self.assertRaisesRegex(ToolError,'SourceUnavailable'):await self.service.revalidate(self.backend,record,lease)
            self.assertEqual(len(self.backend.map_calls),before)

    async def test_over_limit_count_is_explicit_and_narrow_crop_does_not_renumber_aliases(self):
        self.backend.scene['notes']=[dict(id='n'+str(i).zfill(3),x=1900+i,y=2500,text='Note',levels=[],entryId=None,pageId=None) for i in range(150)]
        record=await self.bound()
        async with self.cache.lease(self.backend,record.source_id) as lease:
            all_pins=await self.service.region_pins(self.backend,record,lease)
            self.assertEqual((len(all_pins.pins),all_pins.total_in_region,all_pins.omitted_for_limit),(100,150,50))
            subset=await self.service.region_pins(self.backend,record,lease,dict(x=2,y=0,width=1,height=2))
            self.assertEqual(subset.total_in_region,50);self.assertEqual(subset.pins[0].key,'N101')
        self.assertEqual(self.backend.transfers,1)

    async def test_empty_crop_is_invalid_before_any_context_or_source_reads(self):
        record=await self.bound();before=len(self.backend.map_calls)
        async with self.cache.lease(self.backend,record.source_id) as lease:
            with self.assertRaisesRegex(ValueError,'InvalidCrop'):
                await self.service.region_pins(self.backend,record,lease,{})
        self.assertEqual(len(self.backend.map_calls),before)

    async def test_malformed_private_cursor_returns_fixed_contract_error(self):
        record=await self.bound()
        async def corrupt(method,params,result):
            if method=='getMapRegionCandidates':return{**result,'complete':False,'next_cursor':'not-base64'}
            return result
        self.backend.map_hook=corrupt
        async with self.cache.lease(self.backend,record.source_id) as lease:
            with self.assertRaisesRegex(ToolError,'InvalidFoundryResponse'):
                await self.service.region_pins(self.backend,record,lease)

    async def test_forged_mapped_position_cannot_escape_independent_coordinate_validation(self):
        record=await self.bound()
        async def corrupt(method,params,result):
            if method=='getMapRegionCandidates':return{**result,'entries':[{**result['entries'][0],'source_x':999}]}
            return result
        self.backend.map_hook=corrupt
        async with self.cache.lease(self.backend,record.source_id) as lease:
            with self.assertRaisesRegex(ToolError,'InvalidFoundryResponse'):
                await self.service.region_pins(self.backend,record,lease)

    async def test_small_configured_frames_are_enforced_on_real_browser_rpc_replies(self):
        self.backend.scene['notes']=[dict(id='n'+str(i).zfill(3),x=1900+i,y=2500,text='Note',levels=[],entryId=None,pageId=None) for i in range(20)]
        self.service=MapContextService(principal=lambda:self.identity,clock=lambda:self.time,frame_bytes=2000)
        observed=[]
        async def measure_frame(method,params,result):
            count=len(json.dumps({'id':'x'*36,'result':result},ensure_ascii=False,separators=(',',':')).encode())
            self.assertLessEqual(count,2000);observed.append(count);return result
        self.backend.map_hook=measure_frame
        record=await self.bound()
        async with self.cache.lease(self.backend,record.source_id) as lease:
            pins=await self.service.region_pins(self.backend,record,lease)
            self.assertEqual(len(pins.pins),20)
        self.assertTrue(observed);self.assertGreater(sum(m=='getMapRegionCandidates' for m,_ in self.backend.map_calls),1)

    async def test_moved_missing_denied_or_renumbered_notes_invalidate_the_pinned_snapshot(self):
        template=copy.deepcopy(self.backend.scene)
        def moved(scene):scene['notes'][0]['x']+=1
        def missing(scene):scene['notes'].clear()
        def denied_note(scene):scene['notes'][0]['allowed']=False
        def renumbered(scene):scene['notes'].append(dict(id='a',x=1900,y=2500,text='Earlier alias',levels=[],entryId=None,pageId=None))
        for mutation in (moved,missing,denied_note,renumbered):
            with self.subTest(mutation=mutation.__name__):
                self.backend.scene=copy.deepcopy(template);record=await self.bound();mutation(self.backend.scene)
                async with self.cache.lease(self.backend,record.source_id) as lease:
                    with self.assertRaisesRegex(ToolError,'MapContextChanged'):
                        await self.service.region_pins(self.backend,record,lease)

    async def test_same_file_in_another_scene_or_socket_change_during_rpc_cannot_retarget_context(self):
        original=await self.bound();self.backend.scene['id']='other'
        other=await self.bound({**self.selector,'scene_uuid':'Scene.other'})
        self.assertEqual(original.resolved.image,other.resolved.image)
        self.assertEqual(original.resolved.reference_digest,other.resolved.reference_digest)
        self.assertNotEqual(original.resolved.map_identity,other.resolved.map_identity)
        async with self.cache.lease(self.backend,original.source_id) as lease:
            with self.assertRaisesRegex(ToolError,'MapContextChanged'):
                await self.service.revalidate(self.backend,original,lease)
        async def replace_socket(method,params,result):
            self.backend.websockets['gm']=object();return result
        self.backend.map_hook=replace_socket
        with self.assertRaisesRegex(ToolError,'SourceContextLost'):
            await self.service.resolve(self.backend,{**self.selector,'scene_uuid':'Scene.other'})


class DisplayGeometryOracleTests(unittest.IsolatedAsyncioTestCase):
    async def test_each_display_orientation_matches_independent_native_crop_pixels(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Image.new('RGBA',(5,3));base.putdata([(x*40+10,y*70+20,(x+y)*20+30,255) for y in range(3) for x in range(5)])
            for orientation in range(1,9):
                with self.subTest(orientation=orientation):
                    path=Path(folder)/('o'+str(orientation)+'.png');exif=Image.Exif();exif[274]=orientation;base.save(path,exif=exif)
                    with Image.open(path) as image:expected=ImageOps.exif_transpose(image).convert('RGBA')
                    metadata=await probe_image(path);self.assertEqual((metadata.width,metadata.height),expected.size)
                    mapping=SceneImageMapping(17,23,expected.width*100,expected.height*100,metadata.width,metadata.height)
                    x,y=expected.width-1,expected.height-1
                    pin=(17+(x+.5)*100,23+(y+.5)*100)
                    mapped=mapping.source_point(*pin);self.assertEqual(mapped,(x+.5,y+.5))
                    crop=Crop(x=int(mapped[0]),y=int(mapped[1]),width=1,height=1)
                    self.assertTrue(mapping.contains(*pin,crop));rendered=await render_region(path,crop)
                    with Image.open(io.BytesIO(rendered.png)) as actual:
                        self.assertEqual(actual.convert('RGBA').getpixel((0,0)),expected.getpixel((x,y)))
