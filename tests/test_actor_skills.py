"""PF2e-specific8.6.1 current skill primitives and owner-local Lore evidence."""
import copy
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import AsyncMock
from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_actor
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_casting import casting


SCRIPT=r"""
import {actorSkillsSnapshot} from './foundry-module/scripts/actorSkills.js';
const results=[];globalThis.game={user:{isGM:true}};
for(const type of ['character','npc']){
 const skill={slug:'lore',label:'Duplicate',attribute:'int',value:12,totalModifier:13,dc:24,breakdown:'Explanation',lore:true,itemId:'one',rank:2,armor:true,base:10,mod:14,visible:false};
 const current={type,system:{skills:{'A/B~ Lore':skill,another:{...skill,itemId:'two'}}}};
 const actor={documentName:'Actor',uuid:'Actor.a',id:'a',name:'Actor',type,items:new Map(),testUserPermission:()=>true,toObject:()=>current};
 for(const id of ['one','two'])actor.items.set(id,{documentName:'Item',uuid:`Actor.a.Item.${id}`,id,name:'Duplicate',type:'lore',parent:actor,folder:null,compendium:null,testUserPermission:()=>true});
 results.push({type,...actorSkillsSnapshot({document:actor,token:null})});
}
console.log(JSON.stringify(results));
"""


def javascript(script):
    result=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
    if result.returncode:raise AssertionError(result.stderr)
    return json.loads(result.stdout)


class ActorSkillsTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):cls.results=javascript(SCRIPT)

    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    def page(self,rows=None,actor_type='character'):
        result=copy.deepcopy(self.results[0 if actor_type=='character' else 1])
        page=casting(result['records'][0]);page['identity']['type']=actor_type
        page['sections']=[dict(name='skills',status='partial',reasons=result['reasons'])]
        page['records']=copy.deepcopy(result['records'] if rows is None else rows);page['pagination']['returned']=len(page['records'])
        return page

    async def read(self,page,**selectors):
        self.manager.call.return_value=page
        return await read_actor.fn(sections=['skills'],limit=100,**(selectors or dict(actor_uuid='Actor.a')))

    async def test_actual_helper_fields_ranks_and_distinct_duplicate_lore(self):
        for typ in ('character','npc'):await self.read(self.page(actor_type=typ))
        rows=self.results[0]['records'];links=[r for r in rows if r['provenance']['mapping']=='pf2e.actor.skills-lore.v1']
        self.assertEqual({r['mapped']['value']['target_uuid'] for r in links},{'Actor.a.Item.one','Actor.a.Item.two'})
        self.assertEqual(links[0]['key'],'skills:current-lore:A~1B~0 Lore')
        rank=next(r for r in rows if r['mapped']['concept']=='current_skill_rank')
        self.assertEqual(rank['mapped']['value'],dict(rank=2,label='Expert'))

    async def test_forged_paths_types_provenance_ranks_and_cross_owner_rejected(self):
        original=next(r for r in self.results[0]['records'] if r['mapped']['concept']=='current_skill_value')
        changes=[lambda r:r['raw'][0].update(value=True),lambda r:r['raw'][0].update(document_uuid='Actor.other'),lambda r:r['raw'][0].update(basis='source'),lambda r:r['provenance'].update(limitations=[]),lambda r:r['mapped'].update(concept='available_skill'),lambda r:r['mapped'].update(value=False),lambda r:r['raw'][0].update(path='/system/skills/A~2B/value'),lambda r:r.update(key='generated:skill')]
        for change in changes:
            row=copy.deepcopy(original);change(row)
            with self.subTest(row=row),self.assertRaises(ToolError):await self.read(self.page([row]))
        for actor_type in ('npc','familiar'):
            rank=next(r for r in self.results[0]['records'] if r['mapped']['concept']=='current_skill_rank')
            with self.assertRaises(ToolError):await self.read(self.page([rank],actor_type=actor_type))
        for rank in (True,1.0,5,-1):
            row=copy.deepcopy(next(r for r in self.results[0]['records'] if r['mapped']['concept']=='current_skill_rank'))
            row['raw'][0]['value']=rank;row['mapped']['value']=dict(rank=rank,label='Expert')
            with self.subTest(rank=rank),self.assertRaises(ToolError):await self.read(self.page([row]))

    async def test_lore_identity_and_same_page_claims_are_exact(self):
        original=next(r for r in self.results[0]['records'] if r['provenance']['mapping']=='pf2e.actor.skills-lore.v1')
        changes=[lambda r:r['mapped']['value'].update(target_uuid='Actor.other.Item.one'),lambda r:r['mapped']['value'].update(type='effect'),lambda r:r['mapped']['value'].update(token_uuid='Scene.s.Token.t'),lambda r:r['mapped']['value'].update(name_truncated=0),lambda r:r['mapped']['value'].update(status='denied'),lambda r:r['raw'][0].update(value=False)]
        for change in changes:
            row=copy.deepcopy(original);change(row)
            with self.assertRaises(ToolError):await self.read(self.page([row]))
        field=copy.deepcopy(next(r for r in self.results[0]['records'] if r['key']=='skills:current:/system/skills/A~1B~0 Lore/itemId'))
        field['raw'][0]['value']='two';field['mapped']['value']='two'
        with self.assertRaises(ToolError):await self.read(self.page([original,field]))
        await self.read(self.page([original]))

    async def test_missing_collection_denial_and_required_diagnostics(self):
        row=copy.deepcopy(self.results[0]['records'][0]);raw=row['raw'][0]
        raw.update(path='/system/skills',present=True,value={});row['key']='skills:current:/system/skills';row['mapped']=dict(concept='current_skill_collection',value=None,unit=None)
        row['provenance']['contributors'][0]['path']='/system/skills'
        await self.read(self.page([row]))
        missing=copy.deepcopy(row);missing['raw'][0].update(present=False);missing['raw'][0].pop('value')
        with self.assertRaises(ToolError):await self.read(self.page([missing]))
        page=self.page([missing]);page['sections'][0]['reasons'].append('current_skill_fields_unavailable');await self.read(page)
        with self.assertRaises(ToolError):await self.read(self.page([row,self.results[0]['records'][0]]))
        denied=copy.deepcopy(row);denied.update(key='skills:current:denied',kind='relationship',raw=[],mapped=dict(concept='current_skill_item_reference',value=dict(status='denied',target_uuid=None),unit=None));denied['provenance']['contributors']=[]
        with self.assertRaises(ToolError):await self.read(self.page([denied]))
        page=self.page([denied]);page['sections'][0]['reasons'].append('current_skill_items_denied');await self.read(page)
        denied['mapped']['value']['name']='Secret'
        with self.assertRaises(ToolError):await self.read(self.page([denied]))
        page=self.page(actor_type='npc');page['sections'][0]['reasons'].remove('conditional_skill_variants_not_evaluated')
        with self.assertRaises(ToolError):await self.read(page)

    async def test_token_lore_preserves_selected_owner_and_token(self):
        row=copy.deepcopy(next(r for r in self.results[0]['records'] if r['provenance']['mapping']=='pf2e.actor.skills-lore.v1'));page=self.page([row]);prefix='Scene.s.Token.t.Actor.a'
        page['identity'].update(uuid=prefix,source_kind='token',instance=dict(scene_uuid='Scene.s',scene_name='Scene',token_uuid='Scene.s.Token.t',token_name='Token',actor_link=False,base_actor=dict(uuid='Actor.a',name='Base')))
        row=page['records'][0]
        for raw in row['raw']:raw['document_uuid']=prefix
        row['provenance']['contributors']=[{k:r[k] for k in ('document_uuid','path','basis')} for r in row['raw']]
        row['mapped']['value'].update(target_uuid=prefix+'.Item.one',token_uuid='Scene.s.Token.t')
        await self.read(page,token_uuid='Scene.s.Token.t')
        row['mapped']['value']['token_uuid']='Scene.other.Token.t'
        with self.assertRaises(ToolError):await self.read(page,token_uuid='Scene.s.Token.t')

    async def test_actual_paginated_reader_retains_source_lore_and_familiar_boundary(self):
        script=r"""
import {readActor} from './foundry-module/scripts/actors.js';
const results=[];
for(const type of ['character','npc','familiar']){
 const skill={slug:'lore',label:'Displayed Lore',attribute:'int',value:12,totalModifier:13,dc:24,breakdown:'Explanation',lore:true,itemId:'one',rank:2,armor:true,base:10,mod:14,visible:false};
 const source={type,name:'Actor',system:{}},current={type,system:{skills:{'A/B~ Lore':skill,SECRET_KEY:{lore:true,itemId:'hidden'}}}};
 const actor={documentName:'Actor',uuid:'Actor.a',id:'a',type,name:'Actor',items:new Map(),parent:null,compendium:null,folder:null,testUserPermission:()=>true,toObject(flag){if(type==='familiar'&&!flag)throw Error('familiar current serialized');return structuredClone(flag?source:current);}};
 for(const id of ['one','two','hidden'])actor.items.set(id,{documentName:'Item',uuid:`Actor.a.Item.${id}`,id,name:id==='hidden'?'SECRET_NAME':'Duplicate',type:'lore',parent:actor,compendium:null,folder:null,testUserPermission:()=>id!=='hidden',toObject(){if(id==='hidden')throw Error('denied source');return {type:'lore',name:'Duplicate',system:{}};}});
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map([['a',actor]]),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>uuid===actor.uuid?actor:null}};
 const pages=[];let cursor;do{const page=await readActor({actor_uuid:actor.uuid,sections:['skills'],limit:5,...(cursor?{cursor}:{})});pages.push(page);cursor=page.pagination.next_cursor;}while(cursor);results.push({type,pages});
}
console.log(JSON.stringify(results));
"""
        results=javascript(script)
        for result in results:
            rows=[]
            for page in result['pages']:rows.extend((await self.read(page))['records'])
            self.assertNotIn('SECRET',json.dumps(rows))
            source=[r for r in rows if r['provenance']['mapping']=='pf2e.lore.specialty.v1' and r['key']!='skills:lore:denied']
            self.assertEqual(len(source),2)
            current=[r for r in rows if r['provenance']['mapping']=='pf2e.actor.skills-current.v1']
            if result['type']=='familiar':self.assertEqual(current,[])
            else:
                self.assertGreater(len(result['pages']),1)
                self.assertTrue(current)
                self.assertEqual(len([r for r in rows if r['provenance']['mapping']=='pf2e.actor.skills-lore.v1']),1)
