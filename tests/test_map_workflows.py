"""Complete returned-call MCP workflow with independent map/file/pin identities."""
import io
import importlib.util
import json
import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch

from PIL import Image
from foundry_mcp_server.mcp_server import maps
import test_map_image_tools as image_tools
from map_workflow_harness import MapWorkflowBackend,large_annotations
from foundry_mcp_server import map_workflow_acceptance as acceptance
from foundry_mcp_server.image_preview_live_support import Budget,cleanup_map_review
from types import SimpleNamespace

REVIEW_SPEC=importlib.util.spec_from_file_location('map_review_check',Path(__file__).resolve().parents[1]/'scripts/map-preview-review-check.py')
review=importlib.util.module_from_spec(REVIEW_SPEC);REVIEW_SPEC.loader.exec_module(review)


class MapWorkflowTests(image_tools.MapToolFixture,unittest.IsolatedAsyncioTestCase):
    backend_factory=MapWorkflowBackend

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.enterContext(patch.object(maps,'current_principal',lambda:self.identity))

    async def test_folder_next_calls_to_all_levels_grid_annotated_crop_tiles_and_complete_legend(self):
        args={}
        for expected in ('Adventure','Chapter','Map'):
            page=await self.call('browse_maps',args);self.assertFalse(page.is_error,str(page.content))
            entry=next(e for e in page.structured_content['entries'] if e['name']==expected)
            args=entry['next_call']['arguments']
        config=await self.call('get_map_info',{**args,'limit':1})
        self.assertFalse(config.is_error,str(config.content));first=config.structured_content
        self.assertEqual(first['grid'],dict(type=1,size=180,distance=5,units='ft',style='solid',thickness=1,color='#000000',alpha=.35))
        self.assertEqual([a['name'] for a in first['scene']['ancestry']],['Adventure','Chapter'])
        all_levels=list(first['entries']);next_args={**args,'limit':1}
        while not config.structured_content['complete']:
            next_args['cursor']=config.structured_content['next_cursor'];config=await self.call('get_map_info',next_args)
            self.assertFalse(config.is_error,str(config.content));all_levels+=config.structured_content['entries']
        self.assertEqual([e['level_id'] for e in all_levels],['floor','empty','video'])
        self.assertEqual(all_levels[1]['background']['support_status'],'missing')
        self.assertEqual(all_levels[2]['background']['support_status'],'unsupported_video')
        follow=all_levels[0]['background']['info_next_call'];info=await self.info(follow['arguments']['request'])
        self.assertEqual((info.width,info.height),(500,500));self.assertNotEqual(first['geometry']['width'],info.width)
        value=await self.url(dict(source_id=info.source_id,map_notes=True,crop=dict(x=200,y=200,width=150,height=150)))
        decoded=Image.open(io.BytesIO(await self.fetch(value))).convert('RGB')
        self.assertEqual(decoded.getpixel((50,50)),(255,255,255))
        self.assertEqual(value.map_notes.keys,['N1','N2'])
        legend_args=value.map_notes.legend_next_call.arguments.model_dump();seen=[];pages=0
        while True:
            page=await self.call('get_map_info',{**legend_args,'limit':1});self.assertFalse(page.is_error,str(page.content))
            seen+=page.structured_content['entries'];pages+=1
            if page.structured_content['complete']:break
            legend_args['cursor']=page.structured_content['next_cursor']
        self.assertEqual(pages,2);self.assertEqual([e['key'] for e in seen],['N1','N2'])
        self.assertEqual({e['journal']['journal_uuid'] for e in seen},{'JournalEntry.journal'})
        self.assertEqual({e['page']['page_uuid'] for e in seen},{'JournalEntry.journal.JournalEntryPage.page'})
        self.assertEqual(len({e['note_uuid'] for e in seen}),2)
        tiles=await self.call('get_map_info',dict(scene_uuid='Scene.scene',level_id='floor',section='tiles'))
        self.assertFalse(tiles.is_error,str(tiles.content));self.assertEqual(tiles.structured_content['entries'][0]['placement']['rotation'],15)
        self.assertEqual(self.transfers(),1)
        self.assertTrue(all(row['json_bytes']<=8000 for row in self.measurements))
        print('COMPLETE_MAP_WORKFLOW',json.dumps(dict(calls=len(self.measurements),transfers=self.transfers(),legend_pages=pages,rows=self.measurements),separators=(',',':')))

    async def test_shared_source_duplicate_folder_and_map_names_keep_exact_scene_owners(self):
        parent=await self.call('browse_maps',dict(folder_uuid='Folder.root'))
        self.assertFalse(parent.is_error,str(parent.content))
        self.assertEqual([e['name'] for e in parent.structured_content['entries']],['Chapter','Chapter'])
        self.assertEqual(len({e['folder_uuid'] for e in parent.structured_content['entries']}),2)
        identities=[]
        for scene in ('Scene.scene','Scene.copy'):
            value=await self.url(dict(map=dict(scene_uuid=scene,level_id='floor',role='background'),map_notes=True))
            identities.append(value.map_notes.map.scene_uuid)
            legend=await self.call('get_map_info',value.map_notes.legend_next_call.arguments.model_dump())
            self.assertFalse(legend.is_error,str(legend.content));self.assertTrue(legend.structured_content['entries'][0]['note_uuid'].startswith(scene+'.'))
        self.assertEqual(identities,['Scene.scene','Scene.copy'])

    async def test_stale_legend_and_mapping_change_reject_joins_without_breaking_plain_pixels(self):
        info=await self.info();value=await self.url(dict(source_id=info.source_id,map_notes=True))
        args=value.map_notes.legend_next_call.arguments.model_dump();first=await self.call('get_map_info',{**args,'limit':1})
        self.assertFalse(first.is_error);self.assertFalse(first.structured_content['complete'])
        self.browser.primary['notes'][0]['text']='Metadata changed'
        stale=await self.call('get_map_info',{**args,'limit':1,'cursor':first.structured_content['next_cursor']})
        self.assertTrue(stale.is_error);self.assertIn('ContentChanged',str(stale.content))
        stale=await self.call('get_foundry_image_url',dict(source_id=info.source_id,map_notes=True))
        self.assertTrue(stale.is_error);self.assertIn('MapContextChanged',str(stale.content))
        await self.url(dict(source_id=info.source_id))
        self.browser.primary['levels'][0]['textures']={'unsupported_placement':True}
        current=await self.info()
        unsupported=await self.call('get_foundry_image_url',dict(source_id=current.source_id,map_notes=True))
        self.assertTrue(unsupported.is_error);self.assertIn('UnsupportedMapMapping',str(unsupported.content))
        await self.url(dict(source_id=current.source_id))

    async def test_small_independent_annotated_measurement_and_resource_aggregation(self):
        report=await large_annotations(600,600)
        self.assertTrue(report['passed']);self.assertEqual(report['resources']['operations'],2)
        self.assertEqual(report['renders'][1]['notes']['keys'],['N2'])

    async def test_one_pixel_map_crop_reports_omission_without_shrinking_keys(self):
        info=await self.info()
        tiny=await self.url(dict(source_id=info.source_id,map_notes=True,crop=dict(x=250,y=250,width=1,height=1)))
        self.assertEqual((tiny.width,tiny.height),(1,1))
        self.assertEqual((tiny.map_notes.total_in_region,tiny.map_notes.rendered_count,tiny.map_notes.omitted_count),(1,0,1))
        self.assertEqual(tiny.map_notes.omission_reasons,{'tiny_image':1})
        self.assertFalse(tiny.map_notes.complete);self.assertIsNone(tiny.map_notes.legend_next_call)
        detail=await self.url(dict(source_id=info.source_id,map_notes=True,crop=dict(x=200,y=200,width=150,height=150)))
        self.assertIn('N1',detail.map_notes.keys);self.assertEqual(self.transfers(),1)


class NativeMapHarnessTests(unittest.IsolatedAsyncioTestCase):
    async def test_measured_native_glyph_area_and_small_canvas_rejection(self):
        value=await review.measure(['N1'],500,500)
        self.assertEqual(value['label_box_pixels'],308);self.assertEqual(value['max_ink_height'],14)
        self.assertEqual(value['coverage_percent'],.1232)
        with self.assertRaises(ValueError):await review.measure(['N1'],20,20)

    async def test_native_harness_follows_returned_calls_and_exact_revision_legend(self):
        selector=dict(scene_uuid='Scene.fixture',level_id='floor',role='background')
        note=dict(key='N1',note_uuid='Scene.fixture.Note.note',x=1900,y=2500,journal=dict(journal_uuid='JournalEntry.fixture'),page=dict(page_uuid='JournalEntry.fixture.JournalEntryPage.page'))
        calls=[]
        class Client:
            async def list_tools(self,**_):return []
            async def call_tool(self,name,args,**_):
                calls.append((name,args))
                common=dict(revision='a'*64,complete=True,scope_status='complete',next_cursor=None)
                if name=='execute_javascript':
                    code=args['code']
                    if code==acceptance.SELECT:value=dict(scene_uuid='Scene.fixture',level_id='floor',active=None,grid={},count=1,pin=dict(key='N1',x=100,y=100),folder='folder')
                    elif 'const rows=' in code:value=dict(matched=True,count=1)
                    else:value=dict(active=None)
                    value=dict(value=json.dumps(value))
                elif name=='browse_maps':
                    entry=(dict(kind='folder',folder_uuid='Folder.folder',parent_uuid=None,name='Chapter',next_call=dict(tool='browse_maps',arguments=dict(folder_uuid='Folder.folder')))
                        if args.get('folder_uuid') is None else dict(kind='map',scene_uuid='Scene.fixture',parent_uuid='Folder.folder',name='Map',next_call=dict(tool='get_map_info',arguments=dict(scene_uuid='Scene.fixture'))))
                    value={**common,'entries':[entry]}
                elif name=='get_map_info':
                    section=args.get('section','assets')
                    if section=='assets':entries=[dict(level_id='floor',background=dict(info_next_call=dict(tool='get_foundry_image_info',arguments=dict(request=dict(map=selector)))))]
                    elif section=='tiles':entries=[]
                    else:
                        self_outer.assertEqual(args['expected_revision'],'a'*64);self_outer.assertEqual(args['note_keys'],['N1']);entries=[note]
                    value={**common,'entries':entries,'grid':{},'level_id':args.get('level_id')}
                elif name=='get_foundry_image_info':value=dict(source_id='private-source',width=6800,height=9000)
                elif name=='get_foundry_image_url':value=dict(source_id='private-source',width=800,height=600,size_bytes=100,map_notes=dict(map=selector,revision='a'*64,keys=['N1'],rendered_count=1,total_in_region=1,omitted_count=0,complete=True,scope_status='complete',omission_reasons={},legend_next_call=dict(tool='get_map_info',arguments=dict(scene_uuid='Scene.fixture',level_id='floor',section='notes',expected_revision='a'*64,note_keys=['N1']))))
                else:raise AssertionError('Unexpected call')
                return SimpleNamespace(is_error=False,structured_content=value,content=[],meta=None)
        self_outer=self;read=[]
        report=await acceptance.verify_map(Client(),lambda value,label,pin:read.append((label,pin)) or dict(passed=True))
        self.assertTrue(report['passed'],report);self.assertEqual(report['calls'],len(calls)+1)
        self.assertEqual(report['legend_rows'],2);self.assertEqual(report['legend_pages'],2)
        self.assertEqual(read,[('overview',None),('detail',(100,100))])
        self.assertNotIn('private-source',json.dumps(report));self.assertEqual(report['persisted_fixtures'],0)

    async def test_failed_native_discovery_counts_call_and_redacts_private_error(self):
        class Client:
            async def list_tools(self,**_):raise RuntimeError('private source sentinel')
        report=await acceptance.verify_map(Client(),lambda *_:None)
        self.assertFalse(report['passed']);self.assertEqual(report['calls'],1)
        self.assertNotIn('sentinel',json.dumps(report))

    async def test_native_budget_prevents_any_tool_call_after_expiry(self):
        now=[0];budget=Budget(seconds=1,clock=lambda:now[0])
        class Client:
            async def list_tools(self,**_):now[0]=1;return []
            async def call_tool(self,*_,**__):raise AssertionError('Dispatched after deadline')
        report=await acceptance.verify_map(Client(),lambda *_:None,budget=budget)
        self.assertFalse(report['passed']);self.assertEqual(report['calls'],1)

    def test_review_cleanup_rejects_extra_files_and_preserves_neighbors(self):
        with tempfile.TemporaryDirectory() as parent:
            directory=Path(parent)/'review';directory.mkdir();(directory/'.owner').write_text('a'*32)
            (directory/'overview.png').write_bytes(b'pixels');(directory/'extra').write_bytes(b'preserve')
            with self.assertRaises(ValueError):cleanup_map_review(directory)
            self.assertTrue((directory/'extra').exists());(directory/'extra').unlink()
            self.assertEqual(cleanup_map_review(directory),dict(cleanup_complete=True,files=1))
