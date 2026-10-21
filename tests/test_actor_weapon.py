"""PF2e-specific weapon8.6.1 authored-source DTO boundary regressions."""
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_item, _weapon_spec
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_action import response


def weapon(path='/system/damage/dice', value=0, *, present=True):
    result=response(path,value,item_type='weapon',present=present)
    row=result['records'][0];spec=_weapon_spec(path)
    row.update(key='source:'+path,mapped=dict(concept=spec[0] if spec else 'forged',value=value if present else None,unit=None))
    row['provenance'].update(mapping='pf2e.weapon.source.v1',limitations=['source_only_no_effective_strike_calculation'])
    return result


class ActorWeaponTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,result):
        self.manager.call.return_value=result
        return await read_item.fn(item_uuid='Item.a',sections=['source'])

    async def test_damage_runes_ammunition_and_optional_values_preserve_source(self):
        cases=[('/system/damage/dice',0),('/system/damage/die',None),('/system/damage/modifier',-2),('/system/damage/damageType','custom'),('/system/damage/persistent',None),('/system/damage/persistent',{}),('/system/damage/persistent/faces',None),('/system/damage/persistent/number',2),('/system/runes/potency',0),('/system/runes/striking',2),('/system/runes/property',[]),('/system/runes/property/0','custom-rune'),('/system/ammo',None),('/system/ammo/builtIn',False),('/system/ammo/capacity',0),('/system/selectedAmmoId','local-ammo'),('/system/range',None),('/system/maxRange',120),('/system/reload/value','custom'),('/system/expend',None),('/system/attribute',None),('/system/usage/canBeAmmo',False)]
        for path,value in cases:
            with self.subTest(path=path):await self.read(weapon(path,value))
        missing=await self.read(weapon('/system/maxRange',present=False))
        self.assertNotIn('value',missing['records'][0]['raw'][0])

    async def test_combination_toggle_and_specific_baseline_remain_selected_leaves(self):
        for path,value in [('/system/meleeUsage',{}),('/system/meleeUsage/damage/type','slashing'),('/system/meleeUsage/traits',[]),('/system/meleeUsage/traitToggles/modular',None),('/system/traits/toggles',{}),('/system/traits/toggles/modular',None),('/system/traits/toggles/doubleBarrel/selected',False),('/system/specific',None),('/system/specific/material/type',None),('/system/specific/runes/property/0','custom')]:
            with self.subTest(path=path):await self.read(weapon(path,value))
        for path,value in [('/system/meleeUsage',None),('/system/traits/toggles/doubleBarrel',None),('/system/runes/property',['secret']),('/system/runes/property/00','bad'),('/system/damage/dice',True),('/system/range','120'),('/system/ammo/capacity',False),('/system/runes/effects/0','prepared'),('/system/damage/formula','prepared'),('/system/isEquipped',True),('/system/flags/fixedAttack',3),('/system/ammo',{'capacity':1})]:
            with self.subTest(path=path),self.assertRaises(ToolError):await self.read(weapon(path,value))

    async def test_exact_mapping_provenance_and_type_scopes(self):
        for change in [lambda r:r['mapped'].update(concept='effective_damage'),lambda r:r['mapped'].update(value=False),lambda r:r['mapped'].update(unit='feet'),lambda r:r['provenance'].update(mapping='pf2e.physical.source.v1'),lambda r:r['provenance'].update(limitations=[]),lambda r:r['raw'][0].update(document_uuid='Item.other'),lambda r:r['provenance']['contributors'][0].update(path='/system/range'),lambda r:r.update(kind='relationship'),lambda r:r.update(key='forged')]:
            bad=weapon();change(bad['records'][0])
            with self.assertRaises(ToolError):await self.read(bad)
        bad=weapon();bad['identity']['type']='armor'
        with self.assertRaises(ToolError):await self.read(bad)
        with self.assertRaises(ToolError):await self.read(weapon('/system/quantity',1))
        bad=weapon('/system/quantity',1);bad['records'][0]['provenance']['mapping']='pf2e.effect.source.v1'
        with self.assertRaises(ToolError):await self.read(bad)

    async def test_actual_selector_descriptors_cross_strict_python_boundary(self):
        script=r"""
import {weaponFields} from './foundry-module/scripts/actorWeapon.js';
const source={type:'weapon',system:{category:'martial',group:null,damage:{dice:0,die:null,damageType:'custom',modifier:-2,persistent:{number:2,faces:null,type:'fire'}},range:null,maxRange:120,reload:{value:'1'},ammo:{builtIn:false,baseType:null,capacity:0},selectedAmmoId:'local-only',runes:{potency:0,striking:2,property:['custom-rune']},specific:{material:{type:null,grade:null},runes:{potency:1,striking:0,property:[]}},meleeUsage:{damage:{type:'slashing',die:'d8'},group:'sword',traits:['custom'],traitToggles:{modular:null,versatile:'fire'}},traits:{value:['custom'],otherTags:[],rarity:'custom',toggles:{doubleBarrel:{selected:false},modular:null,versatile:{selected:null}}},usage:{canBeAmmo:false},grade:null,attribute:null,graspingAppendage:false,bonus:{value:0},splashDamage:{value:0},slug:null,publication:{title:'Book',authors:'Author',license:'ORC',remaster:true},flags:{secret:'never'}}};
const populated=weaponFields(source);source.system={};const absent=weaponFields(source);
source.system={damage:{persistent:{}},ammo:{},runes:{},meleeUsage:{},traits:{toggles:{}},specific:{}};
console.log(JSON.stringify([...populated,...absent,...weaponFields(source)]));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(process.returncode,0,process.stderr)
        descriptors=json.loads(process.stdout)
        self.assertGreater(len(descriptors),100)
        for field in descriptors:
            with self.subTest(path=field['path']):
                result=weapon(field['path'],field.get('value'),present=field['present'])
                row=result['records'][0]
                row['mapped']['concept']=field['concept'];row['provenance']['limitations']=field['limitations']
                await self.read(result)

    async def test_actual_reader_pages_mix_physical_and_weapon_mappings(self):
        script=r"""
import {readItem} from './foundry-module/scripts/actors.js';
const source={name:'Weapon',type:'weapon',system:{quantity:0,baseItem:'longsword',category:'martial',damage:{dice:1,die:'d8',damageType:'slashing',modifier:0,persistent:null},range:null,selectedAmmoId:'local-ammo',runes:{potency:0,striking:0,property:[]},traits:{value:['custom'],otherTags:[],rarity:'common'},description:{value:'<p>Exact 😀</p>'},flags:{secret:'never'}}};
const item={id:'a',uuid:'Item.a',name:source.name,type:'weapon',documentName:'Item',parent:null,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
globalThis.game={version:'14.369',system:{id:'pf2e',version:'8.6.1'},ready:true,user:{isGM:true},actors:new Map(),items:new Map([['a',item]])};globalThis.foundry={utils:{fromUuid:async()=>item}};
let cursor;const pages=[];do{const page=await readItem({item_uuid:'Item.a',sections:['source'],limit:4,max_bytes:8000,...(cursor?{cursor}:{})});pages.push(page);cursor=page.pagination.next_cursor;}while(cursor);console.log(JSON.stringify(pages));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(process.returncode,0,process.stderr)
        records=[]
        for page in json.loads(process.stdout):
            records.extend((await self.read(page))['records'])
            self.assertNotIn('never',json.dumps(page))
        self.assertEqual({r['provenance']['mapping'] for r in records},{'core.selected_source.v1','pf2e.physical.source.v1','pf2e.weapon.source.v1'})
        self.assertEqual(sum(r['raw'][0]['path']=='/system/baseItem' for r in records),1)
        selected=next(r for r in records if r['raw'][0]['path']=='/system/selectedAmmoId')
        self.assertEqual(selected['mapped']['value'],'local-ammo')
