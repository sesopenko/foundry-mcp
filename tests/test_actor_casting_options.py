"""PF2e-specific8.6.1 contextual options preserve exact source evidence."""
import copy
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import AsyncMock
from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import _record, read_actor
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_casting import casting


SCRIPT=r"""
import {actorCastingOptions} from './foundry-module/scripts/actorCastingOptions.js';
const results=[];
for(const mode of ['prepared','spontaneous','innate','focus','items','ritual','unknown','unassigned']){
 const target={uuid:'Actor.a',type:'npc',instance:null},actorSource={type:'npc',system:{resources:{focus:{value:0,max:3}}}};
 const item=(id,type,system)=>({identity:{id,uuid:`Actor.a.Item.${id}`,type,name:id,name_truncated:false,actor:{uuid:'Actor.a'}},source:{name:id,type,system}});
 const entry=item('entry','spellcastingEntry',{prepared:{value:mode,flexible:false},autoHeightenLevel:{value:7},slots:{slot0:{value:0,max:3,prepared:[{id:'spell',expended:false},{id:'spell',expended:true},{id:'spell',expended:'bad'}]},slot11:{prepared:[{id:'spell'}]}}});
 const spell=item('spell','spell',{level:{value:1},location:{value:mode==='unassigned'?null:'entry',heightenedLevel:4,signature:true,autoHeightenLevel:5,uses:{value:0,max:2}},traits:{value:['cantrip']},ritual:mode==='ritual'?{primary:{check:'Arcana'},secondary:{checks:'Occultism',casters:2}}:null});
 const relationships=[{key:'spellcasting:assignment:Actor.a.Item.spell',mapped:{value:{status:'missing',target_uuid:null}}}];
 results.push({mode,...actorCastingOptions(target,mode==='unassigned'?[spell]:[entry,spell],actorSource,relationships)});
}
console.log(JSON.stringify(results));
"""


def javascript(script):
    result=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
    if result.returncode:raise AssertionError(result.stderr)
    return json.loads(result.stdout)


class ActorCastingOptionsTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):cls.results=javascript(SCRIPT)

    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,result):
        page=casting(result['records'][0]);page['records']=copy.deepcopy(result['records'])
        page['sections'][0]['reasons']=result['reasons'].copy();page['pagination']['returned']=len(page['records'])
        self.manager.call.return_value=page
        return await read_actor.fn(actor_uuid='Actor.a',sections=['spellcasting'])

    async def test_actual_helper_modes_repeated_preparations_and_opaque_slot11(self):
        for result in self.results:
            with self.subTest(mode=result['mode']):await self.read(result)
        prepared=self.results[0]
        self.assertEqual([r['mapped']['value']['preparation_index'] for r in prepared['records']],[0,1,2])
        self.assertEqual([r['mapped']['value']['expended'] for r in prepared['records']],[False,True,None])
        self.assertTrue(all(r['mapped']['value']['slot_rank']==0 for r in prepared['records']))
        self.assertIn('template_slot11_no_spell_rank_semantics',prepared['reasons'])

    async def test_forged_values_paths_provenance_and_identity_rejected(self):
        changes=[lambda r:r['mapped']['value'].update(cast_rank=4),lambda r:r['mapped']['value'].update(availability='available'),lambda r:r['mapped']['value'].update(configured_rank=9),lambda r:r['mapped']['value'].update(slot_rank=11),lambda r:r['mapped']['value'].update(preparation_index=1),lambda r:r['mapped']['value'].update(cantrip=False),lambda r:r['mapped']['value'].update(signature=False),lambda r:r['mapped']['value']['entry'].update(target_uuid='Actor.other.Item.entry'),lambda r:r['mapped']['value']['spell'].update(name='Invented'),lambda r:r['mapped']['value'].update(resource_scope='shared_actor_focus'),lambda r:r['raw'][0].update(document_uuid='Actor.other.Item.spell'),lambda r:r['raw'][0].update(basis='transformed'),lambda r:r['provenance'].update(limitations=[]),lambda r:r.update(key='generated:spell'),lambda r:r['raw'].append(dict(document_uuid='Actor.a',path='/flags/private',present=True,value='private',basis='source'))]
        for change in changes:
            result=copy.deepcopy(self.results[0]);result['records']=result['records'][:1];change(result['records'][0])
            with self.subTest(row=result['records'][0]),self.assertRaises(ToolError):await self.read(result)

    async def test_missing_diagnostics_and_false_completeness_rejected(self):
        for reason in ('signature_alternatives_not_evaluated','malformed_preparation'):
            result=copy.deepcopy(self.results[0]);result['reasons'].remove(reason)
            with self.subTest(reason=reason),self.assertRaises(ToolError):await self.read(result)
        result=copy.deepcopy(self.results[-1]);result['records'][0]['mapped']['value']['entry']['status']='denied'
        with self.assertRaises(ToolError):await self.read(result)

    async def test_missing_flags_and_ranks_remain_unknown_without_defaults(self):
        result=copy.deepcopy(self.results[1]);row=result['records'][0]
        for path,key in [('/system/location/signature','signature'),('/system/level/value','base_rank'),('/system/location/heightenedLevel','configured_rank')]:
            field=next(r for r in row['raw'] if r['path']==path);field['present']=False;field.pop('value')
            row['mapped']['value'][key]=None
        await self.read(result)
        field=next(r for r in row['raw'] if r['path']=='/system/location/signature')
        field.update(present=True,value=False);row['mapped']['value']['signature']=False
        await self.read(result)
        for malformed in (True,'1',float('inf')):
            bad=copy.deepcopy(result);field=next(r for r in bad['records'][0]['raw'] if r['path']=='/system/level/value')
            field.update(present=True,value=malformed);bad['records'][0]['mapped']['value']['base_rank']=malformed
            with self.subTest(value=malformed),self.assertRaises(ToolError):await self.read(bad)

    def test_token_identity_and_nested_bool_number_forgery(self):
        row=copy.deepcopy(self.results[2]['records'][0]);identity=casting()['identity'];prefix='Scene.s.Token.t.Actor.a'
        identity.update(uuid=prefix,instance=dict(token_uuid='Scene.s.Token.t'))
        row['key']=row['key'].replace('Actor.a',prefix)
        for field in row['raw']:field['document_uuid']=field['document_uuid'].replace('Actor.a',prefix)
        row['provenance']['contributors']=[{k:r[k] for k in ('document_uuid','path','basis')} for r in row['raw']]
        for label in ('spell','entry'):
            row['mapped']['value'][label]['target_uuid']=row['mapped']['value'][label]['target_uuid'].replace('Actor.a',prefix)
            row['mapped']['value'][label]['token_uuid']='Scene.s.Token.t'
        self.assertTrue(_record(row,['spellcasting'],identity))
        bad=copy.deepcopy(row);bad['mapped']['value']['uses']['value']=False
        self.assertFalse(_record(bad,['spellcasting'],identity))
        bad=copy.deepcopy(row);bad['mapped']['value']['spell'].pop('token_uuid')
        self.assertFalse(_record(bad,['spellcasting'],identity))

    async def test_actual_paginated_read_actor_dto(self):
        script=r"""
import {readActor} from './foundry-module/scripts/actors.js';
const actor={documentName:'Actor',uuid:'Actor.a',id:'a',name:'Caster',type:'npc',items:new Map(),folder:null,compendium:null,testUserPermission:()=>true,toObject:flag=>({type:'npc',name:'Caster',system:{resources:{focus:{value:0,max:3,cap:3}}}})};
const add=(id,type,system)=>{const source={type,name:id,system};const item={documentName:'Item',uuid:`Actor.a.Item.${id}`,id,name:id,type,parent:actor,folder:null,compendium:null,testUserPermission:()=>true,toObject:flag=>flag?structuredClone(source):{type,system:type==='spell'?{cast:{focusPoints:0}}:{}}};actor.items.set(id,item);};
add('entry','spellcastingEntry',{prepared:{value:'prepared'},slots:{slot1:{value:0,max:2,prepared:[{id:'spell',expended:false},{id:'spell',expended:true}]}}});
add('spell','spell',{level:{value:1},traits:{value:[]},location:{value:'entry',signature:true,heightenedLevel:4}});
globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map([['a',actor]]),items:new Map()};
globalThis.foundry={utils:{fromUuid:async uuid=>uuid===actor.uuid?actor:[...actor.items.values()].find(item=>item.uuid===uuid)}};
const pages=[];let cursor;
do{const page=await readActor({actor_uuid:actor.uuid,sections:['spellcasting'],limit:5,...(cursor?{cursor}:{})});pages.push(page);cursor=page.pagination.next_cursor;}while(cursor);
console.log(JSON.stringify(pages));
"""
        pages=javascript(script);self.assertGreater(len(pages),1);options=[]
        for page in pages:
            self.manager.call.return_value=page
            result=await read_actor.fn(actor_uuid='Actor.a',sections=['spellcasting'],limit=5)
            options.extend(r for r in result['records'] if r['provenance']['mapping']=='pf2e.actor.casting-options.v1')
        self.assertEqual(len(options),2)
        self.assertEqual([r['mapped']['value']['expended'] for r in options],[False,True])
        self.assertTrue(all(r['mapped']['value']['cast_rank'] is None for r in options))
