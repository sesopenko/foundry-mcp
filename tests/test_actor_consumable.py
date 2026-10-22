"""PF2e-specific consumable8.6.1 authored-source DTO boundary regressions."""
import copy
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_item, _consumable_spec, _contained_spell_spec, SPELL_LIMIT
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_action import response


def consumable(path='/system/traits/rarity', value='common', *, present=True):
    result=response(path,value,item_type='consumable',present=present)
    row=result['records'][0];spec=_consumable_spec(path)
    row.update(key='source:'+path,mapped=dict(concept=spec[0] if spec else 'forged',value=value if present else None,unit=None))
    row['provenance'].update(mapping='pf2e.consumable.source.v1',limitations=['source_only_no_consumable_use_or_spell_application'])
    return result


def contained(path='/system/spell/system/range/value', value='120 feet', *, present=True):
    result=consumable(path,value,present=present)
    row=result['records'][0];spec=_contained_spell_spec(path)
    row['mapped']['concept']=spec[0] if spec else 'forged'
    row['provenance'].update(mapping='pf2e.spell.source.v1',limitations=SPELL_LIMIT.copy())
    return result


class ActorConsumableTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,result):
        self.manager.call.return_value=result
        return await read_item.fn(item_uuid='Item.a',sections=['source'])

    async def test_authored_values_and_absence(self):
        for path,value in [('/system/traits/value',[]),('/system/traits/value/0','custom'),('/system/traits/otherTags',[]),('/system/traits/otherTags/0','custom'),('/system/traits/rarity','custom'),('/system/slug',None),('/system/category','custom'),('/system/uses/value',0),('/system/uses/max',5),('/system/uses/autoDestroy',False),('/system/damage',None),('/system/damage/formula','2d6'),('/system/damage/type','custom'),('/system/damage/kind','healing'),('/system/spell',None),('/system/spell/_id','local'),('/system/spell/name','Spell'),('/system/spell/type','spell'),('/system/spell/system/level/value',2),('/system/publication/title','Book'),('/system/publication/authors','Author'),('/system/publication/license','ORC'),('/system/publication/remaster',False)]:
            with self.subTest(path=path):await self.read(consumable(path,value))
        await self.read(consumable('/system/slug',present=False))

    async def test_strict_shapes_and_type_scope(self):
        for path,value in [('/system/traits/value',['custom']),('/system/traits/value/00','bad'),('/system/traits/value',None),('/system/traits/otherTags',{}),('/system/slug',False),('/system/traits/rarity',None),('/system/publication/remaster',0),('/system/activation',{}),('/system/frequency/max',3),('/system/benefitsActive',True),('/system/uses',{}),('/system/uses/value',True),('/system/damage',{}),('/system/damage/formula',None),('/system/spell',{}),('/system/spell/type','weapon'),('/system/spell/uuid','Item.fake'),('/system/spell/system/description/value','hidden')]:
            with self.subTest(path=path),self.assertRaises(ToolError):await self.read(consumable(path,value))
        for change in [lambda r:r['mapped'].update(concept='active_benefits'),lambda r:r['mapped'].update(value=False),lambda r:r['mapped'].update(unit='benefits'),lambda r:r['provenance'].update(mapping='pf2e.physical.source.v1'),lambda r:r['provenance'].update(limitations=[]),lambda r:r['raw'][0].update(document_uuid='Item.other'),lambda r:r['provenance']['contributors'][0].update(path='/system/slug'),lambda r:r.update(kind='relationship'),lambda r:r.update(key='forged')]:
            bad=consumable();change(bad['records'][0])
            with self.assertRaises(ToolError):await self.read(bad)
        bad=consumable();bad['identity']['type']='weapon'
        with self.assertRaises(ToolError):await self.read(bad)
        with self.assertRaises(ToolError):await self.read(consumable('/system/quantity',1))

    async def test_contained_definition_and_schema_markers(self):
        fields=[('time/value','2 actions or 1 minute'),('range/value','120 feet'),
                ('location/value','unresolved-local-entry'),('location/heightenedLevel',5),
                ('traits/traditions',[]),('traits/value/0','custom'),('damage',{}),
                ('damage/key~1one~0/formula','2d6'),('damage/key/kinds',[]),
                ('defense/save/basic',True),('heightening/type','fixed'),
                ('heightening/levels',{}),('heightening/levels/3',{}),
                ('heightening/levels/3/range',{}),('heightening/levels/3/range/value','240 feet'),
                ('overlays',{}),('overlays/mode/name','Alternate'),
                ('overlays/mode/system',{}),('overlays/mode/system/damage',{})]
        for suffix,value in fields:
            with self.subTest(path=suffix):
                await self.read(contained('/system/spell/system/'+suffix,value))
        await self.read(contained('/system/spell/system/heightening',present=False))
        # Established consumable metadata and base rank keep their original contract.
        await self.read(consumable('/system/spell/system/level/value',2))
        with self.assertRaises(ToolError):
            await self.read(contained('/system/spell/system/level/value',2))

    async def test_contained_forgery_and_prose_boundaries(self):
        for suffix,value in [('statistic',{}),('damage',{'secret':'never'}),
                             ('traits/value',['arcane']),('heightening/levels/03/range/value','x'),
                             ('overlays/mode/system/overlays/second/name','x'),('level/value',True),
                             ('description/value','prose in source')]:
            with self.subTest(path=suffix),self.assertRaises(ToolError):
                await self.read(contained('/system/spell/system/'+suffix,value))
        for mutate in [lambda r:r['mapped'].update(concept='effective_cast_rank'),
                       lambda r:r['provenance'].update(mapping='pf2e.consumable.source.v1'),
                       lambda r:r['provenance'].update(limitations=[]),
                       lambda r:r['raw'][0].update(document_uuid='Item.nested'),
                       lambda r:r['provenance']['contributors'][0].update(path='/system/range/value'),
                       lambda r:r.update(kind='relationship'),lambda r:r.update(key='source:/system/range/value')]:
            bad=contained();mutate(bad['records'][0])
            with self.assertRaises(ToolError):await self.read(bad)
        for suffix in ['description/value','heightening/levels/3/description/value',
                       'overlays/mode/system/description/value']:
            path='/system/spell/system/'+suffix
            result=contained(path,'<p>Exact 😀</p>');row=result['records'][0]
            result['sections']=[dict(name='description',status='complete',reasons=[])]
            row.update(section='description',kind='text',key='description:'+path+':0',
                       text=dict(path=path,start=0,end=15,total=15,complete=True))
            row['mapped']['value']=None
            self.manager.call.return_value=result
            await read_item.fn(item_uuid='Item.a',sections=['description'])
            for mutate in [lambda r:r['text'].update(path='/system/description/value'),
                           lambda r:r['text'].update(end=14),lambda r:r['mapped'].update(value='parsed')]:
                bad=copy.deepcopy(result);mutate(bad['records'][0]);self.manager.call.return_value=bad
                with self.assertRaises(ToolError):
                    await read_item.fn(item_uuid='Item.a',sections=['description'])

    async def test_actual_selector_descriptors_cross_boundary(self):
        script=r"""
import {consumableFields} from './foundry-module/scripts/actorConsumable.js';
const source={type:'consumable',system:{category:'wand',uses:{value:1,max:2,autoDestroy:false},damage:{formula:'1d6',type:'fire',kind:'damage'},spell:{_id:'local',name:'Spell',type:'spell',system:{level:{value:2}}},traits:{value:['custom'],otherTags:[],rarity:'rare'},slug:null,publication:{title:'Book',authors:'Author',license:'ORC',remaster:true}}};
const fields=consumableFields(source);source.system={};fields.push(...consumableFields(source));console.log(JSON.stringify(fields));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(process.returncode,0,process.stderr)
        fields=json.loads(process.stdout);self.assertGreater(len(fields),15)
        for field in fields:
            with self.subTest(path=field['path']):
                result=consumable(field['path'],field.get('value'),present=field['present']);row=result['records'][0]
                row['mapped']['concept']=field['concept'];row['provenance']['limitations']=field['limitations']
                await self.read(result)

    async def test_actual_reader_pages_separate_physical_source(self):
        script=r"""
import {readItem} from './foundry-module/scripts/actors.js';
const source={name:'Consumable',type:'consumable',system:{quantity:12,usage:{value:'worn'},equipped:{carryType:'worn',invested:false},category:'potion',uses:{value:2,max:3,autoDestroy:true},damage:null,spell:null,traits:{value:['custom'],otherTags:[],rarity:'common'},description:{value:'<p>Exact 😀</p>'},flags:{secret:'never'}}};
const item={id:'a',uuid:'Item.a',name:source.name,type:'consumable',documentName:'Item',parent:null,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
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
        self.assertEqual({r['provenance']['mapping'] for r in records},{'core.selected_source.v1','pf2e.physical.source.v1','pf2e.consumable.source.v1'})
        paths=[r['raw'][0]['path'] for r in records]
        self.assertEqual(len(paths),len(set(paths)))
        self.assertEqual(next(r for r in records if r['raw'][0]['path']=='/system/quantity')['mapped']['value'],12)
        self.assertEqual(next(r for r in records if r['raw'][0]['path']=='/system/equipped/invested')['mapped']['value'],False)
        self.assertEqual(next(r for r in records if r['raw'][0]['path']=='/system/usage/value')['mapped']['value'],'worn')
        self.assertEqual(next(r for r in records if r['raw'][0]['path']=='/system/uses/value')['mapped']['value'],2)
        self.assertEqual(next(r for r in records if r['raw'][0]['path']=='/system/spell')['mapped']['value'],None)

    async def test_actual_contained_spell_pages_and_exact_layered_prose(self):
        script=r"""
import {readItem} from './foundry-module/scripts/actors.js';
const text='<p>Exact 😀 '+('é😀'.repeat(3500))+'</p>';
const source={name:'Wand',type:'consumable',system:{quantity:2,category:'wand',uses:{value:1,max:1,autoDestroy:false},damage:null,spell:{_id:'local',name:'Spell',type:'spell',system:{level:{value:1},time:{value:'2 actions'},location:{value:'entry',heightenedLevel:5},damage:{heal:{formula:'1d6',type:'vitality',category:null,kinds:['healing'],materials:[]}},heightening:{type:'fixed',levels:{3:{description:{value:text},range:{},damage:{heal:{formula:'3d6'}}},4:{}}},overlays:{mode:{name:'Mode',overlayType:'override',sort:0,system:{description:{value:'<p>Overlay exact 😀</p>'},traits:{},heightening:{}}}},description:{value:'<p>Root exact 😀</p>'}}},description:{value:'<p>Activate this wand.</p>'}}};
const owner={id:'owner',uuid:'Actor.owner',name:'Owner',type:'npc',documentName:'Actor',items:new Map(),testUserPermission:()=>true};
const item={id:'a',uuid:'Actor.owner.Item.a',name:source.name,type:'consumable',documentName:'Item',parent:owner,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};owner.items.set('a',item);
owner.items.set('entry',{get uuid(){throw Error('Contained spell must not resolve actor entry');}});
globalThis.game={version:'14.369',system:{id:'pf2e',version:'8.6.1'},ready:true,user:{isGM:true},actors:new Map([['owner',owner]]),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>{if(uuid===item.uuid)return item;throw Error('Unexpected nested lookup');}}};
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
            self.assertEqual(next(s for s in checked['sections'] if s['name']=='relationships')['status'],'unsupported')
        source=[r for r in records if r['section']=='source'];paths=[r['raw'][0]['path'] for r in source]
        self.assertEqual(len(paths),len(set(paths)))
        base=next(r for r in source if r['raw'][0]['path']=='/system/spell/system/level/value')
        self.assertEqual(base['mapped']['concept'],'consumable_contained_spell_base_rank')
        self.assertEqual(base['provenance']['mapping'],'pf2e.consumable.source.v1')
        self.assertIn('/system/spell/system/heightening/levels/4',paths)
        self.assertIn('/system/spell/system/heightening/levels/3/range',paths)
        nested=[r for r in records if r['provenance']['mapping']=='pf2e.spell.source.v1']
        self.assertGreater(len(nested),10)
        self.assertTrue(all(r['raw'][0]['document_uuid']=='Actor.owner.Item.a' for r in nested))
        self.assertFalse(any(r['kind']=='relationship' for r in records))
        prose=[r for r in records if r['kind']=='text' and r['raw'][0]['path']=='/system/spell/system/heightening/levels/3/description/value']
        self.assertGreater(len(prose),1)
        self.assertEqual(''.join(r['raw'][0]['value'] for r in prose),payload['text'])
        self.assertTrue(all(r['mapped']['value'] is None for r in prose))
