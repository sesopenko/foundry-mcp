"""PF2e-specific8.6.1 actor casting source joins; no castability inference."""
import copy
import json
import subprocess
from pathlib import Path
import unittest
from unittest.mock import AsyncMock
from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_actor, CASTING_LIMIT, _record
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_action import response
from test_actor_spellcasting_entry import entry


def casting(row=None):
    page=response(section='spellcasting')
    page['identity'].update(document_name='Actor',uuid='Actor.a',type='npc')
    page['sections']=[dict(name='spellcasting',status='partial',reasons=['availability_not_evaluated'])]
    if row is None:
        raw=dict(document_uuid='Actor.a',path='/system/resources/focus/value',present=True,value=0,basis='source')
        row=dict(key='spellcasting:focus:value',section='spellcasting',kind='field',raw=[raw],mapped=dict(concept='casting_focus_value',value=0,unit=None),provenance=dict(mapping='pf2e.actor.casting-source.v1',limitations=CASTING_LIMIT.copy(),contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}]))
    page['records']=[row]
    return page


def field():
    row=entry()['records'][0];uuid='Actor.a.Item.entry';path=row['raw'][0]['path']
    row.update(section='spellcasting',key='spellcasting:source:'+uuid+':'+path)
    row['raw'][0]['document_uuid']=uuid;row['provenance']['contributors'][0]['document_uuid']=uuid
    return row


def assignment(status='resolved'):
    row=casting()['records'][0]
    raw=dict(document_uuid='Actor.a.Item.spell',path='/system/location/value',present=True,value='entry',basis='source')
    value=dict(status=status,target_uuid=None)
    if status=='resolved':value.update(target_uuid='Actor.a.Item.entry',type='spellcastingEntry',name='Entry',name_truncated=False)
    row.update(key='spellcasting:assignment:Actor.a.Item.spell',kind='relationship',raw=[raw],mapped=dict(concept='casting_spell_assignment',value=value,unit=None))
    row['provenance']['contributors']=[{k:raw[k] for k in ('document_uuid','path','basis')}]
    return row


class ActorCastingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,page):
        self.manager.call.return_value=page
        return await read_actor.fn(actor_uuid='Actor.a',sections=['spellcasting'])

    async def test_source_fields_focus_and_explicit_unresolved_states(self):
        await self.read(casting());await self.read(casting(field()))
        for status in ('resolved','missing','denied','unsupported','unverified','mismatched_assignment'):
            await self.read(casting(assignment(status)))
        page=casting();r=page['records'][0];r['raw'][0].pop('value');r['raw'][0]['present']=False;r['mapped']['value']=None
        await self.read(page)

    async def test_cross_owner_and_fabricated_metadata_rejected(self):
        changes=[lambda r:r['raw'][0].update(document_uuid='Actor.other.Item.spell'),lambda r:r['mapped']['value'].update(target_uuid='Actor.other.Item.entry'),lambda r:r['mapped']['value'].update(target_uuid='Actor.a.Item.wrong'),lambda r:r['mapped']['value'].update(token_uuid='Scene.bad.Token.bad'),lambda r:r['provenance'].update(limitations=[]),lambda r:r['raw'][0].update(path='/flags/private'),lambda r:r['mapped']['value'].update(available=True),lambda r:r['mapped']['value'].update(status='loaded'),lambda r:r.update(key='generated:spell')]
        for mutate in changes:
            page=casting(assignment());mutate(page['records'][0])
            with self.assertRaises(ToolError):await self.read(page)
        bad=assignment('denied');bad['mapped']['value']['name']='Secret'
        with self.assertRaises(ToolError):await self.read(casting(bad))
        bad=field();bad['mapped']['value']='spontaneous'
        with self.assertRaises(ToolError):await self.read(casting(bad))

    async def test_character_derived_focus_max_and_unknown_sources_rejected(self):
        page=casting();page['identity']['type']='character';r=page['records'][0];r['key']='spellcasting:focus:max';r['raw'][0]['path']='/system/resources/focus/max';r['provenance']['contributors'][0]['path']=r['raw'][0]['path'];r['mapped']['concept']='casting_focus_max'
        with self.assertRaises(ToolError):await self.read(page)
        await self.read(casting())
        page=casting();page['records'][0]['raw'][0]['value']=True
        with self.assertRaises(ToolError):await self.read(page)

    async def test_actual_javascript_records_cross_strict_boundary(self):
        script=r"""
import {actorCastingRecords} from './foundry-module/scripts/actorCasting.js';
globalThis.game={user:{isGM:true}};
const results=[];
for(const type of ['character','npc','familiar']){
 const actor={documentName:'Actor',id:'a',uuid:'Actor.a',name:'Actor',type,items:new Map(),testUserPermission:()=>true,toObject:()=>({type,system:{resources:{focus:{value:0,max:3}}}})};
 const add=(id,type,system)=>{const source={name:id,type,system};const item={id,uuid:actor.uuid+'.Item.'+id,documentName:'Item',type,name:id,parent:actor,testUserPermission:()=>true,toObject:()=>structuredClone(source)};actor.items.set(id,item);return source;};
 add('entry','spellcastingEntry',{prepared:{value:'prepared'},slots:{slot1:{value:0,max:3,prepared:[{id:'spell',expended:false},{id:'spell',expended:true},{id:'missing',expended:false}]},slot2:{prepared:{0:{id:'legacy'}}}}});
 add('spell','spell',{level:{value:1},traits:{value:['cantrip']},location:{value:'entry',signature:true,heightenedLevel:4,autoHeightenLevel:5,uses:{value:0,max:2}}});
 add('empty','spell',{});
 results.push({type,...actorCastingRecords({document:actor})});
}
console.log(JSON.stringify(results));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(process.returncode,0,process.stderr)
        results=json.loads(process.stdout)
        for result in results:
            identity=casting()['identity'];identity['type']=result['type']
            self.assertIn('malformed_preparations',result['reasons'])
            self.assertGreater(len(result['records']),60)
            for row in result['records']:
                with self.subTest(type=result['type'],key=row['key']):self.assertTrue(_record(row,['spellcasting'],identity),row)

    async def test_token_context_and_denied_marker_are_strict(self):
        identity=casting()['identity'];identity.update(uuid='Scene.s.Token.t.Actor.a',instance=dict(token_uuid='Scene.s.Token.t'))
        row=assignment();row['key']=row['key'].replace('Actor.a','Scene.s.Token.t.Actor.a')
        row['raw'][0]['document_uuid']='Scene.s.Token.t.Actor.a.Item.spell'
        row['provenance']['contributors'][0]['document_uuid']=row['raw'][0]['document_uuid']
        row['mapped']['value'].update(target_uuid='Scene.s.Token.t.Actor.a.Item.entry',token_uuid='Scene.s.Token.t')
        self.assertTrue(_record(row,['spellcasting'],identity))
        for token in (None,'Scene.other.Token.t'):
            bad=copy.deepcopy(row)
            if token is None:bad['mapped']['value'].pop('token_uuid')
            else:bad['mapped']['value']['token_uuid']=token
            self.assertFalse(_record(bad,['spellcasting'],identity))
        denied=assignment('denied');denied.update(key='spellcasting:denied',raw=[]);denied['mapped']['concept']='casting_item';denied['provenance']['contributors']=[]
        await self.read(casting(denied))
        denied['mapped']['value']['target_uuid']='Actor.a.Item.secret'
        with self.assertRaises(ToolError):await self.read(casting(denied))

    async def test_noncanonical_identities_and_empty_unresolved_claims_rejected(self):
        for suffix in ('bad id','bad\tid','bad#id','nested.Item.id','x'*513):
            row=assignment();raw=row['raw'][0]
            uuid='Actor.a.Item.'+suffix
            row['key']='spellcasting:assignment:'+uuid
            raw['document_uuid']=uuid
            row['provenance']['contributors'][0]['document_uuid']=uuid
            with self.subTest(suffix=suffix),self.assertRaises(ToolError):await self.read(casting(row))
        row=assignment();row['mapped']['value']['name']='x'*257
        with self.assertRaises(ToolError):await self.read(casting(row))
        for present,value in ((True,None),(True,''),(False,None)):
            for status in ('resolved','denied','unsupported','unverified','mismatched_assignment'):
                row=assignment(status);raw=row['raw'][0];raw['present']=present
                if present:raw['value']=value
                else:raw.pop('value')
                with self.subTest(present=present,value=value,status=status),self.assertRaises(ToolError):await self.read(casting(row))
            row=assignment('missing');raw=row['raw'][0];raw['present']=present
            if present:raw['value']=value
            else:raw.pop('value')
            await self.read(casting(row))

    async def test_section_never_claims_complete_castability(self):
        for status,reasons in [('complete',['availability_not_evaluated']),('unsupported',['availability_not_evaluated']),('partial',[])]:
            page=casting();page['sections'][0].update(status=status,reasons=reasons)
            with self.subTest(status=status,reasons=reasons),self.assertRaises(ToolError):await self.read(page)
        await self.read(casting())
