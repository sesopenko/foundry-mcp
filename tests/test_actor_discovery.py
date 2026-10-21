"""MCP discovery contracts and browser DTO boundary for world Actor navigation."""
import asyncio
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from fastmcp import Client
from fastmcp.exceptions import ToolError

from foundry_mcp_server.mcp_server.actor_discovery import get_actor_tree, search_actors, list_scene_actors
from foundry_mcp_server.mcp_server.server import mcp
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from foundry_mcp_server.ws.connection import RpcError

RUNTIME=dict(core_version='14.369',system_id='pf2e',system_version='8.6.1')


def folder():
    return dict(kind='folder',id='f',uuid='Folder.f',name='Empty',name_truncated=False,parent_uuid=None,depth=1,children_complete=True,expand=None)


def actor():
    identity=dict(document_name='Actor',id='a',uuid='Actor.a',name='Duplicate',name_truncated=False,type='npc',source_kind='world',folder=None,pack=None,actor=None,instance=None)
    return dict(kind='actor',identity=identity,parent_uuid=None,depth=0,folder_path=[],next_call=dict(tool='read_actor',arguments=dict(actor_uuid='Actor.a')))


def response(tree=True):
    result=dict(contract_version=1,runtime=RUNTIME.copy(),revision='revision',nodes=[folder(),actor()] if tree else [actor()],scopes=[dict(id='world',status='searched',reason=None)],pagination=dict(complete=True,next_cursor=None,returned=2 if tree else 1),limitations=[])
    if tree:result['tree_complete']=True
    return result


class ActorDiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def test_exact_rpc_inputs_and_defaults(self):
        for tool,args,method,params,tree in [(get_actor_tree,{},'getActorTree',dict(folder_uuid=None,depth=2,limit=50,max_bytes=48000,cursor=None),True),(search_actors,dict(query='Duplicate'),'searchActors',dict(query='Duplicate',types=None,folder_uuid=None,recursive=True,limit=50,max_bytes=48000,cursor=None),False)]:
            self.manager.reset_mock();self.manager.call.return_value=response(tree)
            self.assertEqual(await tool.fn(**args),response(tree))
            self.manager.call.assert_awaited_once_with('gm',method,params,timeout=15.0)

    async def test_bad_direct_inputs_never_call_browser(self):
        for args in [dict(depth=True),dict(depth=0),dict(depth=6),dict(folder_uuid=''),dict(folder_uuid='x'*513),dict(limit=True),dict(limit=101),dict(max_bytes=7999),dict(cursor='é')]:
            with self.subTest(args=args),self.assertRaises(ToolError):await get_actor_tree.fn(**args)
        for args in [dict(query=' '),dict(query='x'*201),dict(query='x',types=[]),dict(query='x',types=['npc','npc']),dict(query='x',types=['loot']),dict(query='x',recursive=1)]:
            with self.subTest(args=args),self.assertRaises(ToolError):await search_actors.fn(**args)
        self.manager.call.assert_not_awaited()

    async def test_errors_preserve_browser_codes_and_recovery(self):
        for error,code in [(RpcError(dict(code='ContentChanged',message='Changed',recovery='Restart.')),'ContentChanged'),(RpcError(dict(type='PermissionDenied',message='Denied')),'PermissionDenied'),(asyncio.TimeoutError(),'ReadFailed'),(ConnectionError(),'BridgeUnavailable'),(RuntimeError(),'BridgeUnavailable')]:
            self.manager.call.side_effect=error
            with self.assertRaises(ToolError) as caught:await get_actor_tree.fn()
            self.assertEqual(json.loads(str(caught.exception))['code'],code)

    async def test_response_envelope_counts_bytes_and_runtime_are_strict(self):
        good=response()
        malformed=[None,{},dict(good,private='unexpected'),dict(good,contract_version=True),dict(good,runtime=dict(RUNTIME,system_id='other')),dict(good,tree_complete='yes'),dict(good,pagination=dict(complete=True,next_cursor='x',returned=2)),dict(good,pagination=dict(complete=True,next_cursor=None,returned=True)),dict(good,scopes=[]),dict(good,revision=None),dict(good,limitations=['😀'*12000])]
        for result in malformed:
            self.manager.call.return_value=result
            with self.subTest(result_type=type(result)),self.assertRaises(ToolError):await get_actor_tree.fn()
        self.manager.call.return_value=good
        with self.assertRaises(ToolError):await get_actor_tree.fn(limit=1)
        self.manager.call.return_value=dict(good,limitations=['é'*4000])
        with self.assertRaises(ToolError):await get_actor_tree.fn(max_bytes=8000)

    async def test_malformed_nodes_and_excluded_types_are_rejected(self):
        for change in [('kind','item'),('depth',True),('parent_uuid',8),('next_call',dict(tool='read_actor',arguments=dict(actor_uuid='Actor.wrong'))),('folder_path',[{'name':'unidentified'}])]:
            result=response(False);result['nodes'][0][change[0]]=change[1];self.manager.call.return_value=result
            with self.subTest(change=change),self.assertRaises(ToolError):await search_actors.fn(query='Duplicate')
        result=response(False);result['nodes'][0]['identity']['type']='loot';self.manager.call.return_value=result
        with self.assertRaises(ToolError):await search_actors.fn(query='Duplicate')
        result=response();result['nodes'][0].update(children_complete=False,expand=dict(folder_uuid='Folder.f'));self.manager.call.return_value=result
        with self.assertRaises(ToolError):await get_actor_tree.fn()
        result['tree_complete']=False
        self.assertEqual(await get_actor_tree.fn(),result)

    async def test_incomplete_scope_and_empty_search_remain_explicit(self):
        result=response(False);result.update(nodes=[],scopes=[dict(id='Folder.f',status='incomplete',reason='Some records denied.')]);result['pagination']['returned']=0
        self.manager.call.return_value=result
        self.assertEqual(await search_actors.fn(query='Absent',folder_uuid='Folder.f'),result)

    async def test_real_mcp_discovery_schemas_unknown_inputs_and_follow_up(self):
        async with Client(mcp) as client:
            tools={tool.name:tool for tool in await client.list_tools()}
            for name in ('get_actor_tree','search_actors'):
                tool=tools[name];self.assertTrue(tool.annotations.readOnlyHint);self.assertFalse(tool.inputSchema['additionalProperties']);self.assertIn('next_cursor',tool.description);self.assertIn('read_actor',tool.description);self.assertIn('GM',tool.description)
            self.assertEqual(tools['get_actor_tree'].inputSchema['properties']['depth']['maximum'],5)
            self.assertEqual(tools['search_actors'].inputSchema['required'],['query'])
            self.manager.call.return_value=response(False)
            result=await client.call_tool('search_actors',dict(query='Duplicate'))
            self.assertFalse(result.is_error)
            for name,args in [('get_actor_tree',dict(unknown=True)),('get_actor_tree',dict(depth=True)),('search_actors',dict(query='x',recursive='true')),('search_actors',dict(query='x',types=['npc','npc'])),('search_actors',dict(query='x',limit='2'))]:
                self.manager.reset_mock();result=await client.call_tool(name,args,raise_on_error=False)
                self.assertTrue(result.is_error);self.manager.call.assert_not_awaited()

    async def test_actual_world_and_scene_browser_dtos(self):
        script=r"""
import {getActorTree,searchActors} from './foundry-module/scripts/actorWorld.js';
import {listSceneActors} from './foundry-module/scripts/actorScenes.js';
const make=(uuid,documentName,type)=>({uuid,id:uuid.split('.').at(-1),documentName,type,name:'Duplicate',parent:null,folder:null,compendium:null,items:new Map(),testUserPermission:()=>true,toObject:()=>({name:'Duplicate',type,folder:null})});
const actor=make('Actor.a','Actor','npc');const folder=make('Folder.f','Folder','Actor');
const scene=make('Scene.s','Scene','');const token=make('Scene.s.Token.t','Token','');token.parent=scene;token.actor=actor;token.baseActor=actor;token.isLinked=true;scene.tokens=new Map([['t',token]]);
globalThis.game={version:'14.369',system:{id:'pf2e',version:'8.6.1'},ready:true,user:{isGM:true},actors:new Map([['a',actor]]),items:new Map(),folders:new Map([['f',folder]]),scenes:new Map([['s',scene]])};
globalThis.foundry={utils:{fromUuid:async()=>null}};
console.log(JSON.stringify([await getActorTree(),await searchActors({query:'Duplicate'}),await listSceneActors(),await listSceneActors({scene_uuid:'Scene.s'})]));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1],check=True)
        results=json.loads(process.stdout)
        for tool,args,result in [(get_actor_tree,{},results[0]),(search_actors,dict(query='Duplicate'),results[1]),(list_scene_actors,{},results[2]),(list_scene_actors,dict(scene_uuid='Scene.s'),results[3])]:
            self.manager.call.return_value=result
            with self.subTest(tool=tool.name):self.assertEqual(await tool.fn(**args),result)

    async def test_scene_inputs_missing_actor_and_shape_boundaries(self):
        for args in [dict(query='Guard'),dict(types=['npc']),dict(scene_uuid='Scene.s',types=[]),dict(scene_uuid='Scene.s',types=['npc','npc']),dict(scene_uuid='Scene.s',query=' ')]:
            with self.subTest(args=args),self.assertRaises(ToolError):await list_scene_actors.fn(**args)
        self.manager.call.assert_not_awaited()
        result=response(False);result['unsupported_count']=0;result['nodes']=[dict(kind='token',id='t',uuid='Scene.s.Token.t',name='Missing',name_truncated=False,parent_uuid='Scene.s',identity=None,actor_link=False,base_actor=None,next_call=None,limitations=['ActorUnavailable: missing current actor.'])]
        self.manager.call.return_value=result
        self.assertEqual(await list_scene_actors.fn(scene_uuid='Scene.s'),result)
        self.manager.call.assert_awaited_once_with('gm','listSceneActors',dict(scene_uuid='Scene.s',query=None,types=None,limit=50,max_bytes=48000,cursor=None),timeout=15.0)
        result['nodes'][0]['limitations']=[]
        with self.assertRaises(ToolError):await list_scene_actors.fn(scene_uuid='Scene.s')

    async def test_scene_actual_discovery_schema(self):
        async with Client(mcp) as client:
            tools={tool.name:tool for tool in await client.list_tools()};tool=tools['list_scene_actors']
            self.assertTrue(tool.annotations.readOnlyHint);self.assertFalse(tool.inputSchema['additionalProperties'])
            for value in ('token_uuid','base_actor','next_cursor','Scene.<id>','GM'):self.assertIn(value,tool.description)
            for args in [dict(extra=True),dict(limit=True),dict(scene_uuid='Scene.s',types=['loot'])]:
                result=await client.call_tool('list_scene_actors',args,raise_on_error=False);self.assertTrue(result.is_error)
            self.manager.call.assert_not_awaited()
