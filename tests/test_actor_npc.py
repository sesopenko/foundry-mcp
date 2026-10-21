"""PF2e-specific NPC8.6.1 strict source boundary; no derived statistics."""
import copy
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import AsyncMock
from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_actor, _npc_spec
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_action import response


def npc(path,value,present=True):
    page=response(path,value,present=present)
    page['identity'].update(document_name='Actor',uuid='Actor.a',type='npc')
    row=page['records'][0];raw=row['raw'][0];raw['document_uuid']='Actor.a'
    row.update(key='source:'+path,mapped=dict(concept=(_npc_spec(path) or ('unknown',))[0],value=value if present else None,unit=None))
    row['provenance'].update(mapping='pf2e.npc.source.v1',contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}])
    return page


class NpcBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,page):
        self.manager.call.return_value=page
        return await read_actor.fn(actor_uuid='Actor.a',sections=['source'])

    async def test_scalar_and_empty_markers(self):
        for path,value in [('/system/attributes/hp/value',0),('/system/abilities/str/mod',-2),('/system/details/alliance',None),('/system/perception/vision',False),('/system/skills',{}),('/system/skills/a~1~0/base',None),('/system/skills//note','exact'),('/system/traits/value',[]),('/system/attributes/immunities',[]),('/system/attributes/resistances/0/exceptions',[])]:
            with self.subTest(path=path):await self.read(npc(path,value))
        await self.read(npc('/system/attributes/hp/value',None,False))

    async def test_escaped_nested_predicate_leaves_and_compound_iwr(self):
        for path,value in [('/system/skills/arcana/special/0/predicate',[]),('/system/skills/arcana/special/0/predicate/0/and/0','target:trait:undead'),('/system/attributes/resistances/0/exceptions/0/definition/0/eq/1',2),('/system/attributes/resistances/0/doubleVs/0/label','Silver'),('/system/skills/a/special/0/predicate/0/a~1~0',{}),('/system/skills/a/special/0/predicate/0/null',None)]:
            with self.subTest(path=path):await self.read(npc(path,value))

    async def test_invalid_path_types_semantics_and_owner_are_rejected(self):
        for path,value in [('/system/attributes/hp/value',True),('/system/attributes/hp/value',None),('/system/perception/vision',0),('/system/skills',{'secret':1}),('/system/traits/value',['secret']),('/system/attributes/immunities/0/value',1),('/system/attributes/resistances/0/applyOnce',True),('/system/skills/a/special/00/label','bad'),('/system/skills/a~2/base',2),('/system/skills/a/special/0/predicate/key','bad'),('/system/skills/a/special/0/predicate','bad'),('/system/skills/a/special/0/predicate',{}),('/system/skills/a/special/0/predicate/0/'+('/'.join(['x']*32)),'bad'),('/system/details/privateNotes','secret'),('/system/attributes/hp/derived',1),('/flags/secret',1)]:
            with self.subTest(path=path),self.assertRaises(ToolError):await self.read(npc(path,value))
        original=npc('/system/attributes/hp/value',12)
        for mutate in [lambda p:p['identity'].update(type='character'),lambda p:p['records'][0]['mapped'].update(concept='effective_hp'),lambda p:p['records'][0]['mapped'].update(value=13),lambda p:p['records'][0]['provenance'].update(mapping='made_up'),lambda p:p['records'][0]['raw'][0].update(document_uuid='Actor.other'),lambda p:p['records'][0]['provenance']['contributors'][0].update(path='/name')]:
            page=copy.deepcopy(original);mutate(page)
            with self.assertRaises(ToolError):await self.read(page)

    async def test_actual_node_descriptors_and_reader_pages(self):
        script=r"""
import {readActor} from './foundry-module/scripts/actors.js';
const source={name:'NPC',type:'npc',system:{skills:{'a/~':{base:null,note:'Exact',special:[{label:'Special',base:12,predicate:[{and:['x',{eq:['a',1]}]}]}]}},attributes:{hp:{value:0,max:12,temp:0},resistances:[{type:'physical',value:2,exceptions:[{label:'silver',definition:[{or:['silver','holy']}]}],doubleVs:['wood']}],immunities:[],weaknesses:[]},traits:{value:[]}}};
const actor={id:'a',uuid:'Actor.a',name:'NPC',type:'npc',documentName:'Actor',folder:null,compendium:null,items:new Map(),testUserPermission:()=>true,toObject:()=>structuredClone(source)};
globalThis.game={version:'14.369',system:{id:'pf2e',version:'8.6.1'},ready:true,user:{isGM:true},items:new Map(),actors:new Map([['a',actor]])};globalThis.foundry={utils:{fromUuid:async()=>actor}};
const pages=[];let cursor=null;do {const page=await readActor({actor_uuid:'Actor.a',sections:['source'],limit:10,...(cursor?{cursor}:{})});pages.push(page);cursor=page.pagination.next_cursor;}while(cursor);console.log(JSON.stringify(pages));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(process.returncode,0,process.stderr)
        pages=json.loads(process.stdout)
        for page in pages:await self.read(page)
        records=[r for page in pages for r in page['records']]
        self.assertGreater(len(records),50)
        self.assertTrue(any(r['raw'][0]['path'].endswith('/predicate/0/and/1/eq/1') for r in records))
