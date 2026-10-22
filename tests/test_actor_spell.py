"""PF2e-specific spell8.6.1 strict source and owner-local assignment boundary."""
import copy
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_item, _spell_spec, SPELL_LIMIT
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_action import response


def spell(path='/system/level/value', value=2, *, present=True):
    result=response(path,value,item_type='spell',present=present)
    row=result['records'][0];spec=_spell_spec(path)
    row.update(key='source:'+path,mapped=dict(concept=spec[0] if spec else 'forged',value=value if present else None,unit=None))
    row['provenance'].update(mapping='pf2e.spell.source.v1',limitations=SPELL_LIMIT.copy())
    return result


def relationship(local_id='entry',status='unverified',*,owned=False):
    result=spell('/system/location/value',local_id);row=result['records'][0]
    result['sections']=[dict(name='relationships',status='complete',reasons=[])]
    row.update(key='relationships:spell:location',section='relationships',kind='relationship',mapped=dict(concept='stored_spellcasting_entry_reference',value=dict(status=status,target_uuid=None),unit=None))
    row['provenance'].update(mapping='pf2e.spell.casting-entry.v1',limitations=['stored_assignment_not_castability'])
    if owned:
        result['identity']['actor']=dict(uuid='Actor.owner',name='Owner',type='npc')
        result['identity']['uuid']='Actor.owner.Item.a'
        row['raw'][0]['document_uuid']='Actor.owner.Item.a';row['provenance']['contributors'][0]['document_uuid']='Actor.owner.Item.a'
    if status == 'resolved':
        row['mapped']['value'].update(target_uuid='Actor.owner.Item.'+local_id,document_name='Item',type='spellcastingEntry',name='Entry',name_truncated=False)
    return result


class ActorSpellTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,result,section='source'):
        self.manager.call.return_value=result
        return await read_item.fn(item_uuid=result['identity']['uuid'],token_uuid=result['identity']['instance']['token_uuid'] if result['identity']['instance'] else None,sections=[section])

    async def test_authored_rank_text_components_and_nested_layers(self):
        values=[('/system/level/value',1),('/system/time/value','1 minute or 2 actions'),('/system/duration/sustained',True),('/system/traits/traditions',[]),('/system/damage',{}),('/system/damage/dmg~1one~0/formula','2d6'),('/system/damage/dmg~1one~0/kinds/0','healing'),('/system/damage/dmg~1one~0/materials',[]),('/system/damage/a/category',None),('/system/defense',None),('/system/defense/passive',None),('/system/defense/save/basic',False),('/system/area',None),('/system/ritual/secondary/casters',2),('/system/location/value',None),('/system/location/uses/value',0),('/system/location/autoHeightenLevel',None),('/system/location/heightenedLevel',5),('/system/heightening/type','interval'),('/system/heightening/damage/a','1d6'),('/system/heightening/levels',{}),('/system/heightening/levels/3/level/value',3),('/system/overlays',{}),('/system/overlays/mode~1one~0/name','Mode'),('/system/overlays/mode/sort',0),('/system/overlays/mode/system/damage/a/formula','4d6'),('/system/overlays/mode/system/heightening/levels/5/range/value','120 feet')]
        for path,value in values:
            with self.subTest(path=path): await self.read(spell(path,value))
        await self.read(spell('/system/area',present=False))
        await self.read(spell('/system/heightening',present=False))

    async def test_forged_shapes_private_paths_and_mapping_rejected(self):
        for path,value in [('/system/cast/focusPoints',1),('/system/statistic',{}),('/system/traits/traditions',['arcane']),('/system/damage/a',{}),('/system/damage/a/formula',None),('/system/damage/a/kinds/00','healing'),('/system/damage/key~2bad/formula','secret'),('/system/heightening/type','unknown'),('/system/heightening/levels/0/level/value',3),('/system/heightening/levels/03/level/value',3),('/system/overlays/a/system/overlays/b/name','bad'),('/system/level/value',True),('/system/location/signature',0),('/system/area',{}),('/system/heightening',{}),('/system/description/value','prose')]:
            with self.subTest(path=path),self.assertRaises(ToolError): await self.read(spell(path,value))
        for change in [lambda r:r['mapped'].update(concept='cast_rank'),lambda r:r['mapped'].update(value=3),lambda r:r['mapped'].update(unit='rank'),lambda r:r['provenance'].update(mapping='pf2e.physical.source.v1'),lambda r:r['provenance'].update(limitations=[]),lambda r:r['raw'][0].update(document_uuid='Item.other'),lambda r:r['provenance']['contributors'][0].update(path='/system/location/value'),lambda r:r.update(key='forged'),lambda r:r.update(kind='relationship')]:
            bad=spell();change(bad['records'][0])
            with self.assertRaises(ToolError): await self.read(bad)
        bad=spell();bad['identity']['type']='equipment'
        with self.assertRaises(ToolError): await self.read(bad)

    async def test_assignment_states_same_owner_and_token_context(self):
        for local,status,owned in [(None,'missing',False),('','missing',False),('entry','unverified',False),('entry','missing',True),('entry','denied',True),('entry','unsupported',True),('entry','resolved',True)]:
            with self.subTest(status=status): await self.read(relationship(local,status,owned=owned),'relationships')
        for bad in [relationship('entry','resolved'),relationship(None,'denied'),relationship('entry','denied'),relationship('entry','missing')]:
            with self.assertRaises(ToolError): await self.read(bad,'relationships')
        for change in [lambda v:v.update(target_uuid='Actor.other.Item.entry'),lambda v:v.update(type='spell'),lambda v:v.update(token_uuid='Scene.s.Token.t'),lambda v:v.update(name_truncated=1),lambda v:v.update(extra='secret')]:
            bad=relationship('entry','resolved',owned=True);change(bad['records'][0]['mapped']['value'])
            with self.assertRaises(ToolError): await self.read(bad,'relationships')
        synthetic=relationship('entry','resolved',owned=True)
        identity=synthetic['identity'];identity.update(source_kind='token',instance=dict(scene_uuid='Scene.s',scene_name='Scene',token_uuid='Scene.s.Token.t',token_name='Token',actor_link=False,base_actor=dict(uuid='Actor.base',name='Base')))
        identity['actor']['uuid']='Scene.s.Token.t.Actor.owner';identity['uuid']='Scene.s.Token.t.Actor.owner.Item.a'
        row=synthetic['records'][0];row['raw'][0]['document_uuid']=identity['uuid'];row['provenance']['contributors'][0]['document_uuid']=identity['uuid'];row['mapped']['value'].update(target_uuid='Scene.s.Token.t.Actor.owner.Item.entry',token_uuid='Scene.s.Token.t')
        await self.read(synthetic,'relationships')
        del row['mapped']['value']['token_uuid']
        with self.assertRaises(ToolError): await self.read(synthetic,'relationships')

    async def test_actual_selector_descriptors_cross_python_boundary(self):
        script=r"""
import {spellFields} from './foundry-module/scripts/actorSpell.js';
const source={type:'spell',system:{level:{value:2},traits:{traditions:['arcane'],value:['custom'],otherTags:[],rarity:'common'},time:{value:'1 minute or 2 actions'},requirements:'Requirement',cost:{value:'Cost'},range:{value:'30 feet'},target:{value:'1 creature'},area:{type:'burst',value:10,details:'Special'},duration:{value:'1 minute',sustained:true},damage:{'key/~':{formula:'2d6',kinds:['damage','healing'],applyMod:false,type:'fire',category:null,materials:[]}},defense:{passive:null,save:{statistic:'reflex',basic:true}},counteraction:false,ritual:{primary:{check:'Arcana'},secondary:{checks:'Occultism',casters:2}},location:{value:'entry',signature:true,heightenedLevel:4,autoHeightenLevel:null,uses:{value:0,max:1}},slug:null,publication:{title:'Book',authors:'Author',license:'ORC',remaster:true},heightening:{type:'fixed',levels:{3:{damage:{'key/~':{formula:'4d6'}}}}},overlays:{'mode/~':{name:'Variant',overlayType:'override',sort:1,system:{heightening:{type:'interval',interval:1,area:5,damage:{'key/~':'1d6'}},location:{value:null}}}}}};
const fields=spellFields(source);fields.push(...spellFields({type:'spell',system:{}}));console.log(JSON.stringify(fields));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(process.returncode,0,process.stderr)
        fields=json.loads(process.stdout);self.assertGreater(len(fields),50)
        for field in fields:
            with self.subTest(path=field['path']):
                result=spell(field['path'],field.get('value'),present=field['present']);row=result['records'][0]
                row['mapped']['concept']=field['concept'];row['provenance']['limitations']=field['limitations']
                await self.read(result)

    async def test_actual_reader_pages_source_relationship_and_exact_nested_prose(self):
        script=r"""
import {readItem} from './foundry-module/scripts/actors.js';
const text='<p>Exact 😀 '+('é😀'.repeat(3500))+'</p>';
const source={name:'Spell',type:'spell',system:{level:{value:1},time:{value:'2 actions or 1 minute'},location:{value:'entry',heightenedLevel:5},damage:{heal:{formula:'1d6',type:'vitality',category:null,kinds:['healing'],materials:[]}},heightening:{type:'fixed',levels:{3:{description:{value:text},range:{},damage:{heal:{formula:'3d6'}}},4:{}}},overlays:{mode:{name:'Mode',overlayType:'override',sort:0,system:{description:{value:'<p>Overlay exact 😀</p>'},traits:{},heightening:{}}}},description:{value:'<p>Root exact 😀</p>'}}};
const owner={id:'owner',uuid:'Actor.owner',name:'Owner',type:'npc',documentName:'Actor',items:new Map(),testUserPermission:()=>true};
const entry={id:'entry',uuid:'Actor.owner.Item.entry',name:'Entry',type:'spellcastingEntry',documentName:'Item',parent:owner,testUserPermission:()=>true,toObject:()=>{throw Error('Target source must stay unread');}};
const item={id:'a',uuid:'Actor.owner.Item.a',name:source.name,type:'spell',documentName:'Item',parent:owner,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};owner.items.set('entry',entry);owner.items.set('a',item);
globalThis.game={version:'14.369',system:{id:'pf2e',version:'8.6.1'},ready:true,user:{isGM:true},actors:new Map([['owner',owner]]),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>uuid===item.uuid?item:uuid===owner.uuid?owner:entry}};
let cursor;const pages=[];do{const page=await readItem({item_uuid:item.uuid,sections:['source','relationships','description'],limit:4,max_bytes:12000,...(cursor?{cursor}:{})});pages.push(page);cursor=page.pagination.next_cursor;}while(cursor);console.log(JSON.stringify({pages,text}));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(process.returncode,0,process.stderr)
        payload=json.loads(process.stdout);records=[]
        self.assertGreater(len(payload['pages']),3)
        for page in payload['pages']:
            self.manager.call.return_value=page
            checked=await read_item.fn(item_uuid='Actor.owner.Item.a',sections=['source','relationships','description'],limit=4,max_bytes=12000)
            records.extend(checked['records'])
        source=[r for r in records if r['section']=='source'];paths=[r['raw'][0]['path'] for r in source]
        self.assertEqual(len(paths),len(set(paths)))
        self.assertEqual(next(r for r in source if r['raw'][0]['path']=='/system/level/value')['mapped']['value'],1)
        self.assertEqual(next(r for r in source if r['raw'][0]['path']=='/system/location/heightenedLevel')['mapped']['value'],5)
        self.assertIn('/system/heightening/levels/4',paths)
        self.assertIn('/system/heightening/levels/3/range',paths)
        self.assertIn('/system/overlays/mode/system/traits',paths)
        self.assertIn('/system/overlays/mode/system/heightening',paths)
        target=next(r for r in records if r['section']=='relationships')['mapped']['value']
        self.assertEqual(target['target_uuid'],'Actor.owner.Item.entry')
        prose=[r for r in records if r['kind']=='text' and r['raw'][0]['path']=='/system/heightening/levels/3/description/value']
        self.assertGreater(len(prose),1)
        self.assertEqual(''.join(r['raw'][0]['value'] for r in prose),payload['text'])
        self.assertTrue(all(r['mapped']['value'] is None for r in prose))
