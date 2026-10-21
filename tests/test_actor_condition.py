"""PF2e-specific condition8.6.1 persisted primitive DTO boundary regressions."""
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_item, _condition_spec
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_action import response


def condition(path='/system/value/value',value=0,*,present=True):
    result=response(path,value,item_type='condition',present=present)
    row=result['records'][0];spec=_condition_spec(path)
    row.update(key='source:'+path,mapped=dict(concept=spec[0] if spec else 'forged',value=value if present else None,unit=None))
    row['provenance'].update(mapping='pf2e.condition.source.v1',limitations=['persisted_source_not_effective_condition_state'])
    return result


class ActorConditionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,result,section='source'):
        self.manager.call.return_value=result
        return await read_item.fn(item_uuid='Item.a',sections=[section])

    async def test_valuedness_and_stored_value_are_independent_source_fields(self):
        for path,value in [('/system/value/isValued',False),('/system/value/isValued',True),('/system/value/value',None),('/system/value/value',0),('/system/value/value',2.5),('/system/group',None),('/system/group','detection'),('/system/fromSpell',False),('/system/slug',None)]:
            with self.subTest(path=path,value=value):await self.read(condition(path,value))
        missing=await self.read(condition(present=False))
        self.assertNotIn('value',missing['records'][0]['raw'][0])
        for path,value in [('/system/value/isValued',0),('/system/value/value',False),('/system/value/value','2'),('/system/value/value',float('inf')),('/system/fromSpell',None),('/system/group',True),('/system/active',True),('/system/suppressed',False),('/system/duration/value',-1)]:
            with self.subTest(path=path),self.assertRaises(ToolError):await self.read(condition(path,value))

    async def test_persistent_damage_is_authored_formula_not_prepared_roll(self):
        for path,value in [('/system/persistent',None),('/system/persistent/formula','2d6+@actor.level'),('/system/persistent/damageType','fire'),('/system/persistent/dc',15),('/system/persistent/dc',0),('/system/persistent/criticalHit',False)]:
            with self.subTest(path=path):await self.read(condition(path,value))
        await self.read(condition('/system/persistent',present=False))
        for path,value in [('/system/persistent',{}),('/system/persistent/formula',None),('/system/persistent/dc',True),('/system/persistent/criticalHit',0),('/system/persistent/damage','2d6'),('/system/persistent/expectedValue',7)]:
            with self.subTest(path=path),self.assertRaises(ToolError):await self.read(condition(path,value))

    async def test_local_references_override_slugs_and_empty_markers_remain_exact(self):
        for path,value in [('/system/references/parent',None),('/system/references/parent/id','localParent'),('/system/references/children',[]),('/system/references/children/0/id','sameId'),('/system/references/children/0/type','condition'),('/system/references/overrides',[]),('/system/references/overrides/0/id','sameId'),('/system/references/overrides/0/type','condition'),('/system/references/overriddenBy',[]),('/system/references/overriddenBy/0/id','other'),('/system/references/overriddenBy/0/type','condition'),('/system/overrides',[]),('/system/overrides/0','frightened'),('/system/traits/value',[]),('/system/traits/value/0','custom'),('/system/traits/otherTags',[]),('/system/publication/remaster',False)]:
            with self.subTest(path=path,value=value):await self.read(condition(path,value))
        for path,value in [('/system/references/parent',{}),('/system/references/children',None),('/system/references/children',[{'id':'a'}]),('/system/references/children/00/id','a'),('/system/references/children/0/type','effect'),('/system/references/parent/type','condition'),('/system/overrides',['a']),('/system/overrides/0',None),('/system/traits/value',['custom']),('/system/publication/remaster','false')]:
            with self.subTest(path=path),self.assertRaises(ToolError):await self.read(condition(path,value))

    async def test_provenance_mapping_and_type_boundaries_reject_forgery(self):
        for change in [lambda r:r['mapped'].update(concept='active'),lambda r:r['mapped'].update(value=False),lambda r:r['mapped'].update(unit='rounds'),lambda r:r['provenance'].update(mapping='pf2e.condition.effective.v1'),lambda r:r['provenance'].update(limitations=[]),lambda r:r['raw'][0].update(document_uuid='Item.other'),lambda r:r['provenance']['contributors'][0].update(path='/system/group'),lambda r:r.update(kind='relationship'),lambda r:r.update(key='forged')]:
            bad=condition();change(bad['records'][0])
            with self.assertRaises(ToolError):await self.read(bad)
        bad=condition();bad['identity']['type']='effect'
        with self.assertRaises(ToolError):await self.read(bad)
        for path in ['/system/rules/0/key','/system/_migration/version','/flags/secret']:
            with self.assertRaises(ToolError):await self.read(condition(path,'never'))

    async def test_actual_browser_condition_pages_preserve_source_and_description(self):
        script=r"""
import {readItem} from './foundry-module/scripts/actors.js';
const docs=new Map();let resolutions=[];
globalThis.game={version:'14.369',system:{id:'pf2e',version:'8.6.1'},ready:true,user:{isGM:true},actors:new Map(),items:docs};globalThis.foundry={utils:{fromUuid:async uuid=>{resolutions.push(uuid);return docs.get(uuid);}}};
const description='<p>Condition exact 😀 text</p>'.repeat(100);
const source={name:'Condition',type:'condition',system:{value:{isValued:true,value:0},persistent:null,references:{parent:{id:'localParent'},children:[{id:'sameId',type:'condition'}],overrides:[{id:'sameId',type:'condition'}],overriddenBy:[]},overrides:['frightened'],fromSpell:false,group:null,traits:{value:['custom'],otherTags:[]},slug:'frightened',publication:{title:'Test',authors:'Author',license:'ORC',remaster:true},description:{value:description,gm:'never'},rules:[{key:'RollOption',secret:'never'}],active:true,suppressed:false,duration:{value:-1}},flags:{secret:'never'}};
const item={id:'a',uuid:'Item.a',name:'Condition',type:'condition',documentName:'Item',parent:null,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};docs.set(item.uuid,item);
const branches=[null,{formula:'2d6+@actor.level',damageType:'fire',dc:15,criticalHit:false},undefined];
const pages=[];
for(const persistent of branches){source.system.persistent=persistent;let cursor;do{const page=await readItem({item_uuid:'Item.a',sections:['source'],limit:4,max_bytes:8000,...(cursor?{cursor}:{})});pages.push(page);cursor=page.pagination.next_cursor;}while(cursor);}
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
            for forbidden in ['/system/active','/system/suppressed','/system/duration','/system/persistent/damage"','/system/persistent/expectedValue']:
                self.assertNotIn(forbidden,json.dumps(page))
        self.assertEqual(set(fixture['resolutions']),{'Item.a'})
        ids=[r['raw'][0]['value'] for r in records if r['raw'][0]['path'].endswith('/id')]
        self.assertEqual(set(ids),{'localParent','sameId'})
        self.assertTrue(any(r['raw'][0]['path']=='/system/persistent/formula' and r['raw'][0]['value']=='2d6+@actor.level' for r in records))
        markers=[r['raw'][0] for r in records if r['raw'][0]['path']=='/system/persistent']
        self.assertTrue(any(r['present'] and r['value'] is None for r in markers))
        self.assertTrue(any(not r['present'] for r in markers))
        fragments=[]
        for page in fixture['text']:
            fragments.extend(r['raw'][0]['value'] for r in (await self.read(page,'description'))['records'])
        self.assertEqual(''.join(fragments),fixture['description'])
