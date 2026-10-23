"""PF2e-specific class8.6.1 authored choices and ABC reference boundaries."""
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import AsyncMock
from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_item, _class_spec
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_action import response


def class_source(path='/system/keyAbility/selected',value=None,*,present=True):
    result=response(path,value,item_type='class',present=present);row=result['records'][0]
    spec=_class_spec(path)
    row.update(key='source:'+path,mapped=dict(concept=spec[0] if spec else 'forged',value=value if present else None,unit=None))

    if spec and spec[1]=='rank' and present:row['mapped']['value']={'rank':value,'label':['Untrained','Trained','Expert','Master','Legendary'][int(value)]} if type(value) in (int,float) and value in range(5) else value
    row['provenance'].update(mapping='pf2e.class.source.v1',limitations=['class_source_not_effective_character'])
    return result


def reference(path='/system/items/a/uuid',claim='Item.feature',status='unverified'):
    result=class_source(path,claim);result['sections'][0]['name']='relationships';row=result['records'][0]
    row.update(section='relationships',kind='relationship',key='relationships:class:'+path,mapped=dict(concept='class_feature_reference',value=dict(status=status,target_uuid=None),unit=None))
    row['provenance'].update(mapping='pf2e.class.feature-reference.v1',limitations=['definition_reference_not_acquired_feature'])
    if status=='resolved':row['mapped']['value'].update(target_uuid=claim,document_name='Item',type='feat',name='Feature definition',name_truncated=False)
    return result


class ActorClassTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,result):
        self.manager.call.return_value=result
        return await read_item.fn(item_uuid='Item.a',sections=[result['sections'][0]['name']])

    async def test_source_contributions_starting_ranks_and_progression(self):
        for path,value in [('/system/keyAbility/value',[]),('/system/keyAbility/value/0','str'),('/system/keyAbility/selected',None),('/system/hp',8),('/system/hp',4.5),('/system/trainedSkills/value',[]),('/system/trainedSkills/value/0','arcana'),('/system/trainedSkills/additional',1e21),('/system/items',{}),('/system/items/a~1b~0c/uuid','Item.f'),('/system/items/a/img','icon.webp'),('/system/items/a/name','Stored'),('/system/items/a/level',0),('/system/items/a/level',1e21),('/system/ancestryFeatLevels/value',[]),('/system/classFeatLevels/value/0',2.5),('/system/generalFeatLevels/value/0',1e21),('/system/skillIncreaseLevels/value/0',3),('/system/traits/otherTags',[]),('/system/slug',None),('/system/publication/remaster',True)]:
            with self.subTest(path=path):await self.read(class_source(path,value))
        for path in ('perception','savingThrows/fortitude','savingThrows/reflex','savingThrows/will','attacks/simple','attacks/martial','attacks/advanced','attacks/unarmed','attacks/other/rank','defenses/unarmored','defenses/light','defenses/medium','defenses/heavy','spellcasting'):
            for rank in range(5):await self.read(class_source('/system/'+path,rank))
        await self.read(class_source('/system/attacks/other/name',present=False))
        await self.read(class_source('/system/perception',present=False))

    async def test_rejects_effective_physical_arbitrary_and_forged_values(self):
        for path,value in [('/system/keyAbility/selected',True),('/system/keyAbility/value/00','str'),('/system/attacks/other/name',None),('/system/hp',3),('/system/hp',13),('/system/perception',True),('/system/perception',0.5),('/system/perception',5),('/system/perception',-1),('/system/traits/value',[]),('/system/traits/value/0','fighter'),('/system/trainedSkills/additional',-1),('/system/trainedSkills/additional',0.5),('/system/trainedSkills/additional',True),('/system/items',{'x':{}}),('/system/items//uuid','Item.f'),('/system/items/a~2/uuid','Item.f'),('/system/items/a/level',-1),('/system/items/a/level',0.5),('/system/items/a/level',True),('/system/items/a/level',float('inf')),('/system/items/a/uuid',None),('/system/items/a/items/b/uuid','Item.f'),('/system/quantity',1),('/system/level/value',1),('/system/equipped/invested',True),('/system/rules',[]),('/system/classFeatLevels/value/0',0.5),('/system/classFeatLevels/value/0',True)]:
            with self.subTest(path=path),self.assertRaises(ToolError):await self.read(class_source(path,value))
        for change in [lambda r:r['mapped'].update(value=True),lambda r:r['provenance'].update(mapping='pf2e.physical.source.v1'),lambda r:r['provenance'].update(limitations=[]),lambda r:r['raw'][0].update(document_uuid='Item.other'),lambda r:r.update(key='forged')]:
            bad=class_source();change(bad['records'][0])
            with self.assertRaises(ToolError):await self.read(bad)
        for mapped in ({'rank':True,'label':'Trained'},{'rank':1,'label':'Expert'},{'rank':1,'label':'Trained','total':5},1):
            bad=class_source('/system/perception',1);bad['records'][0]['mapped']['value']=mapped
            with self.assertRaises(ToolError):await self.read(bad)
        bad=class_source('/system/hp',8);bad['records'][0]['mapped']['value']={'rank':8,'label':'Trained'}
        with self.assertRaises(ToolError):await self.read(bad)

    async def test_feature_claims_are_immediate_definitions_only(self):
        for status in ('resolved','missing','denied','unsupported','unverified'):await self.read(reference(status=status))
        await self.read(reference('/system/items',{},'empty'))
        missing=reference(status='missing');del missing['records'][0]['raw'][0]['value'];missing['records'][0]['raw'][0]['present']=False;await self.read(missing)
        synthetic=reference(claim='Scene.s.Token.t.Actor.a.Item.x',status='resolved');synthetic['records'][0]['mapped']['value']['token_uuid']='Scene.s.Token.t';await self.read(synthetic)
        for change in [lambda r:r['mapped']['value'].update(target_uuid='Item.other'),lambda r:r['mapped']['value'].update(name='x'*257),lambda r:r['mapped']['value'].update(token_uuid='Scene.s.Token.t'),lambda r:r['mapped']['value'].update(acquired=True),lambda r:r['raw'][0].update(document_uuid='Item.other'),lambda r:r['provenance'].update(limitations=[]),lambda r:r.update(key='forged')]:
            bad=reference(status='resolved');change(bad['records'][0])
            with self.assertRaises(ToolError):await self.read(bad)

    async def test_unresolved_relationships_never_disclose_target_identity(self):
        for status in ('missing','denied','unsupported','unverified'):
            for leaked in ({'name':'Leaked'}, {'document_name':'Item'}, {'type':'feat'}, {'target_uuid':'Item.feature'}, {'token_uuid':'Scene.s.Token.t'}):
                bad=reference(status=status);bad['records'][0]['mapped']['value'].update(leaked)
                with self.subTest(status=status,leaked=leaked),self.assertRaises(ToolError):await self.read(bad)
        absent=reference('/system/items',{},'missing');raw=absent['records'][0]['raw'][0];raw.pop('value');raw['present']=False
        await self.read(absent)

    async def test_actual_javascript_source_descriptors(self):
        script="""
import {classFields} from './foundry-module/scripts/actorClass.js';
const source={type:'class',system:{keyAbility:{value:['str','dex'],selected:null},hp:8,perception:1,savingThrows:{fortitude:2,reflex:1,will:1},attacks:{simple:1,other:{name:'',rank:0}},defenses:{light:1},spellcasting:0,trainedSkills:{value:['arcana'],additional:2},classFeatLevels:{value:[1,2.5,4]},skillIncreaseLevels:{value:[]},items:{'a/b':{uuid:'Item.feature',img:'icon.webp',name:'Definition',level:1}},traits:{value:['human'],otherTags:[],rarity:'common'},slug:null,publication:{title:'Book',authors:'Author',license:'ORC',remaster:true}}};
console.log(JSON.stringify([...classFields(source),...classFields({type:'class',system:{}})]));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1]);self.assertEqual(process.returncode,0,process.stderr)
        fields=json.loads(process.stdout);self.assertGreater(len(fields),20)
        for field in fields:
            with self.subTest(path=field['path']):
                result=class_source(field['path'],field.get('value'),present=field['present']);row=result['records'][0];row['mapped']['concept']=field['concept'];row['provenance']['limitations']=field['limitations'];row['mapped']['value']=field.get('mapped_value',field.get('value'));await self.read(result)

    async def test_actual_paginated_reader_preserves_definition_claims(self):
        script=r"""
import {readItem} from './foundry-module/scripts/actors.js';
const source={name:'Class',type:'class',system:{keyAbility:{value:['str','dex'],selected:null},hp:8,perception:1,savingThrows:{fortitude:2,reflex:1,will:1},attacks:{simple:1,other:{name:'',rank:0}},defenses:{light:1},spellcasting:0,trainedSkills:{value:['arcana'],additional:2},classFeatLevels:{value:[1,2.5,4]},skillIncreaseLevels:{value:[]},items:{'a/b~c':{uuid:'Item.feature',name:'Stored name',img:'icon.webp',level:1},second:{uuid:'Item.feature',name:'Repeated definition',img:'icon.webp',level:5}},traits:{value:['human'],otherTags:[],rarity:'common'},description:{value:'<p>Exact definition prose</p>',gm:'class_private_sentinel'},quantity:99},flags:{secret:'class_private_sentinel'}};
const item={id:'a',uuid:'Item.a',name:'Class',type:'class',documentName:'Item',parent:null,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
const feature={id:'feature',uuid:'Item.feature',name:'Actual feature',type:'feat',documentName:'Item',parent:null,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>{throw Error('Target source must not be read')}};
globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map(),items:new Map([['a',item],['feature',feature]])};globalThis.foundry={utils:{fromUuid:async uuid=>uuid==='Item.a'?item:uuid==='Item.feature'?feature:null}};
let cursor;const pages=[];do{const page=await readItem({item_uuid:'Item.a',sections:['source','relationships','description','effective'],limit:5,max_bytes:8000,...(cursor?{cursor}:{})});pages.push(page);cursor=page.pagination.next_cursor;}while(cursor);console.log(JSON.stringify(pages));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1]);self.assertEqual(process.returncode,0,process.stderr)
        from foundry_mcp_server.mcp_server.actors import _validate
        pages=json.loads(process.stdout);self.assertGreater(len(pages),5)
        for page in pages:
            _validate(page,'read',limit=5,max_bytes=8000,sections=['source','relationships','description','effective'])
            self.assertNotIn('class_private_sentinel',json.dumps(page))
        rows=[r for page in pages for r in page['records']]
        self.assertEqual(len(rows),len({r['key'] for r in rows}))
        links=[r for r in rows if r['mapped']['concept']=='class_feature_reference']
        self.assertEqual(len(links),2)
        self.assertEqual({r['mapped']['value']['target_uuid'] for r in links},{'Item.feature'})
        self.assertEqual(len({r['raw'][0]['path'] for r in links}),2)
        self.assertNotIn('/system/quantity',{r['raw'][0]['path'] for r in rows})
