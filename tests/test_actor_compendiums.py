"""MCP compendium input/output contracts and actual browser DTO compatibility."""
import asyncio
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from fastmcp import Client
from fastmcp.exceptions import ToolError

from foundry_mcp_server.mcp_server.actor_compendiums import list_actor_compendiums, search_compendium_actors
from foundry_mcp_server.mcp_server.server import mcp
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from foundry_mcp_server.ws.connection import RpcError

RUNTIME=dict(core_version='14.369',system_id='pf2e',system_version='8.6.1')


def result(search=False, document_type='Actor'):
    if search:
        identity=dict(document_name=document_type,id='a',uuid=f'Compendium.test.pack.{document_type}.a',name='Duplicate',name_truncated=False,type='npc' if document_type=='Actor' else 'action',source_kind='compendium',folder=None,pack=dict(id='test.pack',title='Pack'),actor=None,instance=None)
        node=dict(kind=document_type.lower(),identity=identity,parent_uuid=None,next_call=dict(tool='read_actor' if document_type=='Actor' else 'read_item',arguments={'actor_uuid' if document_type=='Actor' else 'item_uuid':identity['uuid']}))
    else:
        node=dict(kind='pack',id='test.pack',title='Pack',title_truncated=False,document_type=document_type,visible=True,folder=None,parent_uuid=None,next_call=None,search_scope=dict(pack_ids=['test.pack'],document_type=document_type),limitations=['Add a literal query to search this scope.'])
    return dict(contract_version=1,runtime=RUNTIME.copy(),revision='revision',nodes=[node],scopes=[dict(id='test.pack' if search else 'packs',status='searched',reason=None)],pagination=dict(complete=True,next_cursor=None,returned=1),limitations=[])


class ActorCompendiumTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def test_exact_rpc_defaults_and_item_scope(self):
        for tool,args,method,params,search,kind in [(list_actor_compendiums,{},'listActorCompendiums',dict(document_type='Actor',query=None,limit=50,max_bytes=48000,cursor=None),False,'Actor'),(search_compendium_actors,dict(pack_ids=['test.pack'],query='Duplicate',document_type='Item'),'searchCompendiumActors',dict(pack_ids=['test.pack'],query='Duplicate',types=None,document_type='Item',limit=50,max_bytes=48000,cursor=None),True,'Item')]:
            self.manager.reset_mock();self.manager.call.return_value=result(search,kind)
            self.assertEqual(await tool.fn(**args),result(search,kind));self.manager.call.assert_awaited_once_with('gm',method,params,timeout=15.0)

    async def test_invalid_inputs_do_not_access_packs(self):
        for extra in [dict(pack_ids=[]),dict(pack_ids=['x','x']),dict(pack_ids=['x'*257]),dict(pack_ids=['  ']),dict(pack_ids=['x']*11),dict(query=' '),dict(types=[]),dict(types=['npc','npc']),dict(types=['weapon']),dict(document_type='Item',types=['npc']),dict(limit=True),dict(max_bytes=48001),dict(cursor='é')]:
            args=dict(pack_ids=['test.pack'],query='Duplicate');args.update(extra)
            with self.subTest(extra=extra),self.assertRaises(ToolError):await search_compendium_actors.fn(**args)
        for args in [dict(document_type='JournalEntry'),dict(query=' '),dict(limit=0)]:
            with self.subTest(args=args),self.assertRaises(ToolError):await list_actor_compendiums.fn(**args)
        self.manager.call.assert_not_awaited()

    async def test_browser_and_transport_errors_are_actionable(self):
        for error,code in [(RpcError(dict(code='ContentChanged',message='Changed',recovery='Restart')),'ContentChanged'),(RpcError(dict(type='PermissionDenied',message='Denied')),'PermissionDenied'),(asyncio.TimeoutError(),'ReadFailed'),(ConnectionError(),'BridgeUnavailable'),(RuntimeError(),'BridgeUnavailable')]:
            self.manager.call.side_effect=error
            with self.assertRaises(ToolError) as caught:await list_actor_compendiums.fn()
            self.assertEqual(json.loads(str(caught.exception))['code'],code)

    async def test_malformed_pack_responses_and_byte_limits(self):
        good=result()
        for bad in [None,{},dict(good,private='unexpected'),dict(good,contract_version=True),dict(good,runtime=dict(RUNTIME,system_id='other')),dict(good,pagination=dict(complete=True,next_cursor='x',returned=1)),dict(good,limitations=['😀'*12000])]:
            self.manager.call.return_value=bad
            with self.subTest(response_type=type(bad)),self.assertRaises(ToolError):await list_actor_compendiums.fn()
        for field,value in [('id','x'*257),('visible','yes'),('next_call',dict(tool='search_compendium_actors',arguments={})),('search_scope',dict(pack_ids=['wrong'],document_type='Actor')),('limitations',[])]:
            bad=result();bad['nodes'][0][field]=value;self.manager.call.return_value=bad
            with self.subTest(field=field),self.assertRaises(ToolError):await list_actor_compendiums.fn()

    async def test_scope_failures_survive_and_missing_scopes_are_rejected(self):
        response=result(True);response['scopes'].append(dict(id='test.denied',status='denied',reason='Pack access required.'));self.manager.call.return_value=response
        self.assertEqual(await search_compendium_actors.fn(pack_ids=['test.pack','test.denied'],query='Duplicate'),response)
        with self.assertRaises(ToolError):await search_compendium_actors.fn(pack_ids=['test.pack','test.missing'],query='Duplicate')
        response['nodes'][0]['identity']['type']='loot'
        with self.assertRaises(ToolError):await search_compendium_actors.fn(pack_ids=['test.pack','test.denied'],query='Duplicate')

    async def test_real_mcp_discovery_strict_schema_and_calls(self):
        async with Client(mcp) as client:
            tools={tool.name:tool for tool in await client.list_tools()}
            for name in ('list_actor_compendiums','search_compendium_actors'):
                tool=tools[name];self.assertTrue(tool.annotations.readOnlyHint);self.assertFalse(tool.inputSchema['additionalProperties']);self.assertIn('GM',tool.description);self.assertIn('next_cursor',tool.description)
            self.assertEqual(tools['search_compendium_actors'].inputSchema['required'],['pack_ids','query'])
            self.assertEqual(tools['search_compendium_actors'].inputSchema['properties']['pack_ids']['maxItems'],10)
            self.manager.call.return_value=result(True)
            response=await client.call_tool('search_compendium_actors',dict(pack_ids=['test.pack'],query='Duplicate'));self.assertFalse(response.is_error)
            for args in [dict(pack_ids=['test.pack'],query='x',extra=True),dict(pack_ids=['test.pack'],query='x',limit=True),dict(pack_ids=['test.pack'],query='x',types=['loot']),dict(pack_ids=['test.pack','test.pack'],query='x')]:
                self.manager.reset_mock();response=await client.call_tool('search_compendium_actors',args,raise_on_error=False);self.assertTrue(response.is_error);self.manager.call.assert_not_awaited()

    async def test_actual_browser_dtos_using_exact_forwarded_rpc_parameters(self):
        script=r"""
import {listActorCompendiums,searchCompendiumActors} from './foundry-module/scripts/actorPacks.js';
const make=(id,documentName,type)=>({collection:id,documentName,title:'Duplicate Pack',visible:true,testUserPermission:()=>true,getIndex:async()=>new Map([['a',{_id:'a',name:'Duplicate',type}]]),getUuid:id=>`Compendium.test.${documentName.toLowerCase()}.${documentName}.${id}`});
const actorPack=make('test.actor','Actor','npc');const itemPack=make('test.item','Item','action');
globalThis.game={version:'14.369',system:{id:'pf2e',version:'8.6.1'},ready:true,user:{isGM:true},actors:new Map(),items:new Map(),packs:new Map([['test.actor',actorPack],['test.item',itemPack]])};
const methods={listActorCompendiums,searchCompendiumActors};
console.log(JSON.stringify(await methods[process.argv[2]](JSON.parse(process.argv[3]))));
"""
        async def browser(client,method,params,timeout):
            process=subprocess.run(['node','--input-type=module','-',method[0].lower()+method[1:],json.dumps(params)],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
            self.assertEqual(process.returncode,0,process.stderr)
            return json.loads(process.stdout)
        self.manager.call.side_effect=browser
        for tool,args in [(list_actor_compendiums,{}),(list_actor_compendiums,dict(document_type='Item')),(search_compendium_actors,dict(pack_ids=['test.actor'],query='Duplicate')),(search_compendium_actors,dict(pack_ids=['test.item'],query='Duplicate',document_type='Item'))]:
            with self.subTest(tool=tool.name,args=args):
                response=await tool.fn(**args)
                self.assertEqual(len(response['nodes']),1)
                if tool is list_actor_compendiums:
                    self.assertIsNone(response['nodes'][0]['next_call'])
                    self.assertIn('search_scope',response['nodes'][0])
                else:
                    self.assertEqual(response['nodes'][0]['identity']['source_kind'],'compendium')
