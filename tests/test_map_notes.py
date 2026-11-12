"""Map-note identities, applicability and bounded legend verification."""
import json
import asyncio
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock,patch
from fastmcp import Client
from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server import map_info
from foundry_mcp_server.mcp_server.server import mcp
from foundry_mcp_server.mcp_server.map_info_models import MapInfoRequest,MapInfoResult
from foundry_mcp_server.mcp_server.map_note_models import MapNoteEntry
from foundry_mcp_server.ws.connection import RpcError
from foundry_mcp_server.mcp_server.selective import size
from pydantic import ValidationError
import test_map_info as map_info_test_helpers

from foundry_mcp_server.map_notes_audit import measure,verify_membership,verify_legend


class NoteBaselineTests(unittest.IsolatedAsyncioTestCase):
    async def test_membership_verifier_enforces_truth_mutation_guards_and_no_private_output(self):
        client=AsyncMock()
        rows=[dict(label=k,included=k!='foreign',included_by_id=k!='foreign',stored_null=k=='null') for k in ('empty','null','explicit','foreign')]
        data=dict(rows=rows,real_empty=25,real_included=25,collection_unchanged=True,active_unchanged=True,private='private sentinel')
        client.call_tool.return_value=SimpleNamespace(is_error=False,structured_content={'value':json.dumps(data)})
        report=await verify_membership(client)
        self.assertTrue(report['passed']);self.assertEqual(report['persisted_fixtures'],0)
        self.assertNotIn('sentinel',json.dumps(report));client.call_tool.assert_awaited_once()
        for changes in ({'active_unchanged':False},{'collection_unchanged':False},{'real_included':0}):
            client.call_tool.return_value.structured_content={'value':json.dumps({**data,**changes})}
            self.assertFalse((await verify_membership(client))['passed'])

    def fixture(self):
        client=AsyncMock()
        client.list_tools.return_value=[SimpleNamespace(model_dump=lambda **_:dict(name='get_map_info'))]
        data=dict(version='14.369',active_unchanged=True,field_label='Levels',field_hint=None,
            counts=dict(scenes=50,notes=3,empty=1,null=1,omitted=0,explicit=1,invalid=0,unlinked=1,
                missing_entry=0,denied_entry=1,linked=1,overrides=0,finite_coordinates=3),private='private sentinel')
        client.call_tool.return_value=SimpleNamespace(structured_content={'value':json.dumps(data)})
        return client,data

    async def test_counts_scope_and_only_allowlisted_aggregates(self):
        client,_=self.fixture();report=await measure(client)
        self.assertTrue(report['passed']);self.assertEqual(report['calls'],2)
        self.assertEqual(report['counts']['notes'],3)
        self.assertNotIn('sentinel',json.dumps(report));client.call_tool.assert_awaited_once()

    async def test_invalid_counts_context_or_errors_never_emit_diagnostics(self):
        for change in ({'version':'13'},{'active_unchanged':False},{'field_hint':False}):
            client,data=self.fixture();data.update(change)
            client.call_tool.return_value.structured_content={'value':json.dumps(data)}
            self.assertFalse((await measure(client))['passed'])
        client,data=self.fixture();data['counts']['empty']=True
        client.call_tool.return_value.structured_content={'value':json.dumps(data)}
        self.assertFalse((await measure(client))['passed'])
        client,_=self.fixture();client.list_tools.side_effect=RuntimeError('private sentinel')
        report=await measure(client);self.assertEqual(report['calls'],1);self.assertFalse(report['passed'])
        self.assertNotIn('sentinel',json.dumps(report))


class NoteContractTests(unittest.TestCase):
    def test_note_aliases_and_denied_label_identity_consistency(self):
        row=dict(kind='note',note_uuid='Scene.one.Note.a',key='N1',x=0,y=1.5,level_id='floor',label=None,
            label_truncated=False,target_status='denied_entry',journal=None,page=None)
        self.assertEqual(MapNoteEntry.model_validate(row).x,0)
        for change in ({'label':'denied label'},{'key':'N0'},{'x':True},{'y':float('inf')},
                {'journal':dict(journal_uuid='JournalEntry.entry',name='Denied',name_truncated=False)}):
            with self.subTest(change=change),self.assertRaises(ValidationError):MapNoteEntry.model_validate({**row,**change})

    def test_note_key_scope_requires_revision_and_distinct_returned_aliases(self):
        args=dict(scene_uuid='Scene.one',level_id='floor',section='notes',expected_revision='a'*64)
        self.assertEqual(MapInfoRequest(**args,note_keys=['N2','N12']).note_keys,['N2','N12'])
        for change in ({'level_id':None},{'section':'assets'},{'expected_revision':None},{'note_keys':[]},
                {'note_keys':['N1','N1']},{'note_keys':['Scene.one.Note.a']}):
            data={**args,'note_keys':['N1'],**change}
            with self.subTest(change=change),self.assertRaises(ValidationError):MapInfoRequest.model_validate(data)


class NoteMCPTests(unittest.IsolatedAsyncioTestCase):
    invoke=map_info_test_helpers.MapInfoMCPTests.invoke

    async def asyncSetUp(self):
        await map_info_test_helpers.MapInfoMCPTests.asyncSetUp(self)
        self.journals=[dict(id='entry',name='Journal',pages=[dict(id='page',name='Page')])]
        self.scenes[0]['notes']=[dict(id='n'+str(i).zfill(2),x=i*10,y=i*20,text='',levels=[],entryId='entry',pageId='page') for i in range(20)]

    async def node(self,client_id,method,params,timeout):
        self.assertEqual((client_id,method),('gm','getMapInfo'))
        process=await asyncio.create_subprocess_exec('node',str(Path(__file__).parent/'js/fixtures/map-info-rpc.js'),
            stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
        try:output,_=await asyncio.wait_for(process.communicate(json.dumps(dict(params=params,scenes=self.scenes,journals=self.journals)).encode()),5)
        except BaseException:
            if process.returncode is None:process.kill()
            await process.wait();raise
        self.assertEqual(process.returncode,0);reply=json.loads(output)
        if reply.get('error'):raise RpcError(reply['error'])
        return reply['result']

    async def notes(self,**kwargs):return await self.invoke(dict(scene_uuid='Scene.one',level_id='floor',section='notes',**kwargs))

    async def test_actual_legend_pagination_alias_filter_and_selected_asset_revision(self):
        first=await self.notes(limit=2);self.assertFalse(first.is_error)
        data=first.structured_content;self.assertEqual([n['key'] for n in data['entries']],['N1','N2'])
        revision=data['revision'];cursor=data['next_cursor']
        rest=await self.notes(cursor=cursor,limit=100,max_bytes=48000,expected_revision=revision)
        self.assertFalse(rest.is_error);self.assertTrue(rest.structured_content['complete'])
        self.assertEqual([n['key'] for n in rest.structured_content['entries']],['N'+str(i) for i in range(3,21)])
        filtered=await self.notes(note_keys=['N12','N2'],expected_revision=revision)
        self.assertFalse(filtered.is_error)
        self.assertEqual([n['key'] for n in filtered.structured_content['entries']],['N2','N12'])
        self.assertEqual(filtered.structured_content['revision'],revision)
        assets=await self.invoke(dict(scene_uuid='Scene.one',level_id='floor',expected_revision=revision))
        self.assertFalse(assets.is_error);self.assertEqual(assets.structured_content['revision'],revision)

    async def test_invalid_note_context_or_keys_fail_before_reads(self):
        for args in (dict(scene_uuid='Scene.one',section='notes'),dict(scene_uuid='Scene.one',note_keys=['N1']),
                dict(scene_uuid='Scene.one',section='notes',level_id='floor',note_keys=['N1']),
                dict(scene_uuid='Scene.one',section='notes',level_id='floor',note_keys=['N1','N1'],expected_revision='a'*64)):
            self.assertTrue((await self.invoke(args)).is_error)
        self.manager.call.assert_not_awaited()

    async def test_level_or_note_change_invalidates_old_alias_context(self):
        first=await self.notes();revision=first.structured_content['revision']
        wrong=await self.invoke(dict(scene_uuid='Scene.one',level_id='upper',section='notes',note_keys=['N1'],expected_revision=revision))
        self.assertIn('ContentChanged',str(wrong.content))
        unknown=await self.notes(note_keys=['N99'],expected_revision=revision)
        self.assertIn('InvalidNoteKeys',str(unknown.content))
        self.scenes[0]['notes'][0]['text']='Changed'
        changed=await self.notes(expected_revision=revision)
        self.assertIn('ContentChanged',str(changed.content))

    async def test_denied_target_label_is_not_evaluated_and_partial_scope_is_explicit(self):
        self.journals[0]['allowed']=False
        result=await self.notes();self.assertFalse(result.is_error)
        data=result.structured_content;self.assertEqual(data['scope_status'],'partial')
        self.assertTrue(all(n['label'] is None and n['journal'] is None and n['page'] is None for n in data['entries']))
        self.assertNotIn('Journal',json.dumps(data))

    async def test_candidates_are_bounded_by_actual_configured_frame_with_revisions(self):
        revision=(await self.notes()).structured_content['revision']
        with patch.object(map_info,'settings',SimpleNamespace(max_response_bytes=3000)):
            candidate=await map_info.read_map_note_candidates('Scene.one','floor',revision)
            self.assertLessEqual(size({'id':'x'*36,'result':candidate}),3000)
            self.assertTrue(0<len(candidate['entries'])<20);self.assertIsNotNone(candidate['next_cursor'])
            self.assertEqual(candidate['revision'],revision)
        self.manager.call.reset_mock()
        with patch.object(map_info,'settings',SimpleNamespace(max_response_bytes=1024)):
            with self.assertRaisesRegex(ToolError,'ResponseTooLarge'):
                await map_info.read_map_note_candidates('Scene.one','floor',revision)
        self.manager.call.assert_not_awaited()
        with self.assertRaisesRegex(ToolError,'expected_revision'):
            await map_info.read_map_note_candidates('Scene.one','floor',None)
        self.manager.call.assert_not_awaited()

    async def test_actual_discovery_publishes_notes_constraints_without_private_candidate_tool(self):
        async with Client(mcp) as client:catalog=await client.list_tools()
        tool=next(t for t in catalog if t.name=='get_map_info')
        self.assertIn('notes',tool.input_schema['properties']['section']['enum'])
        self.assertIn('note_keys',tool.input_schema['properties'])
        for term in ('includedInLevel','denied_page','expected_revision','note_keys','N1/N2'):
            self.assertIn(term,tool.description)
        self.assertFalse(any('candidate' in t.name for t in catalog))

    async def test_forged_alias_ordinal_is_rejected_even_on_a_single_entry_page(self):
        result=await self.notes(limit=1);raw=result.structured_content
        forged={**raw,'entries':[{**raw['entries'][0],'key':'N999'}]}
        self.manager.call.side_effect=None;self.manager.call.return_value=forged
        invalid=await self.notes(limit=1)
        self.assertTrue(invalid.is_error)
        self.assertIn('InvalidFoundryResponse',str(invalid.content))

    async def test_legend_verifier_completes_actual_reader_without_printing_identities(self):
        owner=self
        class Runtime:
            def __init__(self):self.calls=0
            async def list_tools(self,**_):
                self.calls+=1
                async with Client(mcp) as client:return await client.list_tools()
            async def call_tool(self,name,args,**_):
                self.calls+=1
                if name=='execute_javascript':
                    value=json.dumps(dict(scene_uuid='Scene.one',level_id='floor',active='private-active')) if 'JSON.stringify' in args['code'] else 'private-active'
                    return SimpleNamespace(is_error=False,structured_content={'value':value})
                return await owner.invoke(args)
        runtime=Runtime();report=await verify_legend(runtime)
        self.assertTrue(report['passed']);self.assertEqual(report['notes'],20)
        self.assertEqual(report['calls'],runtime.calls);self.assertLessEqual(report['calls'],30)
        self.assertEqual(report['filter_keys'],2)
        self.assertNotIn('private-active',json.dumps(report));self.assertNotIn('JournalEntry.',json.dumps(report))
