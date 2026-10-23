"""PF2e-specific character8.6.1 strict selected-source and biography boundary."""
import copy
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_actor, _character_spec, _character_note_spec, CHARACTER_LIMIT, LORE_RANKS
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_action import response


def character(path, value, present=True, section='source'):
    page=response(path,value,present=present,section=section)
    page['identity'].update(document_name='Actor',uuid='Actor.a',type='character')
    row=page['records'][0];raw=row['raw'][0];raw['document_uuid']='Actor.a'
    spec=_character_spec(path)
    concept=spec[0] if spec else 'unknown'
    mapped=value if present else None
    limits=spec[3] if spec else CHARACTER_LIMIT
    if section=='description':
        note=_character_note_spec(path);concept=note[0] if note else 'unknown'
        mapped=[] if value==[] and present else None
    elif spec and spec[1]=='rank' and type(value) is int and 0<=value<=4 and present:
        mapped=dict(rank=value,label=LORE_RANKS[value])
    row.update(key=section+':'+path,mapped=dict(concept=concept,value=mapped,unit=None))
    row['provenance'].update(mapping='pf2e.character.'+('notes' if section=='description' else 'source')+'.v1',limitations=list(limits),contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}])
    if section=='description' and present and type(value) is str:
        row.update(kind='text',key=row['key']+':0',text=dict(path=path,start=0,end=len(value.encode('utf-16-le'))//2,total=len(value.encode('utf-16-le'))//2,complete=True))
    return page


class CharacterBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,page):
        self.manager.call.return_value=page
        return await read_actor.fn(actor_uuid='Actor.a',sections=[s['name'] for s in page['sections']])

    async def test_source_null_omissions_ranks_codes_and_empty_choices(self):
        for path,value in [('/system/abilities',None),('/system/abilities/str/mod',-2.5),('/system/details/level/value',1),('/system/details/age/value','unknown'),('/system/details/keyability/value','unrecognized'),('/system/details/languages/value',[]),('/system/details/languages/value/0','custom'),('/system/details/xp/max',1000),('/system/details/biography/visibility/appearance',False),('/system/attributes/hp/value',0),('/system/attributes/hp/sp/value',0),('/system/skills',{}),('/system/skills/a~1~0/rank',4),('/system/skills//rank',0),('/system/resources/heroPoints/max',3),('/system/resources/focus/value',0),('/system/resources/crafting/infusedReagents/value',2),('/system/resources/resolve/value',0),('/system/build/attributes/manual',False),('/system/build/attributes/boosts/5',[]),('/system/build/attributes/boosts/20/0','unknown'),('/system/build/attributes/apex',None)]:
            with self.subTest(path=path):await self.read(character(path,value))
        for path in ('/system/abilities','/system/abilities/dex/mod','/system/skills','/system/skills/arcana/rank','/system/build/attributes/apex'):
            await self.read(character(path,None,False))

    async def test_description_fragments_and_array_markers_opt_in(self):
        for path,value in [('/system/details/languages/details','exact language exception'),('/system/details/biography/backstory','<p>Exact 😀</p>'),('/system/details/biography/edicts',[]),('/system/details/biography/anathema/0','Exact edict')]:
            with self.subTest(path=path):await self.read(character(path,value,section='description'))
        await self.read(character('/system/details/biography/edicts',None,False,'description'))
        with self.assertRaises(ToolError):await self.read(character('/system/details/biography/backstory','private prose'))
        for section in ('source','description'):
            with self.subTest(section=section),self.assertRaises(ToolError):
                await self.read(character('/system/description/value','unsupported generic actor prose',section=section))

    async def test_prepared_paths_malformed_types_and_rank_labels_rejected(self):
        for path,value in [('/system/abilities',{}),('/system/abilities/str/mod',None),('/system/abilities/str/mod',True),('/system/details/level/value',float('inf')),('/system/skills',{'arcana':1}),('/system/skills/arcana/rank',True),('/system/skills/arcana/rank',1.0),('/system/skills/arcana/rank',5),('/system/skills/a~2/rank',1),('/system/skills/arcana/base',2),('/system/skills/arcana/total',12),('/system/details/languages/value',['secret']),('/system/details/languages/value/00','bad'),('/system/attributes/hp/max',20),('/system/resources/focus/max',3),('/system/resources/focus/cap',3),('/system/resources/resolve/max',3),('/system/details/xp/pct',10),('/system/traits/value',[]),('/system/details/publication/title','bad'),('/system/build/attributes/boosts/ancestry/0','str'),('/system/build/attributes/allowedBoosts/1',4),('/flags/secret','secret')]:
            with self.subTest(path=path),self.assertRaises(ToolError):await self.read(character(path,value))
        original=character('/system/skills/arcana/rank',1)
        for mutate in [lambda p:p['records'][0]['mapped']['value'].update(label='Master'),lambda p:p['records'][0]['mapped']['value'].update(rank=True),lambda p:p['records'][0]['provenance'].update(limitations=[]),lambda p:p['records'][0]['provenance'].update(mapping='pf2e.npc.source.v1'),lambda p:p['records'][0]['raw'][0].update(document_uuid='Actor.other'),lambda p:p['identity'].update(type='npc')]:
            page=copy.deepcopy(original);mutate(page)
            with self.assertRaises(ToolError):await self.read(page)
        original=character('/system/attributes/hp/value',1)
        original['records'][0]['mapped']['value']=True
        with self.assertRaises(ToolError):await self.read(original)
        original=character('/system/details/biography/backstory','exact',section='description')
        for mutate in [lambda p:p['records'][0]['provenance'].update(limitations=[]),lambda p:p['records'][0]['provenance']['contributors'][0].update(path='/name'),lambda p:p['records'][0]['mapped'].update(value='exact'),lambda p:p['records'][0]['text'].update(end=4)]:
            page=copy.deepcopy(original);mutate(page)
            with self.assertRaises(ToolError):await self.read(page)

    async def test_actual_helper_descriptors_and_paginated_reader(self):
        script=r"""
import {readActor} from './foundry-module/scripts/actors.js';
const source={name:'PC',type:'character',system:{abilities:null,details:{level:{value:2},languages:{value:['common','unknown','common'],details:'Exact languages'},biography:{backstory:'<p>😀 Exact</p>'.repeat(700),edicts:[],anathema:['Exact','Exact']}},skills:{'a/~':{rank:3},arcana:{rank:0}},attributes:{hp:{value:0,temp:2,tempSource:'local',sp:{value:0},max:99}},resources:{heroPoints:{value:1,max:3},focus:{value:0,max:99}},build:{attributes:{manual:false,boosts:{1:['str','unknown','str'],5:[]},apex:null}}}};
const actor={id:'a',uuid:'Actor.a',name:'PC',type:'character',documentName:'Actor',folder:null,compendium:null,items:new Map(),testUserPermission:()=>true,toObject:()=>structuredClone(source)};
globalThis.game={version:'14.369',system:{id:'pf2e',version:'8.6.1'},ready:true,user:{isGM:true},items:new Map(),actors:new Map([['a',actor]])};globalThis.foundry={utils:{fromUuid:async()=>actor}};
const pages=[];let cursor=null;do{const page=await readActor({actor_uuid:'Actor.a',sections:['source','description'],limit:7,...(cursor?{cursor}:{})});pages.push(page);cursor=page.pagination.next_cursor;}while(cursor);console.log(JSON.stringify(pages));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(process.returncode,0,process.stderr)
        pages=json.loads(process.stdout)
        for page in pages:await self.read(page)
        records=[row for page in pages for row in page['records']]
        self.assertGreater(len(pages),5)
        self.assertTrue(any(row['raw'][0]['path']=='/system/skills/a~1~0/rank' and row['mapped']['value']==dict(rank=3,label='Master') for row in records))
        self.assertFalse(any(row['raw'][0]['path'] in ('/system/attributes/hp/max','/system/resources/focus/max') for row in records))
        fragments=[row for row in records if row['raw'][0]['path']=='/system/details/biography/backstory']
        self.assertGreater(len(fragments),1)
        self.assertEqual(''.join(row['raw'][0]['value'] for row in fragments),'<p>😀 Exact</p>'*700)
