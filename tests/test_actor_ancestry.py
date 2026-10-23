"""PF2e-specific ancestry8.6.1 authored choices and ABC reference boundaries."""
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import AsyncMock
from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_item, _ancestry_spec
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_action import response


def ancestry(path='/system/hp',value=8,*,present=True):
    result=response(path,value,item_type='ancestry',present=present);row=result['records'][0]
    spec=_ancestry_spec(path)
    row.update(key='source:'+path,mapped=dict(concept=spec[0] if spec else 'forged',value=value if present else None,unit=None))
    row['provenance'].update(mapping='pf2e.ancestry.source.v1',limitations=['ancestry_source_not_effective_character'])
    return result


def reference(path='/system/items/a/uuid',claim='Item.feature',status='unverified'):
    result=ancestry(path,claim);result['sections'][0]['name']='relationships';row=result['records'][0]
    row.update(section='relationships',kind='relationship',key='relationships:ancestry:'+path,mapped=dict(concept='ancestry_feature_reference',value=dict(status=status,target_uuid=None),unit=None))
    row['provenance'].update(mapping='pf2e.ancestry.feature-reference.v1',limitations=['definition_reference_not_acquired_feature'])
    if status=='resolved':row['mapped']['value'].update(target_uuid=claim,document_name='Item',type='feat',name='Feature definition',name_truncated=False)
    return result


class ActorAncestryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,result):
        self.manager.call.return_value=result
        return await read_item.fn(item_uuid='Item.a',sections=[result['sections'][0]['name']])

    async def test_authored_choices_and_source_contributions(self):
        for path,value in [('/system/hp',8),('/system/speed',25),('/system/hands',0),('/system/reach',5),('/system/size','med'),('/system/vision','unknown'),('/system/boosts',{}),('/system/flaws',{}),('/system/boosts/a~1b~0c/value',[]),('/system/boosts/0/value/0','str'),('/system/boosts/0/selected',None),('/system/flaws/0/selected','dex'),('/system/alternateAncestryBoosts',None),('/system/alternateAncestryBoosts',[]),('/system/alternateAncestryBoosts/0','custom'),('/system/voluntary/legacy',False),('/system/voluntary/boost',None),('/system/voluntary/flaws/0','con'),('/system/languages/value',[]),('/system/languages/custom','Stored text'),('/system/additionalLanguages/count',0),('/system/additionalLanguages/value/0','custom'),('/system/items',{}),('/system/items/a~1b/uuid','Item.f'),('/system/items/a/img','icon.webp'),('/system/items/a/name','Stored'),('/system/items/a/level',0),('/system/items/a/level',1e21),('/system/slug',None),('/system/publication/remaster',True)]:
            with self.subTest(path=path):await self.read(ancestry(path,value))
        await self.read(ancestry('/system/hp',present=False))

    async def test_rejects_effective_physical_arbitrary_and_forged_values(self):
        for path,value in [('/system/hp',True),('/system/hp',None),('/system/boosts',{'x':{}}),('/system/boosts//selected',None),('/system/boosts/a~2/selected',None),('/system/boosts/a/value',['str']),('/system/boosts/a/value/00','str'),('/system/items/a/level',-1),('/system/items/a/level',0.5),('/system/items/a/uuid',None),('/system/items/a/items/b/uuid','Item.f'),('/system/quantity',1),('/system/level/value',1),('/system/equipped/invested',True),('/system/rules',[]),('/system/voluntary/legacy',0),('/system/alternateAncestryBoosts/0',None)]:
            with self.subTest(path=path),self.assertRaises(ToolError):await self.read(ancestry(path,value))
        for change in [lambda r:r['mapped'].update(value=True),lambda r:r['provenance'].update(mapping='pf2e.physical.source.v1'),lambda r:r['provenance'].update(limitations=[]),lambda r:r['raw'][0].update(document_uuid='Item.other'),lambda r:r.update(key='forged')]:
            bad=ancestry();change(bad['records'][0])
            with self.assertRaises(ToolError):await self.read(bad)

    async def test_feature_claims_are_immediate_definitions_only(self):
        for status in ('resolved','missing','denied','unsupported','unverified'):await self.read(reference(status=status))
        await self.read(reference('/system/items',{},'empty'))
        missing=reference(status='missing');del missing['records'][0]['raw'][0]['value'];missing['records'][0]['raw'][0]['present']=False;await self.read(missing)
        synthetic=reference(claim='Scene.s.Token.t.Actor.a.Item.x',status='resolved');synthetic['records'][0]['mapped']['value']['token_uuid']='Scene.s.Token.t';await self.read(synthetic)
        for change in [lambda r:r['mapped']['value'].update(target_uuid='Item.other'),lambda r:r['mapped']['value'].update(name='x'*257),lambda r:r['mapped']['value'].update(token_uuid='Scene.s.Token.t'),lambda r:r['mapped']['value'].update(acquired=True),lambda r:r['raw'][0].update(document_uuid='Item.other'),lambda r:r['provenance'].update(limitations=[]),lambda r:r.update(key='forged')]:
            bad=reference(status='resolved');change(bad['records'][0])
            with self.assertRaises(ToolError):await self.read(bad)

    async def test_actual_javascript_source_descriptors(self):
        script="""
import {ancestryFields} from './foundry-module/scripts/actorAncestry.js';
const source={type:'ancestry',system:{hp:8,size:'med',speed:25,hands:2,reach:5,vision:'normal',languages:{value:['common'],custom:''},additionalLanguages:{count:0,value:[],custom:''},boosts:{'a/b~c':{value:['str','dex'],selected:null}},flaws:{},alternateAncestryBoosts:null,voluntary:{legacy:false,boost:null,flaws:[]},items:{'a/b':{uuid:'Item.feature',img:'icon.webp',name:'Definition',level:1}},traits:{value:['human'],otherTags:[],rarity:'common'},slug:null,publication:{title:'Book',authors:'Author',license:'ORC',remaster:true}}};
console.log(JSON.stringify([...ancestryFields(source),...ancestryFields({type:'ancestry',system:{}})]));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1]);self.assertEqual(process.returncode,0,process.stderr)
        fields=json.loads(process.stdout);self.assertGreater(len(fields),30)
        for field in fields:
            with self.subTest(path=field['path']):
                result=ancestry(field['path'],field.get('value'),present=field['present']);row=result['records'][0];row['mapped']['concept']=field['concept'];row['provenance']['limitations']=field['limitations'];await self.read(result)

    async def test_actual_paginated_reader_preserves_definition_claims(self):
        script=r"""
import {readItem} from './foundry-module/scripts/actors.js';
const source={name:'Ancestry',type:'ancestry',system:{hp:8,size:'med',speed:25,hands:2,reach:5,vision:'normal',languages:{value:['common'],custom:'Exact custom text'},additionalLanguages:{count:0,value:[],custom:''},boosts:{'a/b~c':{value:['str','dex'],selected:null}},flaws:{},alternateAncestryBoosts:['str','wis'],voluntary:{legacy:true,boost:null,flaws:['con','dex']},items:{'a/b~c':{uuid:'Item.feature',name:'Stored name',img:'icon.webp',level:1},second:{uuid:'Item.feature',name:'Repeated definition',img:'icon.webp',level:5}},traits:{value:['human'],otherTags:[],rarity:'common'},description:{value:'<p>Exact definition prose</p>',gm:'ancestry_private_sentinel'},quantity:99},flags:{secret:'ancestry_private_sentinel'}};
const item={id:'a',uuid:'Item.a',name:'Ancestry',type:'ancestry',documentName:'Item',parent:null,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
const feature={id:'feature',uuid:'Item.feature',name:'Actual feature',type:'feat',documentName:'Item',parent:null,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>{throw Error('Target source must not be read')}};
globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map(),items:new Map([['a',item],['feature',feature]])};globalThis.foundry={utils:{fromUuid:async uuid=>uuid==='Item.a'?item:uuid==='Item.feature'?feature:null}};
let cursor;const pages=[];do{const page=await readItem({item_uuid:'Item.a',sections:['source','relationships','description','effective'],limit:5,max_bytes:8000,...(cursor?{cursor}:{})});pages.push(page);cursor=page.pagination.next_cursor;}while(cursor);console.log(JSON.stringify(pages));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1]);self.assertEqual(process.returncode,0,process.stderr)
        from foundry_mcp_server.mcp_server.actors import _validate
        pages=json.loads(process.stdout);self.assertGreater(len(pages),5)
        for page in pages:
            _validate(page,'read',limit=5,max_bytes=8000,sections=['source','relationships','description','effective'])
            self.assertNotIn('ancestry_private_sentinel',json.dumps(page))
        rows=[r for page in pages for r in page['records']]
        self.assertEqual(len(rows),len({r['key'] for r in rows}))
        links=[r for r in rows if r['mapped']['concept']=='ancestry_feature_reference']
        self.assertEqual(len(links),2)
        self.assertEqual({r['mapped']['value']['target_uuid'] for r in links},{'Item.feature'})
        self.assertEqual(len({r['raw'][0]['path'] for r in links}),2)
        self.assertNotIn('/system/quantity',{r['raw'][0]['path'] for r in rows})
