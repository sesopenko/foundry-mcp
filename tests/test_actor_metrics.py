"""Actual MCP typed discovery and browser/Python guarded metric interoperability."""
import copy
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import AsyncMock
from fastmcp import Client
from fastmcp.exceptions import ToolError
from pydantic import ValidationError
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from foundry_mcp_server.mcp_server.server import mcp
from foundry_mcp_server.mcp_server import selective as S, selective_models as M

SCRIPT = r"""
import {readActorSelected} from './foundry-module/scripts/actors.js';
const actor={uuid:'Actor.a',id:'a',name:'PC',type:'character',documentName:'Actor',parent:null,folder:null,compendium:null,items:new Map(),testUserPermission:()=>true,toObject:()=>({name:'PC',type:'character',system:{}}),inventory:{currency:{copperValue:0},get totalWealth(){throw Error('SECRET');},bulk:{value:{normal:0,light:0},encumberedAfter:5,max:10,isEncumbered:false,isOverMax:false}}};
actor.items.set('i',{uuid:'Actor.a.Item.i',name:'Thing',type:'equipment',quantity:1,assetValue:{copperValue:100},bulk:{normal:0,light:1},testUserPermission:()=>true});
globalThis.game={version:'14.369',system:{id:'pf2e',version:'8.6.1'},ready:true,user:{isGM:true},actors:new Map([['a',actor]]),items:new Map()};
globalThis.foundry={utils:{fromUuid:async()=>actor}};
const results=[];
for(const details of [[],['wealth','bulk'],['wealth.items','bulk.items']])for(const evidence of [false,true]){
const args={actor_uuid:actor.uuid,select:{details,evidence}};
results.push({args,packet:await readActorSelected(args)});
}
console.log(JSON.stringify(results));
"""


class MetricTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        result=subprocess.run(['node','--input-type=module'],input=SCRIPT,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1],check=True)
        cls.cases=json.loads(result.stdout)

    async def asyncSetUp(self):
        self.manager=AsyncMock()
        register_foundry_manager(self.manager)

    async def test_actual_mcp_packets_and_discovery(self):
        async with Client(mcp) as client:
            tool=next(t for t in await client.list_tools() if t.name=='read_actor')
            self.assertIn('wealth.items',json.dumps(tool.inputSchema))
            self.assertIn('potentially_missing',json.dumps(tool.outputSchema))
            for case in self.cases:
                self.manager.call.return_value=case['packet']
                result=await client.call_tool('read_actor',case['args'])
                self.assertEqual(result.structured_content,case['packet']['result'])
                self.assertNotIn('SECRET',json.dumps(result.structured_content))

    async def test_forged_missing_status_and_types_rejected(self):
        case=self.cases[2]
        for change in ('unknown_reason','false_zero','missing_value','complete','unit','owner','omitted_field'):
            packet=copy.deepcopy(case['packet'])
            row=packet['proof']['records'][1]
            if change=='unknown_reason':row['mapped']['value']['reason']='secret'
            if change=='false_zero':packet['proof']['records'][0]['mapped']['value']['value']=False
            if change=='missing_value':row['mapped']['value']['value']=0
            if change=='complete':packet['proof']['sections'][0].update(status='complete',reasons=[])
            if change=='unit':row['mapped']['unit']='gp'
            if change=='owner':packet['proof']['identity']['type']='npc'
            if change=='omitted_field':
                packet['proof']['records'].pop(0)
                packet['proof']['pagination']['returned']-=1
                packet['group_lengths'][0]-=1
                packet['result']=S.compact_read(packet['proof'],packet['group_lengths'],False)
            self.manager.call.return_value=packet
            with self.subTest(change=change),self.assertRaises(ToolError):
                await S.read(M.ActorRequest.model_validate(case['args']))

    def test_typed_runtime_availability(self):
        for value in (0,False):
            M.Value(concept='x',value=value,basis='runtime',availability='available')
        for args in [dict(value=0,availability='potentially_missing',reason='getter_failed'),dict(value=None,availability='available'),dict(value=0)]:
            with self.assertRaises(ValidationError):M.Value(concept='x',basis='runtime',**args)
