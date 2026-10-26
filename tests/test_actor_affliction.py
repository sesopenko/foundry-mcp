"""PF2e-specific8.6.1 disabled affliction boundary, not schema-only support."""
import json
import copy
import subprocess
import unittest
from unittest.mock import AsyncMock
from fastmcp import Client
from pathlib import Path
from foundry_mcp_server.mcp_server.actors import read_item, list_actor_items, get_actor_types, _registry
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.server import mcp
from foundry_mcp_server.mcp_server.actor_compendiums import search_compendium_actors


class ActorAfflictionTests(unittest.TestCase):
    def test_published_reader_names_unsupported_runtime_and_recovery(self):
        description=read_item.description
        for phrase in ['Affliction Items are explicitly unsupported','PF2e8.6.1','UnsupportedType','get_actor_types']:
            self.assertIn(phrase,description)

    def test_actual_browser_rejects_affliction_without_reading_source(self):
        script=r"""
import {readItem,getActorTypes} from './foundry-module/scripts/actors.js';
let sourceReads=0;
const item={id:'a',uuid:'Item.a',name:'Affliction',type:'affliction',documentName:'Item',parent:null,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>{sourceReads++;throw new Error('source must not be read');}};
globalThis.game={version:'14.369',system:{id:'pf2e',version:'8.6.1'},ready:true,user:{isGM:true},actors:new Map(),items:new Map([[item.uuid,item]])};
globalThis.foundry={utils:{fromUuid:async uuid=>uuid===item.uuid?item:null}};
let error=null;try{await readItem({item_uuid:'Item.a',sections:['source']});}catch(e){error=e.rpcError;}
const registry=await getActorTypes();game.system.version='9.0.0';const unsupported=await getActorTypes();
console.log(JSON.stringify({error,sourceReads,registry,unsupported}));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(process.returncode,0,process.stderr)
        result=json.loads(process.stdout)
        self.assertEqual(result['sourceReads'],0)
        self.assertEqual(result['error']['code'],'UnsupportedType')
        entry=next(row for row in result['registry']['item_types'] if row['type']=='affliction')
        self.assertFalse(entry['source_supported']);self.assertFalse(entry['mapped_supported']);self.assertFalse(entry['effective_supported'])
        self.assertEqual(entry['verification']['live']['status'],'not_run')
        self.assertFalse(entry['in_scope'])
        self.assertIn('deferred', ' '.join(entry['limitations']))
        self.assertTrue(_registry(result['registry']))
        self.assertTrue(_registry(result['unsupported']))
        outside=next(row for row in result['unsupported']['item_types'] if row['type']=='affliction')
        self.assertTrue(all(outside[flag] is False for flag in ('in_scope','source_supported','mapped_supported','effective_supported')))
        for flag in ('in_scope','source_supported','mapped_supported','effective_supported'):
            bad=copy.deepcopy(result['registry'])
            next(row for row in bad['item_types'] if row['type']=='affliction')[flag]=True
            with self.subTest(flag=flag):self.assertFalse(_registry(bad))

    def test_discovery_description_names_deferred_delivery_scope(self):
        for description in (get_actor_types.description,read_item.description):
            self.assertIn('deferred',description)
            self.assertIn('in_scope false',description)


class AfflictionDiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_discovery_keeps_deferral_and_readonly_contract(self):
        async with Client(mcp) as client:
            tools={tool.name:tool for tool in await client.list_tools()}
        for name in ('get_actor_types','read_item'):
            self.assertIn('in_scope false',tools[name].description)
            self.assertIn('deferred',tools[name].description)
            self.assertTrue(tools[name].annotations.readOnlyHint)

    async def test_no_actual_tool_input_enum_offers_affliction_filter(self):
        async with Client(mcp) as client:
            tools=await client.list_tools()
        def inspect(node):
            if isinstance(node,dict):
                self.assertNotIn('affliction',node.get('enum',[]))
                self.assertNotEqual(node.get('const'),'affliction')
                for value in node.values():inspect(value)
            elif isinstance(node,list):
                for value in node:inspect(value)
        for tool in tools:
            with self.subTest(tool=tool.name):inspect(tool.inputSchema)

    async def test_python_affliction_filters_fail_before_browser_calls(self):
        manager=AsyncMock();register_foundry_manager(manager)
        with self.assertRaises(ToolError):
            await list_actor_items.fn(actor_uuid='Actor.a',types=['affliction'])
        with self.assertRaises(ToolError):
            await search_compendium_actors.fn(pack_ids=['pf2e.example'],query='source',document_type='Item',types=['affliction'])
        manager.call.assert_not_awaited()
