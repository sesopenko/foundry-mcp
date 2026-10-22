"""Actor/Item adapter trust-boundary and actual MCP discovery tests."""
import asyncio
import copy
import json
import subprocess
from pathlib import Path
import unittest
from unittest.mock import AsyncMock

from fastmcp import Client
from fastmcp.exceptions import ToolError

from foundry_mcp_server.mcp_server.actors import get_actor_types, read_actor, read_item, list_actor_items
from foundry_mcp_server.mcp_server.server import mcp
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from foundry_mcp_server.ws.connection import RpcError

RUNTIME = dict(core_version='14.369', system_id='pf2e', system_version='8.6.1')


def identity(kind='Actor'):
    return dict(document_name=kind, id='a', uuid='Actor.a' if kind == 'Actor' else 'Actor.a.Item.i', name='Example', name_truncated=False, type='npc' if kind == 'Actor' else 'action', source_kind='world', folder=None, pack=None, actor=None if kind == 'Actor' else dict(uuid='Actor.a', name='Example'), instance=None)


def reader(kind='Actor', sections=None):
    sections = sections or ['identity', 'source']
    return dict(contract_version=1, runtime=RUNTIME.copy(), identity=identity(kind), revision='revision', sections=[dict(name=s, status='complete', reasons=[]) for s in sections], records=[], pagination=dict(complete=True, next_cursor=None, returned=0), limitations=[])


def registry():
    verification = dict(deterministic=dict(status='passed', evidence=['tests/test_actor_tools.py']), live=dict(status='not_run', evidence=[]))
    row = dict(type='npc', name='NPC', allowed=True, in_scope=True, source_supported=True, mapped_supported=False, effective_supported=False, limitations=['Common metadata only.'], verification=verification)
    section = {k: copy.deepcopy(v) for k, v in row.items() if k != 'type'}
    section['name'] = 'source'
    return dict(contract_version=1, runtime=RUNTIME.copy(), availability=dict(supported=True, reason='Common metadata available.'), actor_types=[row], item_types=[], actor_sections=[section], item_sections=[], limits=dict(default_limit=50,max_records=100,min_bytes=8000,max_bytes=48000,max_text_units=6000,max_cursor_characters=4096,max_selector_characters=512), limitations=[])


def items():
    return dict(contract_version=1,runtime=RUNTIME.copy(),revision='revision',nodes=[dict(kind='item',identity=identity('Item'),parent_uuid='Actor.a',next_call=dict(tool='read_item',arguments=dict(item_uuid='Actor.a.Item.i')),relationships=[])],scopes=[dict(id='Actor.a',status='searched',reason=None)],pagination=dict(complete=True,next_cursor=None,returned=1),unsupported_count=0,limitations=[])


def record():
    raw = dict(document_uuid='Actor.a', path='/name', present=True, value='Example', basis='source')
    return dict(key='source.name',section='source',kind='field',raw=[raw],mapped=dict(concept='name',value='Example',unit=None),provenance=dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='core.name.v1',limitations=[]))


class ActorToolTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager = AsyncMock()
        register_foundry_manager(self.manager)

    async def test_exact_rpc_interfaces_and_defaults(self):
        for tool, args, method, response, params in [
            (get_actor_types,{},'getActorTypes',registry(),{}),
            (read_actor,{'actor_uuid':'Actor.a'},'readActor',reader(),dict(actor_uuid='Actor.a',token_uuid=None,sections=['identity','source'],limit=50,max_bytes=48000,cursor=None)),
            (read_item,{'item_uuid':'Actor.a.Item.i'},'readItem',reader('Item'),dict(item_uuid='Actor.a.Item.i',token_uuid=None,sections=['identity','source'],limit=50,max_bytes=48000,cursor=None)),
            (list_actor_items,{'token_uuid':'Scene.s.Token.t'},'listActorItems',items(),dict(actor_uuid=None,token_uuid='Scene.s.Token.t',types=None,query=None,limit=50,max_bytes=48000,cursor=None)),
        ]:
            with self.subTest(method=method):
                self.manager.reset_mock()
                self.manager.call.return_value = response
                self.assertEqual(await tool.fn(**args),response)
                self.manager.call.assert_awaited_once_with('gm',method,params,timeout=15.0)

    async def test_invalid_inputs_never_reach_browser(self):
        cases = [{},dict(actor_uuid='Actor.a',token_uuid='Scene.s.Token.t'),dict(actor_uuid=''),dict(actor_uuid='x'*513),dict(actor_uuid='Actor.a',limit=True),dict(actor_uuid='Actor.a',limit=101),dict(actor_uuid='Actor.a',max_bytes=7999),dict(actor_uuid='Actor.a',cursor='é'),dict(actor_uuid='Actor.a',sections=[]),dict(actor_uuid='Actor.a',sections=['source','source']),dict(actor_uuid='Actor.a',sections=['unknown'])]
        for args in cases:
            with self.subTest(args=args),self.assertRaises(ToolError):
                await read_actor.fn(**args)
        for args in [dict(types=[]),dict(types=['action','action']),dict(types=['campaignFeature']),dict(query='  ')]:
            with self.subTest(args=args),self.assertRaises(ToolError):
                await list_actor_items.fn(actor_uuid='Actor.a',**args)
        self.manager.call.assert_not_awaited()

    async def test_browser_codes_and_transport_errors_are_structured(self):
        for error, code in [(RpcError(dict(code='ContentChanged',message='Changed',recovery='Restart without cursor.')),'ContentChanged'),(RpcError(dict(type='PermissionDenied',message='Denied')),'PermissionDenied'),(asyncio.TimeoutError(),'ReadFailed'),(ConnectionError(),'BridgeUnavailable'),(RuntimeError(),'BridgeUnavailable')]:
            self.manager.call.side_effect=error
            with self.assertRaises(ToolError) as caught:
                await read_actor.fn(actor_uuid='Actor.a')
            value=json.loads(str(caught.exception))
            self.assertEqual(value['code'],code)
            self.assertEqual(set(value),{'code','message','recovery'})

    async def test_valid_raw_mapped_provenance_and_text_fragments(self):
        response=reader(); response['records']=[record()];response['pagination']['returned']=1
        self.manager.call.return_value=response
        self.assertEqual(await read_actor.fn(actor_uuid='Actor.a'),response)
        for forbidden in ['/system/description/gm', '/flags/private', '/_stats']:
            response['records'][0]['raw'][0]['path'] = forbidden
            with self.subTest(path=forbidden), self.assertRaises(ToolError):
                await read_actor.fn(actor_uuid='Actor.a')
        response['records'] = [record()]
        text=record();text['kind']='text';text['raw'][0].update(path='/system/description/value',value='😀');text['text']=dict(path='/system/description/value',start=0,end=2,total=2,complete=True)
        response['records']=[text]
        self.assertEqual(await read_actor.fn(actor_uuid='Actor.a'),response)
        text['text']['end']=1
        with self.assertRaises(ToolError):await read_actor.fn(actor_uuid='Actor.a')

    async def test_malformed_reader_envelopes_rejected(self):
        good=reader()
        bad=[None,[],{},dict(good,contract_version=True),dict(good,runtime=dict(RUNTIME,system_version=861)),dict(good,identity=dict(identity(),private='secret')),dict(good,revision=None),dict(good,pagination=dict(complete=True,next_cursor='x',returned=0)),dict(good,pagination=dict(complete=True,next_cursor=None,returned=True)),dict(good,sections=[dict(name='source',status='complete',reasons=[])]),dict(good,records=[{'raw':'secret'}]),dict(good,limitations=['😀'*12000]),dict(good,extra='unexpected')]
        for response in bad:
            with self.subTest(response_type=type(response)):
                self.manager.call.return_value=response
                with self.assertRaises(ToolError):await read_actor.fn(actor_uuid='Actor.a')
        self.manager.call.return_value=dict(good,limitations=['é'*4000])
        with self.assertRaises(ToolError):await read_actor.fn(actor_uuid='Actor.a',max_bytes=8000)

    async def test_count_limit_and_no_nan_or_non_json_values(self):
        for response in [dict(reader(),records=[dict(record(),key='a'),dict(record(),key='b')],pagination=dict(complete=True,next_cursor=None,returned=2)),dict(reader(),limitations=[float('nan')]),dict(reader(),limitations=[object()])]:
            self.manager.call.return_value=response
            with self.assertRaises(ToolError):await read_actor.fn(actor_uuid='Actor.a',limit=1)

    async def test_list_and_registry_shapes_rejected(self):
        for tool,args,response in [(get_actor_types,{},dict(registry(),availability={'supported':'yes','reason':'bad'})),(get_actor_types,{},dict(registry(),actor_types=[{}])),(list_actor_items,dict(actor_uuid='Actor.a'),dict(items(),unsupported_count=True)),(list_actor_items,dict(actor_uuid='Actor.a'),dict(items(),scopes=[{'id':'Actor.a','status':'unknown','reason':None}])),(list_actor_items,dict(actor_uuid='Actor.a'),dict(items(),nodes=[dict(kind='item',identity=identity('Item'),next_call={'tool':'read_item','arguments':{'item_uuid':'wrong'}})]))]:
            self.manager.call.return_value=response
            with self.assertRaises(ToolError):await tool.fn(**args)

    async def test_actual_browser_dtos_match_python_boundary(self):
        script = r"""
import {getActorTypes,readActor,readItem,listActorItems} from './foundry-module/scripts/actors.js';
const docs=new Map();
function make(uuid,documentName,type,system={}) {
 const source={name:'Example 😀',type,system,flags:{private:'private_source_sentinel_783f'}};
 const doc={uuid,id:uuid.split('.').at(-1),name:source.name,type,documentName,parent:null,folder:null,compendium:null,items:new Map(),testUserPermission:()=>true,toObject:()=>structuredClone(source)};
 docs.set(uuid,doc);return doc;
}
const actor=make('Actor.a','Actor','npc');
const item=make('Actor.a.Item.i','Item','action',{description:{value:'<p>Exact 😀 &amp;</p>',gm:'private_source_sentinel_783f'}});
item.parent=actor;actor.items.set('i',item);
const scene=make('Scene.s','Scene','');const token=make('Scene.s.Token.t','Token','');
token.parent=scene;token.actor=actor;token.baseActor=actor;token.isLinked=true;
globalThis.game={version:'14.369',system:{id:'pf2e',version:'8.6.1'},ready:true,user:{isGM:true},actors:new Map([['a',actor]]),items:new Map()};
globalThis.foundry={utils:{fromUuid:async uuid=>docs.get(uuid)},documents:{Actor:{TYPES:['npc','loot']},Item:{TYPES:['action','campaignFeature']}}};
console.log(JSON.stringify([await getActorTypes(),await readActor({actor_uuid:actor.uuid}),await readItem({item_uuid:item.uuid,sections:['description']}),await listActorItems({token_uuid:token.uuid}),await readItem({item_uuid:item.uuid,token_uuid:token.uuid})]));
"""
        process = subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1],check=True)
        responses = json.loads(process.stdout)
        for tool, args, response in [(get_actor_types, {}, responses[0]),(read_actor,dict(actor_uuid='Actor.a'),responses[1]),(read_item,dict(item_uuid='Actor.a.Item.i',sections=['description']),responses[2]),(list_actor_items,dict(token_uuid='Scene.s.Token.t'),responses[3]),(read_item,dict(item_uuid='Actor.a.Item.i',token_uuid='Scene.s.Token.t'),responses[4])]:
            with self.subTest(tool=tool.name,args=args):
                self.manager.call.return_value=response
                self.assertEqual(await tool.fn(**args),response)
                self.assertNotIn('private_source_sentinel_783f',json.dumps(response))

    async def test_token_context_is_preserved_for_linked_and_synthetic_items(self):
        for uuid, linked in [('Actor.a.Item.i', True), ('Scene.s.Token.t.Actor.a.Item.i', False)]:
            response = reader('Item')
            response['identity'].update(uuid=uuid, source_kind='token', instance=dict(scene_uuid='Scene.s', scene_name='Scene', token_uuid='Scene.s.Token.t', token_name='Token', actor_link=linked, base_actor=dict(uuid='Actor.a', name='Base', name_truncated=False)))
            self.manager.call.return_value = response
            self.assertEqual(await read_item.fn(item_uuid=uuid, token_uuid='Scene.s.Token.t'), response)
            with self.assertRaises(ToolError):
                await read_item.fn(item_uuid=uuid, token_uuid='Scene.s.Token.wrong')
        self.manager.call.return_value = reader()
        with self.assertRaises(ToolError):
            await read_actor.fn(actor_uuid='Actor.other')

    async def test_wrong_runtime_and_document_kind_do_not_leak_semantics(self):
        for response in [reader('Item'), dict(reader(), runtime=dict(RUNTIME, system_id='dnd5e')), dict(reader(), runtime=dict(RUNTIME, core_version='13.999'))]:
            self.manager.call.return_value = response
            with self.assertRaises(ToolError):
                await read_actor.fn(actor_uuid='Actor.a')

    async def test_real_mcp_discovery_strict_inputs_and_read_only_annotations(self):
        async with Client(mcp) as client:
            tools={tool.name:tool for tool in await client.list_tools()}
            for name in ('get_actor_types','read_actor','read_item','list_actor_items'):
                tool=tools[name]
                self.assertTrue(tool.annotations.readOnlyHint)
                self.assertFalse(tool.annotations.destructiveHint)
                self.assertFalse(tool.inputSchema['additionalProperties'])
                self.assertIn('GM',tool.description)
                self.assertIn('PF2e',tool.description)
            schema=tools['read_actor'].inputSchema['properties']
            self.assertEqual(schema['limit']['maximum'],100)
            self.assertEqual(schema['max_bytes']['minimum'],8000)
            self.assertEqual(schema['sections']['default'],['identity','source'])
            self.assertEqual(tools['read_item'].inputSchema['required'],['item_uuid'])
            self.manager.call.return_value=reader()
            result=await client.call_tool('read_actor',{'actor_uuid':'Actor.a'})
            self.assertFalse(result.is_error)
            for args in [dict(actor_uuid='Actor.a',unknown='no'),dict(actor_uuid='Actor.a',limit=True),dict(actor_uuid='Actor.a',limit='2'),dict(actor_uuid=4),dict(actor_uuid='Actor.a',sections=['source','source']),dict(actor_uuid='Actor.a',sections=['bad']),dict(actor_uuid='Actor.a',cursor='é')]:
                with self.subTest(args=args):
                    self.manager.reset_mock()
                    result=await client.call_tool('read_actor',args,raise_on_error=False)
                    self.assertTrue(result.is_error)
                    self.manager.call.assert_not_awaited()
            result=await client.call_tool('get_actor_types',{'unknown':True},raise_on_error=False)
            self.assertTrue(result.is_error)
