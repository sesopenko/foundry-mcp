"""PF2e-specific deity8.6.1 authored options and spell reference boundaries."""
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import AsyncMock
from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_item, _deity_spec
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_action import response


def deity_source(path='/system/skill',value=None,*,present=True):
    result=response(path,value,item_type='deity',present=present);row=result['records'][0]
    spec=_deity_spec(path)
    row.update(key='source:'+path,mapped=dict(concept=spec[0] if spec else 'forged',value=value if present else None,unit=None))

    row['provenance'].update(mapping='pf2e.deity.source.v1',limitations=['deity_options_not_active_benefits'])
    return result


def reference(path='/system/spells/a',claim='Item.spell',status='unverified'):
    result=deity_source(path,claim);result['sections'][0]['name']='relationships';row=result['records'][0]
    row.update(section='relationships',kind='relationship',key='relationships:deity:'+path,mapped=dict(concept='deity_spell_reference',value=dict(status=status,target_uuid=None),unit=None))
    row['provenance'].update(mapping='pf2e.deity.spell-reference.v1',limitations=['listed_spell_not_learned_or_prepared'])
    if status=='resolved':row['mapped']['value'].update(target_uuid=claim,document_name='Item',type='spell',name='Feature definition',name_truncated=False)
    return result


class ActorDeityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,result):
        self.manager.call.return_value=result
        return await read_item.fn(item_uuid='Item.a',sections=[result['sections'][0]['name']])

    async def test_source_options_absence_and_empty_markers(self):
        for path,value in [('/system/category','philosophy'),('/system/sanctification',None),('/system/sanctification/modal','can'),('/system/sanctification/what',[]),('/system/sanctification/what/0','holy'),('/system/domains/primary',[]),('/system/domains/alternate/0','air'),('/system/font/0','heal'),('/system/attribute/0','str'),('/system/skill',None),('/system/skill',[]),('/system/skill/0','religion'),('/system/weapons/0','longsword'),('/system/spells',{}),('/system/spells/a~1b~0c','Item.spell'),('/system/traits/otherTags',[]),('/system/slug',None),('/system/publication/remaster',True)]:
            with self.subTest(path=path):await self.read(deity_source(path,value))
        await self.read(deity_source('/system/spells',present=False))

    async def test_rejects_invalid_shapes_private_and_physical_fields(self):
        for path,value in [('/system/sanctification',{}),('/system/skill/0',None),('/system/font/00','heal'),('/system/category',None),('/system/spells',{'a':'Item.spell'}),('/system/spells/a~2','Item.spell'),('/system/spells/a/uuid','Item.spell'),('/system/spells/a',None),('/system/traits/value',[]),('/system/traits/rarity','common'),('/system/quantity',1),('/system/rules',[]),('/system/attribute',['str']),('/system/publication/remaster',1)]:
            with self.subTest(path=path),self.assertRaises(ToolError):await self.read(deity_source(path,value))
        for change in [lambda r:r['mapped'].update(value={'active':True}),lambda r:r['provenance'].update(mapping='pf2e.class.source.v1'),lambda r:r['provenance'].update(limitations=[]),lambda r:r['raw'][0].update(document_uuid='Item.other'),lambda r:r.update(key='forged')]:
            bad=deity_source();change(bad['records'][0])
            with self.assertRaises(ToolError):await self.read(bad)

    async def test_spell_reference_status_identity_and_escaping(self):
        for status in ('resolved','missing','denied','unsupported','unverified'):await self.read(reference(status=status))
        await self.read(reference('/system/spells',{},'empty'))
        missing=reference('/system/spells',{},'missing');raw=missing['records'][0]['raw'][0];raw.pop('value');raw['present']=False;await self.read(missing)
        await self.read(reference('/system/spells/a~1b~0c',status='resolved'))
        synthetic=reference(claim='Scene.s.Token.t.Actor.a.Item.x',status='resolved');synthetic['records'][0]['mapped']['value']['token_uuid']='Scene.s.Token.t';await self.read(synthetic)
        for change in [lambda r:r['mapped']['value'].update(target_uuid='Item.other'),lambda r:r['mapped']['value'].update(type='feat'),lambda r:r['mapped']['value'].update(name='x'*257),lambda r:r['mapped']['value'].update(token_uuid='Scene.s.Token.t'),lambda r:r['mapped']['value'].update(prepared=True),lambda r:r['raw'][0].update(document_uuid='Item.other'),lambda r:r['provenance'].update(limitations=[]),lambda r:r.update(key='forged')]:
            bad=reference(status='resolved');change(bad['records'][0])
            with self.assertRaises(ToolError):await self.read(bad)
        for status in ('missing','denied','unsupported','unverified'):
            for leaked in ({'name':'Leaked'},{'document_name':'Item'},{'type':'spell'},{'target_uuid':'Item.spell'},{'token_uuid':'Scene.s.Token.t'}):
                bad=reference(status=status);bad['records'][0]['mapped']['value'].update(leaked)
                with self.subTest(status=status,leaked=leaked),self.assertRaises(ToolError):await self.read(bad)

    async def test_actual_javascript_source_descriptors(self):
        script="""
import {deityFields} from './foundry-module/scripts/actorDeity.js';
const source={type:'deity',system:{category:'philosophy',sanctification:{modal:'can',what:['holy']},domains:{primary:['air'],alternate:[]},font:['heal'],attribute:['str'],skill:null,weapons:['longsword'],spells:{'a/b~c':'Item.spell'},traits:{otherTags:[],value:['excluded'],rarity:'common'},slug:null,publication:{title:'Book',authors:'Author',license:'ORC',remaster:true}}};
console.log(JSON.stringify([...deityFields(source),...deityFields({type:'deity',system:{}}),...deityFields({type:'deity',system:{sanctification:null,skill:[],spells:{}}})]));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1]);self.assertEqual(process.returncode,0,process.stderr)
        fields=json.loads(process.stdout);self.assertGreater(len(fields),20)
        for field in fields:
            with self.subTest(path=field['path']):
                result=deity_source(field['path'],field.get('value'),present=field['present']);row=result['records'][0];row['mapped']['concept']=field['concept'];row['provenance']['limitations']=field['limitations'];row['mapped']['value']=field.get('mapped_value',field.get('value'));await self.read(result)

    async def test_actual_paginated_reader_preserves_spell_claims(self):
        script=r"""
import {readItem} from './foundry-module/scripts/actors.js';
const source={name:'Faith',type:'deity',system:{category:'pantheon',sanctification:{modal:'can',what:['holy']},domains:{primary:['air'],alternate:['fire']},font:['heal'],attribute:['str'],skill:['religion'],weapons:['longsword'],spells:{'a/b~c':'Item.spell',second:'Item.spell'},traits:{value:['excluded'],otherTags:[],rarity:'common'},description:{value:'<p>Exact faith prose</p>',gm:'deity_private_sentinel'},quantity:99},flags:{secret:'deity_private_sentinel'}};
const item={id:'a',uuid:'Item.a',name:'Faith',type:'deity',documentName:'Item',parent:null,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
const spell={id:'spell',uuid:'Item.spell',name:'Actual spell',type:'spell',documentName:'Item',parent:null,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>{throw Error('Target source must not be read')}};
globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map(),items:new Map([['a',item],['spell',spell]])};globalThis.foundry={utils:{fromUuid:async uuid=>uuid==='Item.a'?item:uuid==='Item.spell'?spell:null}};
let cursor;const pages=[];do{const page=await readItem({item_uuid:'Item.a',sections:['source','relationships','description','effective'],limit:5,max_bytes:8000,...(cursor?{cursor}:{})});pages.push(page);cursor=page.pagination.next_cursor;}while(cursor);console.log(JSON.stringify(pages));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1]);self.assertEqual(process.returncode,0,process.stderr)
        from foundry_mcp_server.mcp_server.actors import _validate
        pages=json.loads(process.stdout);self.assertGreater(len(pages),4)
        for page in pages:
            _validate(page,'read',limit=5,max_bytes=8000,sections=['source','relationships','description','effective'])
            self.assertNotIn('deity_private_sentinel',json.dumps(page))
        rows=[r for page in pages for r in page['records']]
        self.assertEqual(len(rows),len({r['key'] for r in rows}))
        links=[r for r in rows if r['mapped']['concept']=='deity_spell_reference']
        self.assertEqual(len(links),2)
        self.assertEqual({r['mapped']['value']['target_uuid'] for r in links},{'Item.spell'})
        self.assertEqual(len({r['raw'][0]['path'] for r in links}),2)
        self.assertNotIn('/system/quantity',{r['raw'][0]['path'] for r in rows})
        self.assertNotIn('/system/traits/rarity',{r['raw'][0]['path'] for r in rows})
        self.assertNotIn('/system/traits/value',{r['raw'][0]['path'] for r in rows})
    async def test_other_system_does_not_admit_pf2e_options(self):
        bad=deity_source('/system/category','philosophy');bad['runtime']['system_id']='other'
        with self.assertRaises(ToolError):await self.read(bad)

    async def test_published_description_contains_deity_contract(self):
        description=read_item.fn.__doc__
        for token in ('deity_spell_reference','relationships:deity:','200','12000','deity Items','target_uuid=null'):
            self.assertIn(token,description)
