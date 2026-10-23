"""PF2e-specific feat8.6.1 strict selected-source boundary regressions."""
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import AsyncMock
from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_item, _feat_spec, _validate
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_action import response


def feat_source(path='/system/category',value='classfeature',*,present=True):
    result=response(path,value,item_type='feat',present=present);row=result['records'][0]
    spec=_feat_spec(path);mapped=value if present else None
    if path=='/system/category' and present:
        mapped=dict(code=value,kind='feature' if value in ('ancestryfeature','calling','classfeature','curse','deityboon','pfsboon') else 'feat' if value in ('ancestry','bonus','class','general','skill') else 'unknown')
    row.update(key='source:'+path,mapped=dict(concept=spec[0] if spec else 'forged',value=mapped,unit=None))
    row['provenance'].update(mapping='pf2e.feat.source.v1',limitations=['feat_source_not_effective_benefit'])
    return result


def javascript(script):
    process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
    if process.returncode:raise AssertionError(process.stderr)
    return json.loads(process.stdout)


class ActorFeatTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,result):
        self.manager.call.return_value=result
        return await read_item.fn(item_uuid='Item.a',sections=['source'])

    async def test_categories_levels_activation_and_source_values(self):
        for code in ('ancestryfeature','calling','classfeature','curse','deityboon','pfsboon','ancestry','bonus','class','general','skill','custom'):
            await self.read(feat_source(value=code))
        for path,value in [('/system/level/value',1),('/system/level/value',30),('/system/level/taken',None),('/system/level/taken',7),('/system/actions/value',None),('/system/actions/value',3),('/system/actionType/value','passive'),('/system/actionType/value','custom'),('/system/location','feature-slot'),('/system/frequency',None),('/system/frequency/value',0),('/system/frequency/max',1),('/system/onlyLevel1',False),('/system/maxTakable',None),('/system/maxTakable',2),('/system/prerequisites/value/0/value','trained in Medicine'),('/system/subfeatures/proficiencies/a~1b~0c/rank',4),('/system/subfeatures/proficiencies/a/attribute',None),('/system/subfeatures/senses/a/range',5.5),('/system/subfeatures/senses/a/range',None),('/system/subfeatures/senses/a/special/llv',False),('/system/traits/toggles/mindshift',None),('/system/traits/toggles/mindshift/selected',True),('/system/selfEffect',None),('/system/selfEffect/name','Effect')]:
            with self.subTest(path=path,value=value):await self.read(feat_source(path,value))

    async def test_missing_and_empty_markers(self):
        for path in ('/system/frequency/value','/system/level/taken','/system/traits/toggles','/system/traits/toggles/mindshift','/system/subfeatures/languages','/system/subfeatures/senses/a/special','/system/subfeatures/senses/a/acuity'):
            await self.read(feat_source(path,present=False))
        for path in ('/system/prerequisites/value','/system/traits/value','/system/traits/otherTags','/system/subfeatures/keyOptions','/system/subfeatures/languages/granted','/system/subfeatures/suppressedFeatures'):
            await self.read(feat_source(path,[]))
        for path in ('/system/subfeatures/proficiencies','/system/subfeatures/senses'):
            await self.read(feat_source(path,{}))

    async def test_rejects_wrong_shapes_ranges_private_fields_and_forgery(self):
        for path,value in [('/system/level/value',0),('/system/level/taken',31),('/system/actions/value',0),('/system/actions/value',True),('/system/actions/value',1.5),('/system/frequency/max',0),('/system/maxTakable',0),('/system/subfeatures/proficiencies/a/rank',0),('/system/subfeatures/proficiencies/a/rank',5),('/system/subfeatures/senses/a/range',301),('/system/subfeatures/senses/a~2/range',30),('/system/prerequisites/value/00/value','x'),('/system/prerequisites/value/0','x'),('/system/prerequisites/value',['x']),('/system/traits/toggles',{}),('/system/subfeatures/languages',{}),('/system/subfeatures/proficiencies',{'a':{}}),('/system/subfeatures/senses/a/special',{}),('/system/frequency',{}),('/system/location',{}),('/system/quantity',1),('/system/rules',[]),('/flags/pf2e/itemGrants/a/id','local'),('/system/_migration/version',1)]:
            with self.subTest(path=path,value=value),self.assertRaises(ToolError):await self.read(feat_source(path,value))
        for change in [lambda r:r['mapped'].update(value='chosen_feat'),lambda r:r['mapped'].update(concept='feat_eligible'),lambda r:r['provenance'].update(limitations=[]),lambda r:r['provenance'].update(mapping='pf2e.class.source.v1'),lambda r:r['raw'][0].update(document_uuid='Item.other'),lambda r:r.update(key='forged')]:
            bad=feat_source();change(bad['records'][0])
            with self.assertRaises(ToolError):await self.read(bad)
        bad=feat_source('/system/actionType/value','passive');bad['records'][0]['mapped']['value']='passive_ability'
        with self.assertRaises(ToolError):await self.read(bad)

    async def test_actual_javascript_source_descriptors(self):
        fields=javascript("""
import {featFields} from './foundry-module/scripts/actorFeat.js';
const source={type:'feat',system:{category:'classfeature',level:{value:1,taken:null},onlyLevel1:false,maxTakable:null,actionType:{value:'passive'},actions:{value:null},location:null,prerequisites:{value:[{value:'Trained'}]},frequency:{value:0,max:1,per:'day'},traits:{value:['skill'],otherTags:[],rarity:'common',toggles:{mindshift:{selected:true}}},subfeatures:{keyOptions:[],languages:{slots:1,granted:['common']},suppressedFeatures:['Item.other'],proficiencies:{'a/b~c':{rank:2,attribute:null}},senses:{'a/b~c':{range:5.5,special:{ancestry:false,llv:true,second:false}}}},selfEffect:{uuid:'Item.effect',name:'Effect'},slug:null,publication:{title:'Book',authors:'Author',license:'ORC',remaster:true}}};
console.log(JSON.stringify([...featFields(source),...featFields({type:'feat',system:{}}),...featFields({type:'feat',system:{frequency:null,selfEffect:null,traits:{toggles:{mindshift:null}},subfeatures:{senses:{darkvision:{range:null}},proficiencies:{},suppressedFeatures:[]}}})]));
""")
        self.assertGreater(len(fields),80)
        for field in fields:
            with self.subTest(path=field['path']):
                result=feat_source(field['path'],field.get('value'),present=field['present']);row=result['records'][0]
                row['mapped'].update(concept=field['concept'],value=field.get('mapped_value',field.get('value')))
                row['provenance']['limitations']=field['limitations'];await self.read(result)

    async def test_actual_paginated_reader_dto(self):
        pages=javascript(r"""
import {readItem} from './foundry-module/scripts/actors.js';
const source={name:'Medicine',type:'feat',system:{category:'skill',level:{value:1,taken:2},actionType:{value:'action'},actions:{value:1},prerequisites:{value:[{value:'trained in Medicine'}]},frequency:{value:0,max:1,per:'day'},traits:{value:['skill'],otherTags:[],rarity:'common'},subfeatures:{proficiencies:{'a/b~c':{rank:2,attribute:null}},senses:{},suppressedFeatures:['Item.future']},description:{value:'<p>Toolkit; Treat Wounds; immunity.</p>',gm:'feat_private_sentinel'},rules:[{secret:'feat_private_sentinel'}],quantity:99},flags:{secret:'feat_private_sentinel'}};
const item={id:'a',uuid:'Item.a',name:'Medicine',type:'feat',documentName:'Item',parent:null,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map(),items:new Map([['a',item]])};globalThis.foundry={utils:{fromUuid:async uuid=>uuid==='Item.a'?item:null}};
let cursor;const pages=[];do{const page=await readItem({item_uuid:'Item.a',sections:['source','description','effective'],limit:5,max_bytes:8000,...(cursor?{cursor}:{})});pages.push(page);cursor=page.pagination.next_cursor;}while(cursor);console.log(JSON.stringify(pages));
""")
        self.assertGreater(len(pages),4)
        for page in pages:
            _validate(page,'read',limit=5,max_bytes=8000,sections=['source','description','effective'])
            self.assertNotIn('feat_private_sentinel',json.dumps(page))
        rows=[r for page in pages for r in page['records']];self.assertEqual(len(rows),len({r['key'] for r in rows}))
        fields={r['raw'][0]['path']:r for r in rows}
        self.assertEqual(fields['/system/category']['mapped']['value'],dict(code='skill',kind='feat'))
        self.assertEqual(fields['/system/level/value']['mapped']['value'],1)
        self.assertEqual(fields['/system/level/taken']['mapped']['value'],2)
        self.assertEqual(fields['/system/frequency/value']['mapped']['value'],0)
        self.assertEqual(fields['/system/subfeatures/proficiencies/a~1b~0c/rank']['mapped']['value'],2)
        self.assertNotIn('/system/quantity',fields)
        self.assertTrue(any('Toolkit' in r['raw'][0].get('value','') for r in rows if r['kind']=='text'))

    async def test_non_pf2e_boundary_and_published_contract(self):
        bad=feat_source();bad['runtime']['system_id']='other'
        with self.assertRaises(ToolError):await self.read(bad)
        for token in ('feat Items','{code,kind}','feat_source_not_effective_benefit','12000','Nominal level','activation codes'):
            self.assertIn(token,read_item.fn.__doc__)
