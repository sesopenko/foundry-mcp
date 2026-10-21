"""PF2e-specific authored NPC attack boundary regressions, schema8.6.1."""
import json
import subprocess
from pathlib import Path
import unittest
from unittest.mock import AsyncMock
from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_item
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_action import response


def attack(path='/system/action', value='strike', **kwargs):
    result=response(path,value,item_type='melee',**kwargs)
    record=result['records'][0]
    record['provenance']['mapping']='pf2e.melee.source.v1'
    record['mapped']['value']=({'strike':'Strike','area-fire':'Area Fire','auto-fire':'Auto Fire'}.get(value,value) if path=='/system/action' and isinstance(value,str) else 'no_explicit_range' if path=='/system/range' and value is None and record['raw'][0]['present'] else value)
    return result


def effect(value='Grab', *, present=True, marker=False):
    result=attack('/system/attackEffects/value'+('' if marker else '/0'),value,present=present,section='relationships')
    record=result['records'][0]
    record.update(kind='relationship',key='relationships:attackEffects'+('' if marker else ':0'))
    record['mapped']=dict(concept='additional_effect',value=dict(target_uuid=None,status='missing' if marker else 'unverified'),unit=None)
    record['provenance'].update(mapping='pf2e.melee.attack_effect.v1',limitations=['label_not_document_uuid'])
    return result


class ActorMeleeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,result,section='source'):
        self.manager.call.return_value=result
        return await read_item.fn(item_uuid='Item.a',sections=[section])

    async def test_modes_range_and_authored_values(self):
        for code,label in [('strike','Strike'),('area-fire','Area Fire'),('auto-fire','Auto Fire'),('custom','custom')]:
            self.assertEqual((await self.read(attack(value=code)))['records'][0]['mapped']['value'],label)
        for path,value in [('/system/range',None),('/system/range/increment',None),('/system/range/max',60),('/system/area',None),('/system/area/type','burst'),('/system/area/value',10),('/system/bonus/value',0),('/system/subjectToMAP',False),('/system/traits/value/0','thrown-20'),('/system/damageRolls/a~1b~0c/damage','2d6+4'),('/system/damageRolls//category',None),('/system/damageRolls/a/damageType','bleed'),('/system/damageRolls',{}),('/system/traits/value',[])]:
            with self.subTest(path=path):await self.read(attack(path,value))
        result=attack('/system/range',None)
        self.assertEqual((await self.read(result))['records'][0]['mapped']['value'],'no_explicit_range')
        result['records'][0]['mapped']['value']='melee'
        with self.assertRaises(ToolError):await self.read(result)
        missing=attack('/system/range',None,present=False)
        self.assertNotIn('value',(await self.read(missing))['records'][0]['raw'][0])

    async def test_reject_invalid_types_private_paths_and_damage_dumps(self):
        for path,value in [('/system/bonus/value',True),('/system/subjectToMAP',0),('/system/range',{}),('/system/area',{}),('/system/damageRolls',{'a':{'damage':'secret'}}),('/system/damageRolls/a',{}),('/system/damageRolls/a~2b/damage','1d6'),('/system/damageRolls/a/damage',None),('/system/damageRolls/a/category',0),('/system/traits/value',['agile']),('/system/traits/value/00','agile'),('/system/traits/value/0',False),('/system/publication/remaster','false'),('/flags/pf2e/linkedWeapon','Item.weapon'),('/system/rules',[])]:
            with self.subTest(path=path),self.assertRaises(ToolError):await self.read(attack(path,value))
        result=attack();result['records'][0]['raw'][0]['document_uuid']='Item.weapon'
        with self.assertRaises(ToolError):await self.read(result)
        result=attack();result['identity']['type']='spell'
        with self.assertRaises(ToolError):await self.read(result)

    async def test_effect_labels_preserve_missing_empty_and_named_unresolved(self):
        for result in [effect(),effect(''),effect('Item.looksLikeUuid'),effect([],marker=True),effect(None,marker=True,present=False)]:
            await self.read(result,'relationships')
        for mutation in [lambda r:r['mapped']['value'].update(target_uuid='Item.effect'),lambda r:r['mapped']['value'].update(status='resolved'),lambda r:r.update(key='relationships:attackEffects:1'),lambda r:r['provenance'].update(limitations=[]),lambda r:r['provenance'].update(limitations=['']),lambda r:r['provenance']['contributors'][0].update(path='/system/action')]:
            result=effect();mutation(result['records'][0])
            with self.assertRaises(ToolError):await self.read(result,'relationships')
        result=effect(['secret'],marker=True)
        with self.assertRaises(ToolError):await self.read(result,'relationships')

    async def test_actual_browser_source_and_effect_label_dtos(self):
        script=r"""
import {readItem} from './foundry-module/scripts/actors.js';
const source={name:'Thrown claw',type:'melee',system:{action:'strike',bonus:{value:12},subjectToMAP:true,range:null,area:null,damageRolls:{'a/~':{damage:'2d6+4',damageType:'piercing',category:null},bleed:{damage:'1d6',damageType:'bleed',category:'persistent'}},traits:{value:['thrown-20'],otherTags:[]},attackEffects:{value:['Grab','Item.not-a-selector','']},description:{value:'<p>Source</p>',gm:'secret'},rules:[{secret:true}]},flags:{secret:true}};
const item={id:'a',uuid:'Item.a',name:source.name,type:'melee',documentName:'Item',parent:null,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
globalThis.game={version:'14.369',system:{id:'pf2e',version:'8.6.1'},ready:true,user:{isGM:true},actors:new Map(),items:new Map([['a',item]])};let resolutions=[];
globalThis.foundry={utils:{fromUuid:async uuid=>{resolutions.push(uuid);return uuid==='Item.a'?item:null;}}};
const sourcePages=[];let cursor;
do{const page=await readItem({item_uuid:'Item.a',sections:['source'],limit:5,max_bytes:8000,...(cursor?{cursor}:{})});sourcePages.push(page);cursor=page.pagination.next_cursor;}while(cursor);
const relationships=await readItem({item_uuid:'Item.a',sections:['relationships']});
source.system.attackEffects.value=[];const empty=await readItem({item_uuid:'Item.a',sections:['relationships']});
delete source.system.attackEffects;const missing=await readItem({item_uuid:'Item.a',sections:['relationships']});
console.log(JSON.stringify({sourcePages,relationships,empty,missing,resolutions}));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(process.returncode,0,process.stderr)
        fixture=json.loads(process.stdout);records=[]
        for page in fixture['sourcePages']:
            records.extend((await self.read(page))['records'])
            self.assertNotIn('secret',json.dumps(page))
        fields={row['raw'][0]['path']:row for row in records}
        self.assertEqual(fields['/system/range']['mapped']['value'],'no_explicit_range')
        self.assertEqual(fields['/system/damageRolls/a~1~0/damage']['raw'][0]['value'],'2d6+4')
        self.assertEqual(fields['/system/damageRolls/bleed/category']['mapped']['value'],'persistent')
        self.assertEqual(set(fixture['resolutions']),{'Item.a'})
        relationships=(await self.read(fixture['relationships'],'relationships'))['records']
        self.assertEqual([r['raw'][0]['value'] for r in relationships],['Grab','Item.not-a-selector',''])
        for key,present in [('empty',True),('missing',False)]:
            row=(await self.read(fixture[key],'relationships'))['records'][0]
            self.assertEqual(row['raw'][0]['present'],present)
            self.assertEqual(row['mapped']['value'],dict(target_uuid=None,status='missing'))
