"""PF2e-specific KitSystemSchema8.6.1 source and definition DTO boundary tests."""
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import AsyncMock
from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_item, _kit_spec
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_action import response


def kit(path='/system/items',value=None,*,present=True):
    result=response(path,value,item_type='kit',present=present);row=result['records'][0]
    spec=_kit_spec(path)
    row.update(key='source:'+path,mapped=dict(concept=spec[0] if spec else 'forged',value=value if present else None,unit=None))
    row['provenance'].update(mapping='pf2e.kit.source.v1',limitations=['bundle_definition_not_owned_inventory'])
    return result


def reference(path='/system/items/a/uuid',claim='Item.component',status='unverified'):
    result=kit(path,claim);result['sections'][0]['name']='relationships';row=result['records'][0]
    row.update(section='relationships',kind='relationship',key='relationships:kit:'+path,mapped=dict(concept='kit_component_reference',value=dict(status=status,target_uuid=None),unit=None))
    row['provenance']['mapping']='pf2e.kit.component-reference.v1'
    if status=='resolved':row['mapped']['value'].update(target_uuid=claim,document_name='Item',type='equipment',name='Actual definition',name_truncated=False)
    return result


class ActorKitTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,result):
        self.manager.call.return_value=result
        return await read_item.fn(item_uuid='Item.a',sections=[result['sections'][0]['name']])

    async def test_source_values_escaped_keys_finite_depth_and_absence(self):
        for path,value in [('/system/items',{}),('/system/items/a~1b~0c/uuid','Item.x'),('/system/items/a/name','Stored name'),('/system/items/a/img','icons/test.webp'),('/system/items/a/quantity',3),('/system/items/a/isContainer',False),('/system/items/a/items',{}),('/system/items/a/items',None),('/system/items/a/items/b/items/c/items/d/items',None),('/system/price/per',2),('/system/price/per',1e21),('/system/price/value/gp',0),('/system/price/sizeSensitive',False),('/system/traits/value',[]),('/system/traits/value/0','custom'),('/system/traits/otherTags',[]),('/system/slug',None),('/system/publication/remaster',False)]:
            with self.subTest(path=path):await self.read(kit(path,value))
        await self.read(kit('/system/items',present=False))

    async def test_strict_types_no_physical_expansion_or_mapping_forgery(self):
        for path,value in [('/system/items',{'a':{}}),('/system/items/a/quantity',True),('/system/items/a/quantity',0),('/system/items/a/quantity',1.5),('/system/items/a/uuid',None),('/system/items/a/isContainer',0),('/system/items/a~2/uuid','Item.a'),('/system/items//uuid','Item.a'),('/system/items/a/items/b/items/c/items/d/items',{}),('/system/items/a/items/b/items/c/items/d/items/e/uuid','Item.a'),('/system/price/per',0),('/system/price/value/gp',-1),('/system/price/value/gp',True),('/system/quantity',2),('/system/containerId','x'),('/system/traits/rarity','common'),('/system/traits/value',['custom'])]:
            with self.subTest(path=path),self.assertRaises(ToolError):await self.read(kit(path,value))
        for change in [lambda r:r['mapped'].update(value=False),lambda r:r['provenance'].update(mapping='pf2e.physical.source.v1'),lambda r:r['provenance'].update(limitations=[]),lambda r:r['raw'][0].update(document_uuid='Item.other'),lambda r:r.update(key='forged')]:
            bad=kit('/system/items',{});change(bad['records'][0])
            with self.assertRaises(ToolError):await self.read(bad)

    async def test_explicit_reference_claims_are_not_generated_inventory(self):
        for status in ('resolved','missing','denied','unsupported','unverified'):await self.read(reference(status=status))
        for path,claim,status in [('/system/items',{},'empty'),('/system/items/a/uuid','invalid uuid','unsupported')]:await self.read(reference(path,claim,status))
        missing=reference(status='missing');del missing['records'][0]['raw'][0]['value'];missing['records'][0]['raw'][0]['present']=False;await self.read(missing)
        synthetic=reference(claim='Scene.s.Token.t.Actor.a.Item.x',status='resolved');synthetic['records'][0]['mapped']['value']['token_uuid']='Scene.s.Token.t';await self.read(synthetic)
        for change in [lambda r:r['mapped']['value'].update(target_uuid='Item.other'),lambda r:r['mapped']['value'].update(name='x'*257),lambda r:r['mapped']['value'].update(token_uuid='Scene.s.Token.t'),lambda r:r['raw'][0].update(document_uuid='Item.other'),lambda r:r['provenance'].update(limitations=[]),lambda r:r.update(key='forged')]:
            bad=reference(status='resolved');change(bad['records'][0])
            with self.assertRaises(ToolError):await self.read(bad)

    async def test_actual_javascript_source_descriptors(self):
        script="""
import {kitFields} from './foundry-module/scripts/actorKit.js';
const source={type:'kit',system:{items:{'a/b~c':{uuid:'Item.x',img:'icon.webp',quantity:2,name:'Definition',isContainer:true,items:{nested:{uuid:'Item.x',img:'icon.webp',quantity:1,name:'Repeated',isContainer:false,items:null}}}},price:{value:{gp:2,sp:0},per:3,sizeSensitive:false},traits:{value:['custom'],otherTags:[]},slug:null,publication:{title:'Book',authors:'Author',license:'ORC',remaster:true}}};
console.log(JSON.stringify([...kitFields(source),...kitFields({type:'kit',system:{}})]));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1]);self.assertEqual(process.returncode,0,process.stderr)
        fields=json.loads(process.stdout);self.assertGreater(len(fields),20)
        for field in fields:
            with self.subTest(path=field['path']):
                result=kit(field['path'],field.get('value'),present=field['present']);row=result['records'][0];row['mapped']['concept']=field['concept'];row['provenance']['limitations']=field['limitations'];await self.read(result)

    async def test_actual_paginated_reader_preserves_duplicate_definitions(self):
        script=r"""
import {readItem} from './foundry-module/scripts/actors.js';
const entry={uuid:'Item.x',name:'Stored definition',img:'icon.webp',quantity:2,isContainer:false,items:null};
const source={name:'Kit',type:'kit',system:{items:{'a/b~c':entry,second:entry},price:{value:{gp:2},per:3},traits:{value:[],otherTags:[]},description:{value:'<p>Exact prose</p>',gm:'private_kit_sentinel'},quantity:999,equipped:{invested:true}},flags:{private:'private_kit_sentinel'}};
const item={id:'a',uuid:'Item.a',name:'Kit',type:'kit',documentName:'Item',parent:null,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
const component={id:'x',uuid:'Item.x',name:'Actual definition',type:'equipment',documentName:'Item',parent:null,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>{throw Error('Target source must not be read')}};
globalThis.game={version:'14.369',system:{id:'pf2e',version:'8.6.1'},ready:true,user:{isGM:true},actors:new Map(),items:new Map([['a',item],['x',component]])};globalThis.foundry={utils:{fromUuid:async uuid=>uuid==='Item.a'?item:component}};
let cursor;const pages=[];do{const page=await readItem({item_uuid:'Item.a',sections:['source','relationships'],limit:3,max_bytes:8000,...(cursor?{cursor}:{})});pages.push(page);cursor=page.pagination.next_cursor;}while(cursor);console.log(JSON.stringify(pages));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1]);self.assertEqual(process.returncode,0,process.stderr)
        pages=json.loads(process.stdout);self.assertGreater(len(pages),1);records=[]
        for page in pages:
            self.manager.call.return_value=page
            records.extend((await read_item.fn(item_uuid='Item.a',sections=['source','relationships']))['records'])
            self.assertNotIn('private_kit_sentinel',json.dumps(page))
        refs=[r for r in records if r['section']=='relationships'];self.assertEqual(len(refs),2)
        self.assertEqual({r['mapped']['value']['target_uuid'] for r in refs},{'Item.x'})
        self.assertEqual(len({r['raw'][0]['path'] for r in refs}),2)
        paths={r['raw'][0]['path'] for r in records}
        self.assertNotIn('/system/quantity',paths);self.assertNotIn('/system/equipped/invested',paths)

    async def test_actual_paginated_reader_crosses_strict_boundary(self):
        script=r"""
import {readItem} from './foundry-module/scripts/actors.js';
const source={name:'Kit',type:'kit',system:{items:{'a/b~c':{uuid:'Item.x',img:'icon.webp',quantity:2,name:'Definition',isContainer:true,items:{nested:{uuid:'Item.x',img:'icon.webp',quantity:1,name:'Repeated',isContainer:false,items:null}}}},price:{value:{gp:2},per:3,sizeSensitive:undefined},traits:{value:[],otherTags:[]},description:{value:'Exact prose'}}};
const item={documentName:'Item',uuid:'Item.a',id:'a',name:'Kit',type:'kit',parent:null,compendium:null,folder:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
const target={documentName:'Item',uuid:'Item.x',id:'x',name:'Definition',type:'equipment',parent:null,compendium:null,folder:null,testUserPermission:()=>true,toObject:()=>{throw Error('no target source');}};
globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map(),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>uuid==='Item.a'?item:uuid==='Item.x'?target:null}};
let cursor;const pages=[];do{const page=await readItem({item_uuid:'Item.a',sections:['source','relationships','description','effective'],limit:7,max_bytes:8000,...(cursor?{cursor}:{})});pages.push(page);cursor=page.pagination.next_cursor;}while(cursor);console.log(JSON.stringify(pages));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1]);self.assertEqual(process.returncode,0,process.stderr)
        from foundry_mcp_server.mcp_server.actors import _validate
        pages=json.loads(process.stdout);self.assertGreater(len(pages),3)
        for page in pages:_validate(page,'read',limit=7,max_bytes=8000,sections=['source','relationships','description','effective'])
        rows=[r for page in pages for r in page['records']]
        self.assertEqual(len(rows),len({r['key'] for r in rows}))
        links=[r for r in rows if r['mapped']['concept']=='kit_component_reference']
        self.assertEqual(len(links),2)
        self.assertTrue(all(r['mapped']['value']['target_uuid']=='Item.x' for r in links))
