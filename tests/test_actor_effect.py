"""PF2e-specific persisted effect8.6.1 source DTO boundary regressions."""
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import AsyncMock
from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_item, _effect_spec
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_action import response


def effect(path='/system/duration/value',value=-1,*,present=True,concept=None):
    result=response(path,value,item_type='effect',present=present)
    row=result['records'][0]
    row.update(key='source:'+path,mapped=dict(concept=concept or (_effect_spec(path)[0][0] if _effect_spec(path) else 'forged'),value=value if present else None,unit=None))
    row['provenance'].update(mapping='pf2e.effect.source.v1',limitations=['persisted_source_not_effective_or_expiration_state'])
    return result


class ActorEffectTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,result,section='source'):
        self.manager.call.return_value=result
        return await read_item.fn(item_uuid='Item.a',sections=[section])

    async def test_duration_and_start_are_persisted_not_expiration_calculations(self):
        for path,value in [('/system/level/value',0),('/system/duration/value',-1),('/system/duration/value',0),('/system/duration/unit','encounter'),('/system/duration/unit','unlimited'),('/system/duration/expiry',None),('/system/duration/expiry','round-end'),('/system/duration/sustained',False),('/system/start/value',0),('/system/start/initiative',None),('/system/start/initiative',0),('/system/tokenIcon/show',False),('/system/unidentified',True),('/system/fromSpell',False)]:
            with self.subTest(path=path,value=value):await self.read(effect(path,value))
        missing=await self.read(effect(present=False))
        self.assertNotIn('value',missing['records'][0]['raw'][0])
        for path,value in [('/system/level/value',1.5),('/system/duration/value',-2),('/system/duration/unit','seconds'),('/system/duration/sustained',0),('/system/start/initiative',False),('/system/duration/expiry','end'),('/system/expired',True),('/system/remaining',0)]:
            with self.subTest(path=path),self.assertRaises(ToolError):await self.read(effect(path,value))

    async def test_badge_union_preserves_formula_and_numeric_source_without_evaluation(self):
        for path,value,concept in [('/system/badge',None,None),('/system/badge/type','counter',None),('/system/badge/type','formula',None),('/system/badge/value','1d4+@actor.level',None),('/system/badge/value',0,None),('/system/badge/min',None,None),('/system/badge/max',3,None),('/system/badge/labels',None,None),('/system/badge/labels',[],None),('/system/badge/labels/0','',None),('/system/badge/loop',False,None),('/system/badge/evaluate',True,None),('/system/badge/reevaluate',None,'effect_badge_reevaluate'),('/system/badge/reevaluate','turn-end','effect_badge_reevaluate_event'),('/system/badge/reevaluate/formula','1d6',None),('/system/badge/reevaluate/initial',0,None)]:
            with self.subTest(path=path,value=value):await self.read(effect(path,value,concept=concept))
        for path,value in [('/system/badge',{}),('/system/badge/type','unknown'),('/system/badge/value',None),('/system/badge/value',True),('/system/badge/min',1.2),('/system/badge/labels',['private']),('/system/badge/labels/00','bad'),('/system/badge/label','derived'),('/system/badge/reevaluate',{}),('/system/badge/reevaluate/event',None),('/system/badge/reevaluate','custom')]:
            with self.subTest(path=path),self.assertRaises(ToolError):await self.read(effect(path,value))

    async def test_context_uuid_text_and_roll_leaves_are_not_hydrated_or_executed(self):
        for path,value in [('/system/context',None),('/system/context/origin/actor','Actor.source'),('/system/context/origin/token',None),('/system/context/origin/item','Compendium.scope.effects.Item.effect'),('/system/context/origin/rollOptions',[]),('/system/context/origin/rollOptions/0','self:condition:frightened:2'),('/system/context/origin/spellcasting',None),('/system/context/origin/spellcasting/attribute/type','wis'),('/system/context/origin/spellcasting/attribute/mod',4),('/system/context/origin/spellcasting/tradition',None),('/system/context/target',None),('/system/context/target/actor','Actor.target'),('/system/context/target/token',None),('/system/context/roll',None),('/system/context/roll/total',0),('/system/context/roll/degreeOfSuccess',None),('/system/context/roll/degreeOfSuccess',3)]:
            with self.subTest(path=path):await self.read(effect(path,value))
        for path,value in [('/system/context',{}),('/system/context/origin/actor',None),('/system/context/origin/rollOptions',[1]),('/system/context/origin/spellcasting/attribute/type','charisma'),('/system/context/roll/degreeOfSuccess',4),('/system/context/roll/degreeOfSuccess',True),('/system/context/roll/secret','never'),('/system/rules/0/key','RollOption'),('/flags/pf2e/aura/origin','Actor.a')]:
            with self.subTest(path=path),self.assertRaises(ToolError):await self.read(effect(path,value))

    async def test_exact_origin_mapping_primitive_types_and_item_scope(self):
        for path,value in [('/system/traits/value',[]),('/system/traits/value/0','custom'),('/system/traits/otherTags',[]),('/system/slug',None),('/system/publication/title','Source'),('/system/publication/remaster',False)]:await self.read(effect(path,value))
        for change in [lambda r:r['mapped'].update(concept='active'),lambda r:r['mapped'].update(value=True),lambda r:r['mapped'].update(unit='rounds'),lambda r:r['provenance'].update(mapping='pf2e.effect.effective.v1'),lambda r:r['provenance'].update(limitations=[]),lambda r:r['raw'][0].update(document_uuid='Item.other'),lambda r:r['provenance']['contributors'][0].update(path='/system/start/value'),lambda r:r.update(kind='relationship'),lambda r:r.update(key='forged')]:
            bad=effect(value=1);change(bad['records'][0])
            with self.assertRaises(ToolError):await self.read(bad)
        bad=effect();bad['identity']['type']='condition'
        with self.assertRaises(ToolError):await self.read(bad)

    async def test_same_page_badge_discriminator_preserves_page_independence(self):
        for badge,value in [('formula',3),('counter','1d4'),('value','1d4')]:
            result=effect('/system/badge/type',badge)
            result['records'].extend(effect('/system/badge/value',value)['records'])
            result['pagination']['returned']=2
            with self.subTest(badge=badge,value=value),self.assertRaises(ToolError):await self.read(result)
        for badge,value in [('formula','1d4'),('counter',0),('value',2)]:
            result=effect('/system/badge/type',badge)
            result['records'].extend(effect('/system/badge/value',value)['records']);result['pagination']['returned']=2
            await self.read(result)
        # A discriminator may be on a different page; isolated source stays valid.
        await self.read(effect('/system/badge/value',3))
        await self.read(effect('/system/badge/value','1d4'))

    async def test_same_page_absent_or_null_container_cannot_have_present_descendant(self):
        for path,child,value in [('/system/badge','/system/badge/value',0),('/system/context','/system/context/origin/actor','Actor.a'),('/system/context/target','/system/context/target/actor','Actor.a'),('/system/context/origin/spellcasting','/system/context/origin/spellcasting/attribute/mod',3),('/system/context/roll','/system/context/roll/total',0),('/system/badge/reevaluate','/system/badge/reevaluate/formula','1d4')]:
            for present in (True,False):
                result=effect(path,None,present=present)
                result['records'].extend(effect(child,value)['records']);result['pagination']['returned']=2
                with self.subTest(path=path,present=present),self.assertRaises(ToolError):await self.read(result)

    async def test_actual_browser_badge_branches_context_and_description_dtos(self):
        script=r"""
import {readItem} from './foundry-module/scripts/actors.js';
const docs=new Map();let resolutions=[];
globalThis.game={version:'14.369',system:{id:'pf2e',version:'8.6.1'},ready:true,user:{isGM:true},actors:new Map(),items:docs};globalThis.foundry={utils:{fromUuid:async uuid=>{resolutions.push(uuid);return docs.get(uuid);}}};
const description='<p>Exact 😀 effect formula text</p>'.repeat(100);
const context={origin:{actor:'Actor.origin',token:null,item:'Item.origin',spellcasting:{attribute:{type:'int',mod:4},tradition:'arcane'},rollOptions:['self:level:5']},target:{actor:'Actor.target',token:'Scene.s.Token.t'},roll:{total:20,degreeOfSuccess:2}};
const source={name:'Effect',type:'effect',system:{level:{value:5},duration:{value:-1,unit:'unlimited',expiry:'turn-start',sustained:false},start:{value:0,initiative:null},badge:null,context,traits:{value:['custom'],otherTags:[]},tokenIcon:{show:false},unidentified:false,fromSpell:true,publication:{title:'Test',authors:'Author',license:'ORC',remaster:true},description:{value:description,gm:'never'},rules:[{key:'RollOption',secret:'never'}],expired:true},flags:{secret:'never'}};
const item={id:'a',uuid:'Item.a',name:'Effect',type:'effect',documentName:'Item',parent:null,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};docs.set(item.uuid,item);
const branches=[null,{type:'counter',value:0,min:null,max:3,labels:['Zero','One'],loop:false},{type:'value',value:10,labels:null,reevaluate:{event:'turn-end',formula:'1d6+2',initial:3}},{type:'formula',value:'1d4+@actor.level',labels:[],evaluate:false,reevaluate:'initiative-roll'}];
const pages=[];
for(const badge of branches){source.system.badge=badge;let cursor;do{const page=await readItem({item_uuid:'Item.a',sections:['source'],limit:7,max_bytes:8000,...(cursor?{cursor}:{})});pages.push(page);cursor=page.pagination.next_cursor;}while(cursor);}
const text=[];let cursor;
do{const page=await readItem({item_uuid:'Item.a',sections:['description'],limit:2,max_bytes:8000,...(cursor?{cursor}:{})});text.push(page);cursor=page.pagination.next_cursor;}while(cursor);
console.log(JSON.stringify({pages,text,description,resolutions}));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(process.returncode,0,process.stderr)
        fixture=json.loads(process.stdout);records=[]
        for page in fixture['pages']:
            records.extend((await self.read(page))['records'])
            self.assertNotIn('never',json.dumps(page))
            self.assertNotIn('/system/expired',json.dumps(page))
        self.assertEqual(set(fixture['resolutions']),{'Item.a'})
        self.assertEqual({r['raw'][0]['value'] for r in records if r['raw'][0]['path']=='/system/badge/value'},{0,10,'1d4+@actor.level'})
        self.assertTrue(any(r['raw'][0]['path']=='/system/duration/expiry' and r['raw'][0]['value']=='turn-start' for r in records))
        fragments=[]
        for page in fixture['text']:
            fragments.extend(r['raw'][0]['value'] for r in (await self.read(page,'description'))['records'])
        self.assertEqual(''.join(fragments),fixture['description'])
