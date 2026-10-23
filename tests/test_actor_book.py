"""PF2e-specific book8.6.1 authored-source DTO boundary regressions."""
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_item, _book_spec
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_action import response


def book(path='/system/traits/rarity', value='common', *, present=True):
    result=response(path,value,item_type='book',present=present)
    row=result['records'][0];spec=_book_spec(path)
    row.update(key='source:'+path,mapped=dict(concept=spec[0] if spec else 'forged',value=value if present else None,unit=None))
    row['provenance'].update(mapping='pf2e.book.source.v1',limitations=['source_only_no_book_ownership_or_preparation'])
    return result


class ActorBookTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,result):
        self.manager.call.return_value=result
        return await read_item.fn(item_uuid='Item.a',sections=['source'])

    async def test_authored_values_and_absence(self):
        for path,value in [('/system/category','formula'),('/system/capacity',0),('/system/contents',[]),('/system/contents/0','Item.x'),('/system/category','coins'),('/system/category','custom'),('/system/traits/value',[]),('/system/traits/value/0','custom'),('/system/traits/otherTags',[]),('/system/traits/otherTags/0','custom'),('/system/traits/rarity','custom'),('/system/slug',None),('/system/publication/title','Book'),('/system/publication/authors','Author'),('/system/publication/license','ORC'),('/system/publication/remaster',False)]:
            with self.subTest(path=path):await self.read(book(path,value))
        await self.read(book('/system/slug',present=False))

    async def test_strict_shapes_and_type_scope(self):
        for path,value in [('/system/category',False),('/system/category',None),('/system/capacity',True),('/system/contents',None),('/system/contents',['Item.x']),('/system/stackGroup','coins'),('/system/usage/value','carried'),('/system/totalValue',100),('/system/traits/value',['custom']),('/system/traits/value/00','bad'),('/system/traits/value',None),('/system/traits/otherTags',{}),('/system/slug',False),('/system/traits/rarity',None),('/system/publication/remaster',0),('/system/activation',{}),('/system/frequency/max',3),('/system/benefitsActive',True),('/system/uses',{})]:
            with self.subTest(path=path),self.assertRaises(ToolError):await self.read(book(path,value))
        for change in [lambda r:r['mapped'].update(concept='active_benefits'),lambda r:r['mapped'].update(value=False),lambda r:r['mapped'].update(unit='benefits'),lambda r:r['provenance'].update(mapping='pf2e.physical.source.v1'),lambda r:r['provenance'].update(limitations=[]),lambda r:r['raw'][0].update(document_uuid='Item.other'),lambda r:r['provenance']['contributors'][0].update(path='/system/slug'),lambda r:r.update(kind='relationship'),lambda r:r.update(key='forged')]:
            bad=book();change(bad['records'][0])
            with self.assertRaises(ToolError):await self.read(bad)
        bad=book();bad['identity']['type']='weapon'
        with self.assertRaises(ToolError):await self.read(bad)
        with self.assertRaises(ToolError):await self.read(book('/system/quantity',1))

    async def test_actual_selector_descriptors_cross_boundary(self):
        script=r"""
import {bookFields} from './foundry-module/scripts/actorBook.js';
const source={type:'book',system:{category:'spell',capacity:2,contents:['Item.x','Item.x'],traits:{value:['custom'],otherTags:[],rarity:'rare'},slug:null,publication:{title:'Book',authors:'Author',license:'ORC',remaster:true}}};
const fields=bookFields(source);source.system={};fields.push(...bookFields(source));console.log(JSON.stringify(fields));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(process.returncode,0,process.stderr)
        fields=json.loads(process.stdout);self.assertGreater(len(fields),15)
        for field in fields:
            with self.subTest(path=field['path']):
                result=book(field['path'],field.get('value'),present=field['present']);row=result['records'][0]
                row['mapped']['concept']=field['concept'];row['provenance']['limitations']=field['limitations']
                await self.read(result)

    async def test_immediate_relationship_scope_and_canonical_targets(self):
        def relation(status='resolved', claim='Item.x'):
            result=response('/system/contents/0',claim,item_type='book',section='relationships')
            row=result['records'][0];raw=row['raw'][0]
            value=dict(status=status,target_uuid=claim,document_name='Item',type='spell',name='Definition',name_truncated=False) if status=='resolved' else dict(status=status,target_uuid=None)
            row.update(key='relationships:book:contents:0',kind='relationship',mapped=dict(concept='book_content_reference',value=value,unit=None),provenance=dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.book.content-reference.v1',limitations=['stored_book_contents_not_ownership_or_preparation']))
            return result
        async def read(result):
            self.manager.call.return_value=result
            return await read_item.fn(item_uuid='Item.a',sections=['relationships'])
        for status in ['resolved','missing','denied','unsupported','unverified']:
            await read(relation(status))
        synthetic=relation(claim='Scene.s.Token.t.Actor.a.Item.x');synthetic['records'][0]['mapped']['value']['token_uuid']='Scene.s.Token.t'
        await read(synthetic)
        for present in [False,True]:
            empty=relation();row=empty['records'][0];raw=row['raw'][0]
            raw.update(path='/system/contents',present=present)
            if present:raw['value']=[]
            else:raw.pop('value')
            row['key']='relationships:book:contents';row['mapped']['value']=dict(status='empty' if present else 'missing',target_uuid=None)
            row['provenance']['contributors'][0]['path']='/system/contents'
            await read(empty)
        for mutate in [lambda r:r['mapped']['value'].update(type='affliction'),lambda r:r['mapped']['value'].update(name='x'*257),lambda r:r['mapped']['value'].update(name_truncated=0),lambda r:r['mapped']['value'].update(target_uuid='Item.other'),lambda r:r['mapped']['value'].update(token_uuid='Scene.s.Token.t'),lambda r:r['raw'][0].update(document_uuid='Item.other'),lambda r:r.update(key='relationships:book:contents:1'),lambda r:r['raw'][0].update(path='/system/contents/00'),lambda r:r['provenance'].update(limitations=[]),lambda r:r['mapped'].update(concept='owned_spell')]:
            bad=relation();mutate(bad['records'][0])
            with self.assertRaises(ToolError):await read(bad)
        with self.assertRaises(ToolError):await read(relation(claim='spell name'))
        bad=relation('denied');bad['records'][0]['mapped']['value']['name']='hidden'
        with self.assertRaises(ToolError):await read(bad)

    async def test_actual_paginated_reader_source_and_relationships_match_boundary(self):
        script=r"""
import {readItem} from './foundry-module/scripts/actors.js';
const source={name:'Book',type:'book',system:{category:'spell',capacity:4,contents:['Item.spell','Item.spell','Item.gone'],quantity:1,description:{value:'Exact prose'}}};
const book={documentName:'Item',uuid:'Item.a',id:'a',name:'Book',type:'book',parent:null,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
const spell={documentName:'Item',uuid:'Item.spell',id:'spell',name:'Definition',type:'spell',parent:null,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>{throw Error('unselected target source');}};
globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map(),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>uuid==='Item.a'?book:uuid==='Item.spell'?spell:null}};
let cursor;const pages=[];do{const page=await readItem({item_uuid:'Item.a',sections:['source','relationships','description','effective'],limit:7,max_bytes:8000,...(cursor?{cursor}:{})});pages.push(page);cursor=page.pagination.next_cursor;}while(cursor);console.log(JSON.stringify(pages));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(process.returncode,0,process.stderr)
        from foundry_mcp_server.mcp_server.actors import _validate
        pages=json.loads(process.stdout)
        self.assertGreater(len(pages),3)
        for page in pages:
            _validate(page,'read',limit=7,max_bytes=8000,sections=['source','relationships','description','effective'])
        records=[r for page in pages for r in page['records']]
        self.assertEqual(len({r['key'] for r in records}),len(records))
        links=[r for r in records if r['mapped']['concept']=='book_content_reference']
        self.assertEqual([r['mapped']['value']['status'] for r in links],['resolved','resolved','missing'])
