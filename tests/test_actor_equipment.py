"""PF2e-specific equipment8.6.1 authored-source DTO boundary regressions."""
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_item, _equipment_spec
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_action import response


def equipment(path='/system/traits/rarity', value='common', *, present=True):
    result=response(path,value,item_type='equipment',present=present)
    row=result['records'][0];spec=_equipment_spec(path)
    row.update(key='source:'+path,mapped=dict(concept=spec[0] if spec else 'forged',value=value if present else None,unit=None))
    row['provenance'].update(mapping='pf2e.equipment.source.v1',limitations=['source_only_no_equipment_benefit_application'])
    return result


class ActorEquipmentTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,result):
        self.manager.call.return_value=result
        return await read_item.fn(item_uuid='Item.a',sections=['source'])

    async def test_authored_values_and_absence(self):
        for path,value in [('/system/traits/value',[]),('/system/traits/value/0','custom'),('/system/traits/otherTags',[]),('/system/traits/otherTags/0','custom'),('/system/traits/rarity','custom'),('/system/slug',None),('/system/publication/title','Book'),('/system/publication/authors','Author'),('/system/publication/license','ORC'),('/system/publication/remaster',False)]:
            with self.subTest(path=path):await self.read(equipment(path,value))
        await self.read(equipment('/system/slug',present=False))

    async def test_strict_shapes_and_type_scope(self):
        for path,value in [('/system/traits/value',['custom']),('/system/traits/value/00','bad'),('/system/traits/value',None),('/system/traits/otherTags',{}),('/system/slug',False),('/system/traits/rarity',None),('/system/publication/remaster',0),('/system/activation',{}),('/system/frequency/max',3),('/system/benefitsActive',True),('/system/uses',{})]:
            with self.subTest(path=path),self.assertRaises(ToolError):await self.read(equipment(path,value))
        for change in [lambda r:r['mapped'].update(concept='active_benefits'),lambda r:r['mapped'].update(value=False),lambda r:r['mapped'].update(unit='benefits'),lambda r:r['provenance'].update(mapping='pf2e.physical.source.v1'),lambda r:r['provenance'].update(limitations=[]),lambda r:r['raw'][0].update(document_uuid='Item.other'),lambda r:r['provenance']['contributors'][0].update(path='/system/slug'),lambda r:r.update(kind='relationship'),lambda r:r.update(key='forged')]:
            bad=equipment();change(bad['records'][0])
            with self.assertRaises(ToolError):await self.read(bad)
        bad=equipment();bad['identity']['type']='weapon'
        with self.assertRaises(ToolError):await self.read(bad)
        with self.assertRaises(ToolError):await self.read(equipment('/system/quantity',1))

    async def test_actual_selector_descriptors_cross_boundary(self):
        script=r"""
import {equipmentFields} from './foundry-module/scripts/actorEquipment.js';
const source={type:'equipment',system:{traits:{value:['custom'],otherTags:[],rarity:'rare'},slug:null,publication:{title:'Book',authors:'Author',license:'ORC',remaster:true}}};
const fields=equipmentFields(source);source.system={};fields.push(...equipmentFields(source));console.log(JSON.stringify(fields));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(process.returncode,0,process.stderr)
        fields=json.loads(process.stdout);self.assertGreater(len(fields),15)
        for field in fields:
            with self.subTest(path=field['path']):
                result=equipment(field['path'],field.get('value'),present=field['present']);row=result['records'][0]
                row['mapped']['concept']=field['concept'];row['provenance']['limitations']=field['limitations']
                await self.read(result)

    async def test_actual_reader_pages_separate_physical_source(self):
        script=r"""
import {readItem} from './foundry-module/scripts/actors.js';
const source={name:'Equipment',type:'equipment',system:{quantity:12,usage:{value:'worn'},equipped:{carryType:'worn',invested:false},subitems:[{_id:'nested',name:'Attachment',type:'equipment',system:{secret:'never'}}],traits:{value:['custom'],otherTags:[],rarity:'common'},description:{value:'<p>Exact 😀</p>'},flags:{secret:'never'}}};
const item={id:'a',uuid:'Item.a',name:source.name,type:'equipment',documentName:'Item',parent:null,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
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
        self.assertEqual({r['provenance']['mapping'] for r in records},{'core.selected_source.v1','pf2e.physical.source.v1','pf2e.equipment.source.v1'})
        paths=[r['raw'][0]['path'] for r in records]
        self.assertEqual(len(paths),len(set(paths)))
        self.assertEqual(next(r for r in records if r['raw'][0]['path']=='/system/quantity')['mapped']['value'],12)
        self.assertEqual(next(r for r in records if r['raw'][0]['path']=='/system/equipped/invested')['mapped']['value'],False)
        self.assertEqual(next(r for r in records if r['raw'][0]['path']=='/system/usage/value')['mapped']['value'],'worn')
        self.assertEqual(next(r for r in records if r['raw'][0]['path']=='/system/subitems/0/_id')['mapped']['value'],'nested')
