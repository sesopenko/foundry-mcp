"""PF2e-specific8.6.1 transformed character/NPC statistics boundary."""
import unittest
import json
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock

from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_actor, LORE_RANKS, _actor_current_concept
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_action import response


def current(path='/system/attributes/ac/value', value=23, present=True, actor_type='character'):
    page=response(path,value,present=present,section='statistics')
    page['identity'].update(document_name='Actor',uuid='Actor.a',type=actor_type)
    page['sections'][0].update(status='partial',reasons=['other_statistics_pending']+([] if present else ['current_fields_unavailable']))
    row=page['records'][0];raw=row['raw'][0]
    raw.update(document_uuid='Actor.a',basis='transformed')
    mapped=dict(rank=value,label=LORE_RANKS[value]) if present and path.endswith('/rank') and type(value) is int and 0<=value<=4 else value if present else None
    try:concept=_actor_current_concept(path)
    except (KeyError,ValueError):concept='invalid'
    row.update(key='statistics:'+path,mapped=dict(concept=concept,value=mapped,unit=None))
    row['provenance']=dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.actor.current.v1',limitations=['serialized_current_value_not_target_context'])
    return page


class CurrentBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,page):
        self.manager.call.return_value=page
        return await read_actor.fn(actor_uuid='Actor.a',sections=[s['name'] for s in page['sections']])

    async def test_selected_types_missing_null_and_rank(self):
        for actor_type in ('character','npc'):
            for path,value in [('/system/abilities/str/mod',-2.5),('/system/attributes/ac/value',23),('/system/attributes/ac/details','exception'),('/system/attributes/hp/max',42),('/system/attributes/hp/temp',0),('/system/saves/will/totalModifier',11),('/system/saves/reflex/breakdown','trace'),('/system/perception/vision',False),('/system/perception/rank',4),('/system/movement/speeds/land/type','land'),('/system/movement/speeds/fly/source',None),('/system/movement/speeds/swim',None)]:
                with self.subTest(actor_type=actor_type,path=path):await self.read(current(path,value,actor_type=actor_type))
            await self.read(current(present=False,actor_type=actor_type))
        await self.read(current('/system/abilities/str/base',2))
        await self.read(current('/system/saves/will/rank',0))

    async def test_closed_allowlist_and_strict_values(self):
        for path,value in [('/system/attributes/ac/value',True),('/system/perception/vision',0),('/system/perception/rank',1.0),('/system/perception/rank',5),('/system/movement/speeds/land',None),('/system/movement/speeds/fly/type','land'),('/system/movement/speeds/fly/value',None),('/system/skills/arcana/value',12),('/system/attributes/ac/private',1),('/system/attributes/hp/max',float('inf'))]:
            with self.subTest(path=path,value=value),self.assertRaises(ToolError):await self.read(current(path,value))
        for actor_type in ('npc','familiar'):
            with self.assertRaises(ToolError):await self.read(current('/system/abilities/str/base',2,actor_type=actor_type))
        with self.assertRaises(ToolError):await self.read(current(actor_type='familiar'))

    async def test_forged_provenance_concepts_and_sections_rejected(self):
        mutations=[lambda p:p['records'][0]['raw'][0].update(basis='source'),lambda p:p['records'][0]['raw'][0].update(document_uuid='Actor.other'),lambda p:p['records'][0]['mapped'].update(concept='armor_class'),lambda p:p['records'][0]['mapped'].update(value=True),lambda p:p['records'][0]['provenance'].update(mapping='pf2e.npc.source.v1'),lambda p:p['records'][0]['provenance'].update(limitations=[]),lambda p:p['records'][0]['provenance'].update(extra=True),lambda p:p['records'][0].update(text={}),lambda p:p['sections'][0].update(status='complete'),lambda p:p['sections'][0].update(reasons=['unrecognized'])]
        for mutate in mutations:
            page=current();mutate(page)
            with self.assertRaises(ToolError):await self.read(page)
        page=current('/system/perception/rank',1);page['records'][0]['mapped']['value']['rank']=True
        with self.assertRaises(ToolError):await self.read(page)
        page=current(present=False);page['sections'][0]['reasons']=['other_statistics_pending']
        with self.assertRaises(ToolError):await self.read(page)
        page=current();page['sections'][0]['name']='source';page['records'][0]['section']='source'
        with self.assertRaises(ToolError):await self.read(page)

    async def test_actual_helper_and_paginated_reader_separate_source(self):
        script=r"""
import {readActor} from './foundry-module/scripts/actors.js';
const source={name:'Current NPC',type:'npc',system:{attributes:{ac:{value:10},hp:{value:4,max:4,temp:0}}}};
const transformed={name:source.name,type:'npc',system:{attributes:{ac:{value:25,breakdown:'trace',details:'exception'},hp:{value:40,max:50,temp:2}},perception:{value:9,totalModifier:9,breakdown:'trace',vision:true},movement:{speeds:{land:{value:25,base:25,type:'land',source:null},burrow:null,climb:null,fly:null,swim:null,travel:{value:20,base:20,type:'travel',source:'travel'}}}}};
const actor={id:'a',uuid:'Actor.a',name:source.name,type:'npc',documentName:'Actor',folder:null,compendium:null,items:new Map(),testUserPermission:()=>true,toObject:(basis=true)=>structuredClone(basis?source:transformed)};
globalThis.game={version:'14.369',system:{id:'pf2e',version:'8.6.1'},ready:true,user:{isGM:true},items:new Map(),actors:new Map([['a',actor]])};globalThis.foundry={utils:{fromUuid:async()=>actor}};
const pages=[];let cursor=null;do{const page=await readActor({actor_uuid:'Actor.a',sections:['source','statistics'],limit:5,...(cursor?{cursor}:{})});pages.push(page);cursor=page.pagination.next_cursor;}while(cursor);console.log(JSON.stringify(pages));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(process.returncode,0,process.stderr)
        pages=json.loads(process.stdout)
        for page in pages:await self.read(page)
        self.assertGreater(len(pages),2)
        rows=[row for page in pages for row in page['records']]
        ac=[row for row in rows if row['raw'] and row['raw'][0]['path']=='/system/attributes/ac/value']
        self.assertEqual({(row['raw'][0]['basis'],row['raw'][0]['value']) for row in ac},{('source',10),('transformed',25)})
        rank=next(row for row in rows if row['key']=='statistics:/system/perception/rank')
        self.assertFalse(rank['raw'][0]['present'])
        self.assertIsNone(rank['mapped']['value'])

    async def test_familiar_requires_exact_pending_master_diagnostic(self):
        page=current(actor_type='familiar');page['records']=[]
        page['pagination']['returned']=0
        page['sections'][0].update(status='unsupported',reasons=['master_current_contract_pending'])
        await self.read(page)
        for reasons in ([],['arbitrary'],['master_current_contract_pending','pagination']):
            page['sections'][0]['reasons']=reasons
            with self.subTest(reasons=reasons),self.assertRaises(ToolError):await self.read(page)

    async def test_movement_missing_or_null_parent_rejects_present_descendant(self):
        for mode in ('burrow','climb','fly','swim'):
            for present in (False,True):
                path='/system/movement/speeds/'+mode
                page=current(path,None,present=present)
                page['records'].extend(current(path+'/value',20)['records'])
                page['pagination']['returned']=2
                with self.subTest(mode=mode,present=present),self.assertRaises(ToolError):await self.read(page)
