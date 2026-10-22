"""PF2e-specific shield8.6.1 authored-source DTO boundary regressions."""
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_item, _shield_spec
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_action import response


def shield(path='/system/acBonus', value=0, *, present=True):
    result=response(path,value,item_type='shield',present=present)
    row=result['records'][0];spec=_shield_spec(path)
    row.update(key='source:'+path,mapped=dict(concept=spec[0] if spec else 'forged',value=value if present else None,unit=None))
    row['provenance'].update(mapping='pf2e.shield.source.v1',limitations=['source_only_no_actor_shield_calculation'])
    return result


class ActorShieldTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,result):
        self.manager.call.return_value=result
        return await read_item.fn(item_uuid='Item.a',sections=['source'])

    async def test_authored_values_and_absence(self):
        for path,value in [('/system/acBonus',0),('/system/speedPenalty',-5),('/system/grade',None),('/system/runes',{}),('/system/runes/reinforcing',3),('/system/specific',None),('/system/specific',{}),('/system/specific/material',{}),('/system/specific/material/type',None),('/system/specific/runes/reinforcing',2),('/system/traits/value',[]),('/system/traits/otherTags/0','custom'),('/system/traits/rarity','custom'),('/system/slug',None),('/system/publication/remaster',True),('/system/traits/integrated',None),('/system/traits/integrated',{}),('/system/traits/integrated/runes/potency',2),('/system/traits/integrated/runes/striking',1),('/system/traits/integrated/runes/property',[]),('/system/specific/integrated/runes/property/0','custom'),('/system/traits/integrated/versatile',None),('/system/traits/integrated/versatile',{}),('/system/traits/integrated/versatile/selected','piercing')]:
            with self.subTest(path=path):await self.read(shield(path,value))
        await self.read(shield('/system/acBonus',present=False))

    async def test_strict_shapes_and_type_scope(self):
        for path,value in [('/system/acBonus',True),('/system/acBonus',None),('/system/runes',None),('/system/traits/integrated/runes/property',['custom']),('/system/traits/integrated/runes/property/00','bad'),('/system/traits/value',None),('/system/slug',False),('/system/usage/value','held-in-one-hand'),('/system/isRaised',True),('/system/isBroken',True),('/system/attributes/ac/value',30),('/system/specific/material',None),('/system/runes/reinforcing','2'),('/system/traits/integrated/versatile/selected',None)]:
            with self.subTest(path=path),self.assertRaises(ToolError):await self.read(shield(path,value))
        for change in [lambda r:r['mapped'].update(concept='actor_ac'),lambda r:r['mapped'].update(value=False),lambda r:r['mapped'].update(unit='AC'),lambda r:r['provenance'].update(mapping='pf2e.physical.source.v1'),lambda r:r['provenance'].update(limitations=[]),lambda r:r['raw'][0].update(document_uuid='Item.other'),lambda r:r['provenance']['contributors'][0].update(path='/system/speedPenalty'),lambda r:r.update(kind='relationship'),lambda r:r.update(key='forged')]:
            bad=shield();change(bad['records'][0])
            with self.assertRaises(ToolError):await self.read(bad)
        bad=shield();bad['identity']['type']='armor'
        with self.assertRaises(ToolError):await self.read(bad)
        with self.assertRaises(ToolError):await self.read(shield('/system/quantity',1))

    async def test_actual_selector_descriptors_cross_boundary(self):
        script=r"""
import {shieldFields} from './foundry-module/scripts/actorShield.js';
const source={type:'shield',system:{acBonus:0,speedPenalty:-5,grade:null,runes:{reinforcing:2},specific:{material:{type:null,grade:'standard'},runes:{reinforcing:1},integrated:{runes:{potency:1,striking:0,property:[]}}},traits:{value:['custom'],otherTags:[],rarity:'rare',integrated:{runes:{potency:1,striking:1,property:['custom']},versatile:{selected:'piercing'}}},slug:null,publication:{title:'Book',authors:'Author',license:'ORC',remaster:true}}};
const fields=shieldFields(source);source.system={specific:null};fields.push(...shieldFields(source));source.system={runes:{},specific:{}};fields.push(...shieldFields(source));source.system={};fields.push(...shieldFields(source));console.log(JSON.stringify(fields));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(process.returncode,0,process.stderr)
        fields=json.loads(process.stdout);self.assertGreater(len(fields),30)
        for field in fields:
            with self.subTest(path=field['path']):
                result=shield(field['path'],field.get('value'),present=field['present']);row=result['records'][0]
                row['mapped']['concept']=field['concept'];row['provenance']['limitations']=field['limitations']
                await self.read(result)

    async def test_actual_reader_pages_separate_physical_source(self):
        script=r"""
import {readItem} from './foundry-module/scripts/actors.js';
const source={name:'Shield',type:'shield',system:{quantity:1,hp:{value:56,max:12},hardness:3,baseItem:'steel-shield',acBonus:2,speedPenalty:0,grade:null,runes:{reinforcing:0},specific:null,traits:{value:['custom'],otherTags:[],rarity:'common',integrated:null},description:{value:'<p>Exact 😀</p>'},flags:{secret:'never'}}};
const item={id:'a',uuid:'Item.a',name:source.name,type:'shield',documentName:'Item',parent:null,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
globalThis.game={version:'14.369',system:{id:'pf2e',version:'8.6.1'},ready:true,user:{isGM:true},actors:new Map(),items:new Map([['a',item]])};globalThis.foundry={utils:{fromUuid:async()=>item}};
let cursor;const pages=[];do{const page=await readItem({item_uuid:'Item.a',sections:['source'],limit:4,max_bytes:8000,...(cursor?{cursor}:{})});pages.push(page);cursor=page.pagination.next_cursor;}while(cursor);console.log(JSON.stringify(pages));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(process.returncode,0,process.stderr)
        records=[];pages=json.loads(process.stdout)
        self.assertGreater(len(pages),1)
        for page in pages:
            records.extend((await self.read(page))['records'])
            self.assertNotIn('never',json.dumps(page))
        self.assertEqual({r['provenance']['mapping'] for r in records},{'core.selected_source.v1','pf2e.physical.source.v1','pf2e.shield.source.v1'})
        paths=[r['raw'][0]['path'] for r in records]
        self.assertEqual(len(paths),len(set(paths)))
        self.assertEqual(next(r for r in records if r['raw'][0]['path']=='/system/quantity')['mapped']['value'],1)
        self.assertEqual(next(r for r in records if r['raw'][0]['path']=='/system/acBonus')['mapped']['value'],2)
        self.assertEqual(next(r for r in records if r['raw'][0]['path']=='/system/hp/value')['mapped']['value'],56)
        self.assertEqual(next(r for r in records if r['raw'][0]['path']=='/system/hp/max')['mapped']['value'],12)
        self.assertEqual(next(r for r in records if r['raw'][0]['path']=='/system/hardness')['mapped']['value'],3)
