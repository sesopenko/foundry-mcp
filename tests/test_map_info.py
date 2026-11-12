"""Selected map metadata measurement and reader contracts."""
import json
import asyncio
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock,patch
from fastmcp import Client,FastMCP
from foundry_mcp_server import main
from foundry_mcp_server.auth.principal import Principal,current_principal
from foundry_mcp_server.auth.metadata import OAuthToolMetadata
from foundry_mcp_server.mcp_server import tools,map_info
from foundry_mcp_server.mcp_server.server import mcp
from foundry_mcp_server.mcp_server.map_info_models import MapInfoResult
from foundry_mcp_server.ws.connection import RpcError

from foundry_mcp_server.map_info_audit import measure,verify_read,diagnose_schema
from foundry_mcp_server.mcp_server.map_info_models import (
    MapInfoRequest,MapGeometry,MapGrid,LevelMedia,TileLevelMembership)
from pydantic import ValidationError


class MapInfoContractTests(unittest.TestCase):
    def test_explicit_scene_defaults_bounds_and_unimplemented_notes_rejection(self):
        value=MapInfoRequest(scene_uuid='Scene.one')
        self.assertEqual((value.level_id,value.section,value.limit,value.max_bytes),(None,'assets',10,8000))
        for fields in ({'scene_uuid':'Same name'},{'scene_uuid':'Compendium.world.scenes.one'},
                {'scene_uuid':'Scene.one','section':'notes'},{'scene_uuid':'Scene.one','note_keys':['N1']},
                {'scene_uuid':'Scene.one','level_id':'Scene.one.Level.x'},{'scene_uuid':'Scene.one','limit':True},
                {'scene_uuid':'Scene.one','max_bytes':1023},{'scene_uuid':'Scene.one','limit':101}):
            with self.subTest(fields=fields),self.assertRaises(ValidationError):MapInfoRequest.model_validate(fields)
        self.assertEqual(MapInfoRequest(scene_uuid='Scene.one',level_id='floor',max_bytes=48000).level_id,'floor')

    def test_geometry_and_grid_preserve_absence_null_zero_and_screen_fields(self):
        geometry=MapGeometry.model_validate(dict(width=5940,height=7920,padding=.25,shiftX=0,shiftY=0,
            scene_rect=dict(sceneX=1620,sceneY=2160,sceneWidth=5940,sceneHeight=7920)))
        self.assertEqual(geometry.model_dump(exclude_unset=True)['shiftX'],0)
        grid=MapGrid.model_validate(dict(type=1,size=180,distance=5,units='ft',style='solid',thickness=1,
            color='#000000',alpha=.35))
        self.assertEqual(grid.model_dump(exclude_unset=True),dict(type=1,size=180,distance=5,units='ft',
            style='solid',thickness=1,color='#000000',alpha=.35))
        self.assertEqual(MapGrid(type=0,alpha=0,units=None).model_dump(exclude_unset=True),dict(type=0,alpha=0,units=None))
        self.assertEqual(MapGrid().model_dump(exclude_unset=True),{})
        with self.assertRaises(ValidationError):MapGrid(alpha=float('nan'))
        with self.assertRaises(ValidationError):MapGrid(size=True)

    def test_media_followups_and_map_identity_are_consistent(self):
        media=dict(reference='maps/a.webp',reference_status='safe',media_kind='image',support_status='reference_only',
            role='background',map=dict(scene_uuid='Scene.one',level_id='floor',role='background'),
            info_next_call=dict(tool='get_foundry_image_info',arguments=dict(request=dict(src='maps/a.webp'))),
            preview_next_call=dict(tool='get_foundry_image_url',arguments=dict(request=dict(src='maps/a.webp'))))
        self.assertEqual(LevelMedia.model_validate(media).map.level_id,'floor')
        for changes in ({'role':'foreground'},{'info_next_call':None},{'reference_status':'sensitive'},
                {'preview_next_call':dict(tool='get_foundry_image_url',arguments=dict(request=dict(src='maps/other.webp')))}):
            with self.subTest(changes=changes),self.assertRaises(ValidationError):LevelMedia.model_validate({**media,**changes})
        private={**media,'reference':None,'reference_status':'sensitive','media_kind':'unknown',
            'support_status':'map_context_required','info_next_call':None,'preview_next_call':None}
        self.assertIsNone(LevelMedia.model_validate(private).reference)

    def test_declared_tile_membership_does_not_invent_empty_or_null_semantics(self):
        for value in (None,[]):
            self.assertEqual(TileLevelMembership(declared_ids=value,status='not_evaluated').declared_ids,value)
            with self.assertRaises(ValidationError):TileLevelMembership(declared_ids=value,status='explicit')
        self.assertEqual(TileLevelMembership(declared_ids=['floor'],status='explicit').declared_ids,['floor'])
        with self.assertRaises(ValidationError):TileLevelMembership(declared_ids=['floor','floor'],status='explicit')

    def test_browser_cannot_label_sensitive_source_as_safe(self):
        for src in ('https://bucket.example/map.webp?signature=secret','https://user:secret@host/map.png'):
            with self.subTest(src=src),self.assertRaises(ValidationError):
                LevelMedia.model_validate(dict(reference=src,reference_status='safe',media_kind='image',support_status='reference_only',
                    role='background',map=dict(scene_uuid='Scene.one',level_id='floor',role='background'),
                    info_next_call=dict(tool='get_foundry_image_info',arguments=dict(request=dict(src=src))),
                    preview_next_call=dict(tool='get_foundry_image_url',arguments=dict(request=dict(src=src)))))


class MapInfoBaselineTests(unittest.IsolatedAsyncioTestCase):
    async def test_successful_diagnostic_exposes_only_fixed_schema_field_names(self):
        client=AsyncMock()
        client.call_tool.return_value=SimpleNamespace(is_error=False,structured_content={'value':json.dumps(dict(handler_valid=True,
            declared_tile_texture=['src','rotation','secret'],source='never expose'))})
        report=await diagnose_schema(client)
        self.assertTrue(report['passed']);self.assertEqual(report['declared_tile_texture'],['rotation','src'])
        self.assertNotIn('secret',json.dumps(report));self.assertNotIn('never expose',json.dumps(report))

    async def test_diagnostic_code_parses_and_never_reports_source_values(self):
        client=AsyncMock()
        async def call(name,args,**_):
            process=await asyncio.create_subprocess_exec('node','--input-type=module','-e',
                'const input=await new Promise(r=>{let s="";process.stdin.on("data",v=>s+=v);process.stdin.on("end",()=>r(s));});new (Object.getPrototypeOf(async function(){}).constructor)(JSON.parse(input));',
                stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
            await process.communicate(json.dumps(args['code']).encode());self.assertEqual(process.returncode,0,'Diagnostic JavaScript must parse')
            return SimpleNamespace(is_error=False,structured_content={'value':json.dumps(dict(failed=True,type='TypeError',
                locations=[['mapInfo','88','4'],['private-source','1','2']],private='secret'))})
        client.call_tool.side_effect=call
        report=await diagnose_schema(client)
        self.assertFalse(report['passed']);self.assertEqual(report['locations'],[['mapInfo','88','4']])
        self.assertNotIn('private-source',json.dumps(report));self.assertNotIn('secret',json.dumps(report))

    def client(self):
        client=AsyncMock()
        client.list_tools.return_value=[SimpleNamespace(model_dump=lambda **_:dict(name='browse_maps'))]
        data=dict(version='14.369',source_match=True,identities_match=True,dimensions_valid=True,
            active_unchanged=True,scenes=50,levels=51,tiles=80,backgrounds=50,foregrounds=3,empty_levels=1,
            grid_fields=['size','distance'],texture_fields=['scaleX','scaleY'],tile_fields=['levels'],
            private='private source sentinel')
        client.call_tool.return_value=SimpleNamespace(structured_content={'value':json.dumps(data)})
        return client,data

    async def test_counts_fields_and_private_output_exclusion(self):
        client,_=self.client();report=await measure(client)
        self.assertTrue(report['passed']);self.assertEqual(report['calls'],2)
        self.assertEqual((report['scenes'],report['levels'],report['tiles']),(50,51,80))
        self.assertNotIn('sentinel',json.dumps(report))
        client.list_tools.assert_awaited_once();client.call_tool.assert_awaited_once()

    async def test_invalid_runtime_counts_fields_or_errors_never_emit_source(self):
        for change in ({'active_unchanged':False},{'identities_match':False},{'scenes':True},
                {'texture_fields':['private source sentinel']},{'version':'13'}):
            client,data=self.client();data.update(change)
            client.call_tool.return_value.structured_content={'value':json.dumps(data)}
            report=await measure(client)
            self.assertFalse(report['passed']);self.assertEqual(report['calls'],2)
            self.assertNotIn('sentinel',json.dumps(report))
        client,_=self.client();client.list_tools.side_effect=RuntimeError('private source sentinel')
        report=await measure(client)
        self.assertFalse(report['passed']);self.assertEqual(report['calls'],1)
        self.assertNotIn('sentinel',json.dumps(report))


class MapInfoMCPTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.scenes=[dict(id='one',name='Map',folder=None,width=5940,height=7920,padding=.25,shiftX=0,shiftY=0,
            grid=dict(type=1,size=180,distance=5,units='ft',style='solid',thickness=1,color='#000000',alpha=.35),
            initialLevel='floor',levels=[dict(id='floor',name='Floor',sort=0,background=dict(src='maps/a.webp'),foreground=dict(src=None)),
                dict(id='upper',name='Upper',sort=10,background={},foreground={})],
            tiles=[dict(id='art',name='Artwork',sort=0,levels=[],texture=dict(src='maps/t.png'),x=0,y=0,width=10,height=20)])]
        self.manager=SimpleNamespace(websockets={'gm':object()},call=AsyncMock(side_effect=self.node))
        self.identity=Principal('basic','','gm','configured-account')
        self.enterContext(patch.object(tools,'_foundry_manager',self.manager))
        self.enterContext(patch.object(map_info,'current_principal',lambda:self.identity))

    async def node(self,client_id,method,params,timeout):
        self.assertEqual((client_id,method),('gm','getMapInfo'))
        process=await asyncio.create_subprocess_exec('node',str(Path(__file__).parent/'js/fixtures/map-info-rpc.js'),
            stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
        try:output,_=await asyncio.wait_for(process.communicate(json.dumps(dict(params=params,scenes=self.scenes)).encode()),5)
        except BaseException:
            if process.returncode is None:process.kill()
            await process.wait();raise
        self.assertEqual(process.returncode,0)
        reply=json.loads(output)
        if reply.get('error'):raise RpcError(reply['error'])
        return reply['result']

    async def invoke(self,args=None):
        async with Client(mcp) as client:return await client.call_tool('get_map_info',args or {'scene_uuid':'Scene.one'},raise_on_error=False)

    async def test_actual_mcp_dispatch_assets_tiles_and_strict_result(self):
        result=await self.invoke();self.assertFalse(result.is_error)
        data=MapInfoResult.model_validate(result.structured_content)
        self.assertEqual(data.grid.size,180);self.assertEqual(data.geometry.width,5940)
        self.assertEqual(len(data.entries),2)
        self.assertEqual(data.entries[0].background.info_next_call.arguments.request.src,'maps/a.webp')
        self.assertNotIn('source_witness',json.dumps(result.structured_content))
        selected=await self.invoke(dict(scene_uuid='Scene.one',level_id='floor'))
        tiles=await self.invoke(dict(scene_uuid='Scene.one',level_id='floor',section='tiles',expected_revision=selected.structured_content['revision']))
        self.assertFalse(tiles.is_error);self.assertEqual(tiles.structured_content['scope_status'],'partial')
        self.assertEqual(tiles.structured_content['entries'][0]['tile_uuid'],'Scene.one.Tile.art')

    async def test_discovery_flat_typed_defaults_and_oauth(self):
        async with Client(mcp) as client:tool=next(t for t in await client.list_tools() if t.name=='get_map_info')
        self.assertEqual(tool.input_schema['required'],['scene_uuid'])
        self.assertFalse(tool.input_schema['additionalProperties']);self.assertFalse(tool.output_schema['additionalProperties'])
        self.assertEqual(tool.input_schema['properties']['limit']['default'],10)
        self.assertEqual(tool.input_schema['properties']['section']['enum'],['assets','tiles','notes'])
        for word in ('reference_only','not_evaluated','partial','get_foundry_image_info','expected_revision','PF2e'):
            self.assertIn(word,tool.description)
        server=FastMCP('map-info-oauth');server.add_middleware(OAuthToolMetadata());server.add_tool(await mcp.get_tool('get_map_info'))
        async with Client(server) as client:self.assertEqual((await client.list_tools())[0].meta['securitySchemes'][0]['scopes'],['foundry:gm'])
        print('MAP_INFO_DISCOVERY_BYTES',len(json.dumps(tool.model_dump(by_alias=True),ensure_ascii=False,separators=(',',':')).encode()))

    async def test_bad_inputs_and_unverified_authority_never_read(self):
        for args in ({'scene_uuid':'Map'},{'scene_uuid':'Scene.one','section':'notes'},
                {'scene_uuid':'Scene.one','caller_key':'forged'},{'scene_uuid':'Scene.one','limit':True},
                {'scene_uuid':'Scene.one','cursor':'bad'}):self.assertTrue((await self.invoke(args)).is_error)
        self.manager.call.assert_not_awaited()
        with patch.object(map_info,'current_principal',current_principal):self.assertTrue((await self.invoke()).is_error)
        self.manager.call.assert_not_awaited()

    async def test_complete_pagination_revision_and_identity_isolation(self):
        first=await self.invoke(dict(scene_uuid='Scene.one',limit=1));self.assertFalse(first.is_error)
        cursor=first.structured_content['next_cursor']
        second=await self.invoke(dict(scene_uuid='Scene.one',cursor=cursor,max_bytes=48000))
        self.assertTrue(second.structured_content['complete']);self.assertEqual(second.structured_content['entries'][0]['level_id'],'upper')
        self.identity=Principal('basic','','other','configured-account')
        self.assertIn('InvalidCursor',str((await self.invoke(dict(scene_uuid='Scene.one',cursor=cursor))).content))
        self.identity=Principal('basic','','gm','configured-account');self.scenes[0]['grid']['size']=200
        changed=str((await self.invoke(dict(scene_uuid='Scene.one',cursor=cursor))).content)
        self.assertIn('ContentChanged',changed);self.assertIn('restart get_map_info',changed)

    async def test_forged_owner_scope_and_followups_fail_closed(self):
        valid=(await self.invoke()).structured_content;entry=valid['entries'][0]
        corruptions=[{**valid,'source_witness':'private sentinel'},{**valid,'level_id':'other'},
            {**valid,'total':100},{**valid,'entries':[{**entry,'level_uuid':'Scene.other.Level.floor'}]},
            {**valid,'entries':[{**entry,'background':{**entry['background'],'map':dict(scene_uuid='Scene.other',level_id='floor',role='background')}}]},
            {**valid,'entries':[{**entry,'background':{**entry['background'],'info_next_call':None}}]}]
        self.manager.call.side_effect=None
        for broken in corruptions:
            self.manager.call.return_value=broken;result=await self.invoke()
            self.assertTrue(result.is_error);self.assertIn('InvalidFoundryResponse',str(result.content))
            self.assertNotIn('private sentinel',str(result.content))

    async def test_socket_replacement_and_browser_diagnostics_do_not_publish(self):
        real=self.node
        async def changed(*args,**kwargs):
            data=await real(*args,**kwargs);self.manager.websockets['gm']=object();return data
        self.manager.call.side_effect=changed
        self.assertIn('ContextChanged',str((await self.invoke()).content))
        self.manager.call.side_effect=RpcError(dict(code='LevelNotFound',message='private sentinel'))
        result=await self.invoke();self.assertIn('LevelNotFound',str(result.content));self.assertNotIn('sentinel',str(result.content))

    async def test_runtime_verifier_completes_both_streams_and_hides_identity(self):
        valid=(await self.invoke()).structured_content
        class Fake:
            async def list_tools(self,**_):return [SimpleNamespace(model_dump=lambda **_:dict(name='get_map_info'))]
            async def call_tool(self,name,args,**_):
                if name=='execute_javascript':
                    data={'value':json.dumps(dict(active='private-active',scenes=['Scene.one'])) if 'JSON.stringify' in args['code'] else 'private-active'}
                else:
                    data={**valid,'section':args['section']}
                    if args['section']=='tiles':data.update(entries=[],total=0)
                return SimpleNamespace(structured_content=data,content=[],is_error=False,meta=None)
        report=await verify_read(Fake())
        self.assertTrue(report['passed']);self.assertEqual(report['calls'],5)
        self.assertEqual([r['entries'] for r in report['rows']],[2,0])
        self.assertNotIn('private-active',json.dumps(report));self.assertNotIn('Scene.one',json.dumps(report))

    async def test_runtime_verifier_enforces_cap_before_dispatch(self):
        valid=(await self.invoke()).structured_content
        class Endless:
            def __init__(self):self.actual=0
            async def list_tools(self,**_):
                self.actual+=1;return [SimpleNamespace(model_dump=lambda **_:dict(name='get_map_info'))]
            async def call_tool(self,name,args,**_):
                self.actual+=1
                if name=='execute_javascript':data={'value':json.dumps(dict(active=None,scenes=['Scene.one']))}
                else:
                    entry={**valid['entries'][0],'level_id':'floor'+str(self.actual),'level_uuid':'Scene.one.Level.floor'+str(self.actual)}
                    data={**valid,'entries':[entry],'complete':False,'total':999,'next_cursor':'continuation'}
                return SimpleNamespace(structured_content=data,content=[],is_error=False,meta=None)
        fake=Endless();report=await verify_read(fake)
        self.assertFalse(report['passed']);self.assertEqual(report['calls'],30);self.assertEqual(fake.actual,30)
