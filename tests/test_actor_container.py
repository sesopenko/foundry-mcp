"""PF2e-specific container8.6.1 authored-source DTO boundary regressions."""
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_item, _container_spec
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_action import response


def container(path='/system/traits/rarity', value='common', *, present=True):
    result=response(path,value,item_type='backpack',present=present)
    row=result['records'][0];spec=_container_spec(path)
    row.update(key='source:'+path,mapped=dict(concept=spec[0] if spec else 'forged',value=value if present else None,unit=None))
    row['provenance'].update(mapping='pf2e.container.source.v1',limitations=['source_only_no_container_bulk_calculation'])
    return result


class ActorContainerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,result):
        self.manager.call.return_value=result
        return await read_item.fn(item_uuid='Item.a',sections=['source'])

    async def test_authored_values_and_absence(self):
        for path,value in [('/system/bulk/heldOrStowed',0),('/system/bulk/capacity',4),('/system/bulk/ignored',2),('/system/stowing',False),('/system/traits/value',[]),('/system/traits/value/0','custom'),('/system/traits/otherTags',[]),('/system/traits/otherTags/0','custom'),('/system/traits/rarity','custom'),('/system/slug',None),('/system/publication/title','Book'),('/system/publication/authors','Author'),('/system/publication/license','ORC'),('/system/publication/remaster',False)]:
            with self.subTest(path=path):await self.read(container(path,value))
        await self.read(container('/system/slug',present=False))

    async def test_strict_shapes_and_type_scope(self):
        for path,value in [('/system/bulk/capacity',True),('/system/stowing',0),('/system/collapsed',True),('/system/bulk/heldOrStowed',None),('/system/traits/value',['custom']),('/system/traits/value/00','bad'),('/system/traits/value',None),('/system/traits/otherTags',{}),('/system/slug',False),('/system/traits/rarity',None),('/system/publication/remaster',0),('/system/activation',{}),('/system/frequency/max',3),('/system/benefitsActive',True),('/system/uses',{})]:
            with self.subTest(path=path),self.assertRaises(ToolError):await self.read(container(path,value))
        for change in [lambda r:r['mapped'].update(concept='active_benefits'),lambda r:r['mapped'].update(value=False),lambda r:r['mapped'].update(unit='benefits'),lambda r:r['provenance'].update(mapping='pf2e.physical.source.v1'),lambda r:r['provenance'].update(limitations=[]),lambda r:r['raw'][0].update(document_uuid='Item.other'),lambda r:r['provenance']['contributors'][0].update(path='/system/slug'),lambda r:r.update(kind='relationship'),lambda r:r.update(key='forged')]:
            bad=container();change(bad['records'][0])
            with self.assertRaises(ToolError):await self.read(bad)
        bad=container();bad['identity']['type']='weapon'
        with self.assertRaises(ToolError):await self.read(bad)
        with self.assertRaises(ToolError):await self.read(container('/system/quantity',1))

    async def test_actual_selector_descriptors_cross_boundary(self):
        script=r"""
import {containerFields} from './foundry-module/scripts/actorContainer.js';
const source={type:'backpack',system:{traits:{value:['custom'],otherTags:[],rarity:'rare'},slug:null,publication:{title:'Book',authors:'Author',license:'ORC',remaster:true}}};
const fields=containerFields(source);source.system={};fields.push(...containerFields(source));console.log(JSON.stringify(fields));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(process.returncode,0,process.stderr)
        fields=json.loads(process.stdout);self.assertGreater(len(fields),15)
        for field in fields:
            with self.subTest(path=field['path']):
                result=container(field['path'],field.get('value'),present=field['present']);row=result['records'][0]
                row['mapped']['concept']=field['concept'];row['provenance']['limitations']=field['limitations']
                await self.read(result)


    async def test_containment_relationship_scope_and_strict_owner_boundaries(self):
        def relation(key,concept,raw,value,owned=True):
            result=container();result['sections']=[dict(name='relationships',status='complete',reasons=[])]
            if owned:result['identity'].update(uuid='Actor.owner.Item.a',actor=dict(uuid='Actor.owner',name='Owner'))
            result['records']=[dict(key='relationships:container:'+key,section='relationships',kind='relationship',raw=raw,mapped=dict(concept=concept,value=value,unit=None),provenance=dict(contributors=[{k:r[k] for k in ('document_uuid','path','basis')} for r in raw],mapping='pf2e.container.contents.v1',limitations=['stored_containment_not_effective_bulk']))]
            return result
        def claim(uuid,value,present=True):
            return dict(document_uuid=uuid,path='/system/containerId',present=present,basis='source',**({'value':value} if present else {}))
        async def read(result):
            self.manager.call.return_value=result
            return await read_item.fn(item_uuid=result['identity']['uuid'],sections=['relationships'],token_uuid=result['identity']['instance']['token_uuid'] if result['identity']['instance'] else None)
        for owned,status in [(False,'unverified'),(True,'empty'),(True,'denied')]:
            await read(relation('scope','container_contents',[],dict(status=status,target_uuid=None),owned))
        for value,status in [(None,'missing'),('ghost','missing'),('parent','denied'),('parent','unsupported')]:
            await read(relation('parent','container_parent',[claim('Actor.owner.Item.a',value)],dict(status=status,target_uuid=None,cycle=False)))
        for owned,status in [(True,'unverified'),(False,'empty'),(False,'denied')]:
            with self.assertRaises(ToolError):await read(relation('scope','container_contents',[],dict(status=status,target_uuid=None),owned))
        with self.assertRaises(ToolError):await read(relation('parent','container_parent',[claim('Actor.owner.Item.a','parent')],dict(status='unverified',target_uuid=None,cycle=False)))
        parent=relation('parent','container_parent',[claim('Actor.owner.Item.a','parent')],dict(status='resolved',target_uuid='Actor.owner.Item.parent',document_name='Item',type='backpack',name='Parent',name_truncated=False,cycle=True))
        await read(parent)
        child=relation('content:Actor.owner.Item.child','container_content',[claim('Actor.owner.Item.child','a')],dict(status='resolved',target_uuid='Actor.owner.Item.child',document_name='Item',type='weapon',name='Child',name_truncated=False,parent_uuid='Actor.owner.Item.a',parent_status='resolved',depth=1))
        await read(child)
        for mutation in [lambda r:r['mapped']['value'].update(target_uuid='Actor.other.Item.child'),lambda r:r['mapped']['value'].update(parent_uuid='Actor.other.Item.a'),lambda r:r['mapped']['value'].update(depth=True),lambda r:r['mapped']['value'].update(depth=0),lambda r:r['mapped']['value'].update(depth=2),lambda r:r['mapped']['value'].update(parent_status='inferred'),lambda r:r['mapped']['value'].update(type='spell'),lambda r:r['mapped']['value'].update(extra='bad'),lambda r:r['raw'][0].update(value='other'),lambda r:r['provenance'].update(limitations=[]),lambda r:r.update(key='relationships:container:content:Actor.owner.Item.fake')]:
            bad=json.loads(json.dumps(child));mutation(bad['records'][0])
            with self.assertRaises(ToolError):await read(bad)
        deeper=json.loads(json.dumps(child));deeper['records'][0]['raw'][0]['value']='nested';deeper['records'][0]['mapped']['value'].update(parent_uuid='Actor.owner.Item.nested',depth=2)
        await read(deeper)
        deeper['records'][0]['mapped']['value']['depth']=1
        with self.assertRaises(ToolError):await read(deeper)
        synthetic=json.loads(json.dumps(child));synthetic['identity']['instance']=dict(scene_uuid='Scene.s',scene_name='Scene',token_uuid='Scene.s.Token.t',token_name='Token',actor_link=True,base_actor=None);synthetic['identity']['source_kind']='token'
        with self.assertRaises(ToolError):await read(synthetic)
        synthetic['records'][0]['mapped']['value']['token_uuid']='Scene.s.Token.t';await read(synthetic)

    async def test_actual_reader_pages_preserve_nested_cycle_source_and_relationships(self):
        script=r"""
import {readItem} from './foundry-module/scripts/actors.js';
const actor={id:'owner',uuid:'Actor.owner',name:'Owner',type:'npc',documentName:'Actor',parent:null,items:new Map(),testUserPermission:()=>true};
function item(id,type,parent){const source={name:id,type,system:{containerId:parent,quantity:1,bulk:{value:1,heldOrStowed:0,capacity:4,ignored:2},stowing:true,traits:{value:[],otherTags:[],rarity:'common'},description:{value:''}}};const doc={id,uuid:actor.uuid+'.Item.'+id,name:id,type,documentName:'Item',parent:actor,compendium:null,folder:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};actor.items.set(id,doc);return doc;}
const root=item('a','backpack','nested');item('nested','backpack','a');item('child','equipment','nested');
globalThis.game={version:'14.369',system:{id:'pf2e',version:'8.6.1'},ready:true,user:{isGM:true},actors:new Map([['owner',actor]]),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>uuid===actor.uuid?actor:[...actor.items.values()].find(i=>i.uuid===uuid)}};
let cursor;const pages=[];do{const page=await readItem({item_uuid:root.uuid,sections:['source','relationships'],limit:4,max_bytes:8000,...(cursor?{cursor}:{})});pages.push(page);cursor=page.pagination.next_cursor;}while(cursor);console.log(JSON.stringify(pages));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(process.returncode,0,process.stderr)
        pages=json.loads(process.stdout);records=[];self.assertGreater(len(pages),1)
        for page in pages:
            self.manager.call.return_value=page
            result=await read_item.fn(item_uuid='Actor.owner.Item.a',sections=['source','relationships'])
            records.extend(result['records'])
        relations=[r for r in records if r['section']=='relationships'];contents=[r for r in relations if r['mapped']['concept']=='container_content']
        self.assertEqual(len(contents),2)
        self.assertEqual({r['mapped']['value']['target_uuid'] for r in contents},{'Actor.owner.Item.nested','Actor.owner.Item.child'})
        self.assertTrue(next(r for r in relations if r['mapped']['concept']=='container_parent')['mapped']['value']['cycle'])
        self.assertIn('containment_cycle',pages[-1]['sections'][-1]['reasons'])
