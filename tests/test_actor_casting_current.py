"""PF2e-specific8.6.1 transformed casting resource boundary checks."""
import copy
import json
import subprocess
from pathlib import Path
import unittest
from unittest.mock import AsyncMock
from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_actor, _record, CASTING_LIMIT
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_casting import casting


def current(path='/system/resources/focus/value', value=0, uuid='Actor.a', present=True):
    concept={'value':'current_focus_points','max':'current_focus_pool_maximum','cap':'current_focus_pool_cap','focusPoints':'current_spell_focus_point_cost'}[path.rsplit('/',1)[1]]
    raw=dict(document_uuid=uuid,path=path,present=present,basis='transformed')
    if present:raw['value']=value
    return dict(key='spellcasting:current:'+uuid+':'+path,section='spellcasting',kind='field',raw=[raw],mapped=dict(concept=concept,value=value if present else None,unit=None),provenance=dict(mapping='pf2e.actor.casting-current.v1',limitations=['casting_availability_not_evaluated'],contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}]))


class ActorCastingCurrentTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,row,actor_type='npc',missing=False):
        page=casting(row);page['identity']['type']=actor_type
        if missing:page['sections'][0]['reasons'].append('current_fields_unavailable')
        self.manager.call.return_value=page
        return await read_actor.fn(actor_uuid='Actor.a',sections=['spellcasting'])

    async def test_actor_numbers_and_spell_integer_contract(self):
        for actor_type in ('character','npc'):
            for leaf in ('value','max','cap'):
                for value in (0,-1,2.5):
                    await self.read(current('/system/resources/focus/'+leaf,value),actor_type)
            for value in range(4):await self.read(current('/system/cast/focusPoints',value,'Actor.a.Item.spell'),actor_type)
        for value in (True,None,'0',float('inf'),float('nan')):
            with self.subTest(value=value),self.assertRaises(ToolError):await self.read(current(value=value))
        for value in (True,-1,4,1.5,1.0):
            with self.subTest(value=value),self.assertRaises(ToolError):await self.read(current('/system/cast/focusPoints',value,'Actor.a.Item.spell'))

    async def test_missing_is_null_with_required_partial_reason(self):
        row=current(present=False)
        await self.read(row,missing=True)
        with self.assertRaises(ToolError):await self.read(row)
        row['mapped']['value']=0
        with self.assertRaises(ToolError):await self.read(row,missing=True)

    async def test_same_page_item_type_witness_must_match_spell(self):
        page=casting(current('/system/cast/focusPoints',1,'Actor.a.Item.entry'))
        raw=[dict(document_uuid='Actor.a.Item.entry',path=path,present=True,value=value,basis='source') for path,value in [('/name','Entry'),('/type','spellcastingEntry')]]
        page['records'].append(dict(key='spellcasting:entry:Actor.a.Item.entry',section='spellcasting',kind='relationship',raw=raw,mapped=dict(concept='casting_entry',value=dict(status='resolved',target_uuid='Actor.a.Item.entry',type='spellcastingEntry',name='Entry',name_truncated=False),unit=None),provenance=dict(mapping='pf2e.actor.casting-source.v1',limitations=['stored_configuration_not_current_castability'],contributors=[{k:r[k] for k in ('document_uuid','path','basis')} for r in raw])))
        page['records'][1]['provenance']['limitations']=CASTING_LIMIT.copy()
        self.assertTrue(_record(page['records'][1],['spellcasting'],page['identity']))
        page['pagination']['returned']=2
        self.manager.call.return_value=page
        with self.assertRaises(ToolError):await read_actor.fn(actor_uuid='Actor.a',sections=['spellcasting'])

    async def test_strict_paths_owner_provenance_and_availability(self):
        mutations=[lambda r:r['raw'][0].update(basis='source'),lambda r:r['raw'][0].update(document_uuid='Actor.other'),lambda r:r['raw'][0].update(path='/system/resources/focus/private'),lambda r:r['provenance'].update(limitations=[]),lambda r:r['provenance']['contributors'][0].update(basis='source'),lambda r:r['mapped'].update(available=True),lambda r:r['mapped'].update(value=False),lambda r:r.update(kind='relationship'),lambda r:r.update(key='generated:focus')]
        for mutate in mutations:
            row=current();mutate(row)
            with self.subTest(row=row),self.assertRaises(ToolError):await self.read(row)
        for row in (current('/system/cast/focusPoints',1,'Actor.other.Item.spell'),current('/system/cast/focusPoints',1,'Actor.a'),current(uuid='Actor.a.Item.spell')):
            with self.assertRaises(ToolError):await self.read(row)
        with self.assertRaises(ToolError):await self.read(current(),'familiar')

    def test_token_uuid_context_preserved_without_fabricated_metadata(self):
        identity=casting()['identity'];identity.update(uuid='Scene.s.Token.t.Actor.a',instance=dict(token_uuid='Scene.s.Token.t'))
        row=current('/system/cast/focusPoints',0,identity['uuid']+'.Item.spell')
        self.assertTrue(_record(row,['spellcasting'],identity))
        bad=copy.deepcopy(row);bad['raw'][0]['document_uuid']='Actor.a.Item.spell'
        self.assertFalse(_record(bad,['spellcasting'],identity))

    async def test_actual_paginated_javascript_reader_dto(self):
        script=r"""
import {readActor} from './foundry-module/scripts/actors.js';
const actor={documentName:'Actor',uuid:'Actor.a',id:'a',name:'Caster',type:'character',items:new Map(),folder:null,compendium:null,testUserPermission:()=>true,toObject:flag=>({type:'character',name:'Caster',system:{resources:{focus:flag?{value:1}:{value:0,max:2.5,cap:3}}}})};
const spell={documentName:'Item',uuid:'Actor.a.Item.s',id:'s',name:'Spell',type:'spell',parent:actor,folder:null,compendium:null,testUserPermission:()=>true,toObject:flag=>flag?{type:'spell',name:'Spell',system:{level:{value:1},traits:{value:[]},location:{value:null}}}:{type:'spell',system:{cast:{focusPoints:0}}}};
actor.items.set(spell.id,spell);
globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map([['a',actor]]),items:new Map()};
globalThis.foundry={utils:{fromUuid:async uuid=>uuid===actor.uuid?actor:uuid===spell.uuid?spell:null}};
const pages=[];let cursor;
do{const page=await readActor({actor_uuid:actor.uuid,sections:['spellcasting'],limit:5,...(cursor?{cursor}:{})});pages.push(page);cursor=page.pagination.next_cursor;}while(cursor);
console.log(JSON.stringify(pages));
"""
        result=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(result.returncode,0,result.stderr)
        pages=json.loads(result.stdout);self.assertGreater(len(pages),1)
        rows=[]
        for page in pages:
            self.manager.call.return_value=page
            validated=await read_actor.fn(actor_uuid='Actor.a',sections=['spellcasting'],limit=5)
            rows.extend(validated['records'])
        current_rows=[r for r in rows if r['provenance']['mapping']=='pf2e.actor.casting-current.v1']
        self.assertEqual(len(current_rows),4)
        self.assertEqual(next(r['mapped']['value'] for r in current_rows if r['mapped']['concept']=='current_focus_pool_maximum'),2.5)
