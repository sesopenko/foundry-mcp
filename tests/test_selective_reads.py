"""Typed MCP discovery, validation and actual browser proof interoperability."""
import copy
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import AsyncMock

from fastmcp import Client
from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from foundry_mcp_server.mcp_server.server import mcp
from foundry_mcp_server.mcp_server import selective as S, selective_models as M


SCRIPT = r"""
import {readActorSelected,readItemSelected} from './foundry-module/scripts/actors.js';
const docs=new Map();
function make(uuid,type,system={}) {
 const documentName=uuid.includes('.Item.')?'Item':'Actor';
 const source={name:'Example',type,system,flags:{private:'SECRET_SENTINEL'}};
 const doc={uuid,id:uuid.split('.').at(-1),name:source.name,type,documentName,parent:null,folder:null,compendium:null,items:new Map(),testUserPermission:()=>true,toObject:()=>structuredClone(source)};
 docs.set(uuid,doc);return doc;
}
const actor=make('Actor.a','npc',{attributes:{ac:{value:21,details:'against traps'}},perception:{senses:[{type:'darkvision'}]}});
const item=make('Actor.a.Item.i','action',{description:{value:'<p>Exact 😀</p>',gm:'SECRET_SENTINEL'},actionType:{value:'reaction'},actions:{value:null}});
item.parent=actor;actor.items.set('i',item);
globalThis.game={version:'14.369',system:{id:'pf2e',version:'8.6.1'},ready:true,user:{isGM:true},actors:new Map([['a',actor]]),items:new Map()};
globalThis.foundry={utils:{fromUuid:async uuid=>docs.get(uuid)}};
const cases=[['actor',{},[]],['actor',{},['statistics.armor_class']],['actor',{evidence:true},['statistics.armor_class']],['item',{},['description']],['item',{evidence:true},['source.activation']]];
const results=[];
for(const [kind,extra,details] of cases){const args={...(kind==='actor'?{actor_uuid:actor.uuid}:{item_uuid:item.uuid}),select:{details,...extra},max_bytes:48000};results.push({kind,args,packet:await (kind==='actor'?readActorSelected:readItemSelected)(args)});}
console.log(JSON.stringify(results));
"""


class SelectiveTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        result = subprocess.run(['node','--input-type=module'], input=SCRIPT, text=True, capture_output=True, cwd=Path(__file__).resolve().parents[1], check=True)
        cls.cases = json.loads(result.stdout)

    async def asyncSetUp(self):
        self.manager = AsyncMock()
        register_foundry_manager(self.manager)

    async def test_actual_packets_and_typed_output(self):
        async with Client(mcp) as client:
            for case in self.cases:
                with self.subTest(kind=case['kind'], args=case['args']):
                    self.manager.call.return_value = case['packet']
                    result = await client.call_tool('read_'+case['kind'],case['args'])
                    self.assertEqual(result.structured_content,case['packet']['result'])
                    self.assertNotIn('SECRET_SENTINEL',json.dumps(result.structured_content))

    async def test_invalid_inputs_do_not_call_bridge(self):
        async with Client(mcp) as client:
            for args in [{}, {'actor_uuid':'Actor.a','token_uuid':'Scene.s.Token.t'},
                         {'actor_uuid':'Actor.a','select':{'details':['private.path']}},
                         {'actor_uuid':'Actor.a','select':{'details':['skills','skills']}},
                         {'actor_uuid':'Actor.a','select':{},'sections':['source']},
                         {'actor_uuid':'Actor.a','limit':True},
                         {'actor_uuid':'Actor.a','max_bytes':7999},
                         {'actor_uuid':'Actor.a','select':{'unknown':True}}]:
                with self.subTest(args=args):
                    result=await client.call_tool('read_actor',args,raise_on_error=False)
                    self.assertTrue(result.is_error)
            self.manager.call.assert_not_awaited()

    async def test_forged_compact_values_and_context_rejected(self):
        case=self.cases[1]
        for change in ('value','uuid','group'):
            packet=copy.deepcopy(case['packet'])
            if change=='value': packet['result']['entries'][0]['values'][0]['value']=999
            elif change=='uuid': packet['proof']['identity']['uuid']='Actor.other'
            else: packet['group_lengths']=[1]
            self.manager.call.return_value=packet
            with self.subTest(change=change),self.assertRaises(ToolError):
                await S.read(M.ActorRequest.model_validate(case['args']))

    async def test_catalog_defaults_and_only_nine_output_schemas(self):
        async with Client(mcp) as client:
            tools={t.name:t for t in await client.list_tools()}
        names=('read_actor','read_item','list_actor_items','get_actor_types','list_actor_compendiums','get_journal_contents','search_journals','read_journal_page','search_pdf_documents')
        for name in names:
            tool=tools[name]
            self.assertIsNotNone(tool.outputSchema)
            self.assertFalse(tool.inputSchema['additionalProperties'])
            self.assertEqual(tool.inputSchema['properties']['max_bytes']['default'],8000)
            self.assertTrue(tool.annotations.readOnlyHint)
        self.assertEqual(tools['read_actor'].inputSchema['properties']['limit']['default'],10)
        self.assertEqual(tools['read_journal_page'].inputSchema['properties']['max_chars']['default'],2000)
        self.assertLess(S.size([tools[n].model_dump(mode='json') for n in names]),80333)

    async def test_response_validation_is_real_not_just_schema_advertising(self):
        tool=await mcp.get_tool('read_actor')
        bad=copy.deepcopy(self.cases[0]['packet']['result']);bad['unexpected']='leak'
        handler=AsyncMock(return_value=bad)
        clone=tool.model_copy(update={'handler':handler})
        with self.assertRaises(ToolError):await clone.run({'actor_uuid':'Actor.a'})

    async def test_valid_but_unrequested_subsection_is_rejected(self):
        self.manager.call.return_value=self.cases[1]['packet']
        with self.assertRaises(ToolError):
            await S.read(M.ActorRequest(actor_uuid='Actor.a',select=M.ActorSelect(details=['statistics.hit_points'])))

    async def test_wrong_owner_in_compact_item_list_is_rejected(self):
        from test_actor_tools import items
        result=items();result['contract_version']=2
        result['nodes']=[{'kind':'item','identity':{'uuid':'Actor.other.Item.i','name':'Item','name_truncated':False,'type':'action'}}]
        self.manager.call.return_value=result
        with self.assertRaises(ToolError):await S.metadata(M.ItemsRequest(actor_uuid='Actor.a'))

    def test_response_arrays_preserve_repeated_source_values(self):
        value=M.Value(concept='source_choices',value=['same','same'],basis='source',present=True)
        self.assertEqual(value.value,['same','same'])
