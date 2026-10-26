"""PF2e-specific8.6.1 serialized senses/languages/IWR boundary tests."""
import copy
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import AsyncMock
from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_actor
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_current import current


SCRIPT=r"""
import {creatureSupplementFields} from './foundry-module/scripts/actorCreatureCurrent.js';
const serialized={type:'npc',system:{perception:{senses:[{type:'darkvision',acuity:'precise',range:Infinity,source:null,label:'Darkvision'}]},details:{languages:{value:['common','custom-code'],details:'Only while conscious'}},attributes:{immunities:[{type:'custom',source:null,label:'Custom immunity',definition:['item:trait:mental'],exceptions:['visual']}],weaknesses:[{type:'fire',source:'Feature',label:'Fire weakness',value:5,exceptions:[{label:'Custom exception',definition:[{and:['a',{not:'b'}]}]}]}],resistances:[{type:'cold',source:null,label:'Cold resistance',value:7,exceptions:[],doubleVs:['non-magical',{label:'Doubled custom',definition:[{gt:['level',2]}]}]}]}}};
console.log(JSON.stringify(creatureSupplementFields(serialized)));
"""


def javascript(script):
    result=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
    if result.returncode:raise AssertionError(result.stderr)
    return json.loads(result.stdout)


class CreatureCurrentTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        selected=javascript(SCRIPT);cls.reasons=selected['reasons'];cls.rows=[]
        for field in selected['fields']:
            raw=dict(document_uuid='Actor.a',path=field['path'],present=field['present'],basis='transformed')
            if field['present']:raw['value']=field['value']
            value=field.get('value');value=None if value==[] and not field['path'].endswith('/definition') else value
            cls.rows.append(dict(key='statistics:'+field['path'],section='statistics',kind='field',raw=[raw],mapped=dict(concept=field['concept'],value=value,unit=None),provenance=dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.actor.creature-current.v1',limitations=field['limitations'])))

    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    def row(self,path):return copy.deepcopy(next(r for r in self.rows if r['raw'][0]['path']==path))

    def page(self,rows=None,reasons=None,actor_type='npc'):
        page=current(actor_type=actor_type);page['records']=copy.deepcopy(self.rows if rows is None else rows);page['sections'][0]['reasons']=self.reasons.copy() if reasons is None else reasons;page['pagination']['returned']=len(page['records']);return page

    async def read(self,page,**selectors):
        self.manager.call.return_value=page
        return await read_actor.fn(sections=['statistics'],limit=100,**(selectors or dict(actor_uuid='Actor.a')))

    async def test_actual_helper_preserves_infinity_languages_and_custom_predicates(self):
        for actor_type in ('character','npc'):await self.read(self.page(actor_type=actor_type))
        self.assertEqual(self.row('/system/perception/senses/0/range')['mapped']['value'],{'$number':'Infinity'})
        self.assertEqual(self.row('/system/attributes/resistances/0/doubleVs/1/definition')['mapped']['value'],[{'gt':['level',2]}])

    async def test_closed_fields_provenance_number_and_null_boundaries(self):
        original=self.row('/system/perception/senses/0/range')
        for value in (None,True,'Infinity',float('inf'),{'$number':'-Infinity'},{'$number':'Infinity','extra':1}):
            row=copy.deepcopy(original);row['raw'][0]['value']=value;row['mapped']['value']=value
            with self.subTest(value=value),self.assertRaises(ToolError):await self.read(self.page([row]))
        for change in [lambda r:r['raw'][0].update(document_uuid='Actor.other'),lambda r:r['raw'][0].update(basis='source'),lambda r:r['provenance'].update(limitations=[]),lambda r:r['mapped'].update(concept='effective_visibility')]:
            row=copy.deepcopy(original);change(row)
            with self.assertRaises(ToolError):await self.read(self.page([row]))
        for path in ('/system/perception/senses/200/range','/system/attributes/immunities/0/value','/system/attributes/weaknesses/0/doubleVs','/system/attributes/resistances/0/private'):
            row=copy.deepcopy(original);row['key']='statistics:'+path;row['raw'][0]['path']=path;row['provenance']['contributors'][0]['path']=path
            with self.assertRaises(ToolError):await self.read(self.page([row]))
        with self.assertRaises(ToolError):await self.read(self.page([original],actor_type='familiar'))

    async def test_predicate_grammar_depth_nodes_utf16_and_no_evaluation(self):
        original=self.row('/system/attributes/immunities/0/definition')
        valid=['a',*[dict([(op,['left',2])]) for op in ('eq','gt','gte','lt','lte')],*[dict([(op,['a','b'])]) for op in ('and','or','xor','nand','nor','iff')],{'not':'a'},{'if':'a','then':{'eq':['b','c']}}]
        row=copy.deepcopy(original);row['raw'][0]['value']=valid;row['mapped']['value']=valid;await self.read(self.page([row]))
        deep='a'
        for _ in range(8):deep={'not':deep}
        invalid=[[{'unknown':['a']}],[{'not':'a','private':1}],[{'if':'a'}],[{'eq':[1,2]}],[{'gt':['left',True]}],[''],[None],['x'*6001],['🙂'*3001],['a']*512,[deep]]
        for value in invalid:
            row=copy.deepcopy(original);row['raw'][0]['value']=value;row['mapped']['value']=value
            with self.subTest(value=str(value)[:60]),self.assertRaises(ToolError):await self.read(self.page([row]))
        for value in ([],None):
            row=copy.deepcopy(original);row['raw'][0]['value']=value;row['mapped']['value']=value;await self.read(self.page([row]))

    async def test_collection_and_discriminator_contradictions_and_diagnostics(self):
        language=self.row('/system/details/languages/value/0');root=copy.deepcopy(language)
        root['raw'][0].update(path='/system/details/languages/value',value=[]);root['key']='statistics:/system/details/languages/value';root['provenance']['contributors'][0]['path']='/system/details/languages/value';root['mapped']=dict(concept='current_languages',value=None,unit=None)
        await self.read(self.page([root]))
        with self.assertRaises(ToolError):await self.read(self.page([root,language]))
        definition=self.row('/system/attributes/immunities/0/definition');typ=self.row('/system/attributes/immunities/0/type');typ['raw'][0]['value']='fire';typ['mapped']['value']='fire'
        with self.assertRaises(ToolError):await self.read(self.page([typ,definition]))
        missing_type=copy.deepcopy(typ);missing_type['raw'][0].update(present=False);missing_type['raw'][0].pop('value');missing_type['mapped']['value']=None
        with self.assertRaises(ToolError):await self.read(self.page([missing_type,definition],[*self.reasons,'current_fields_unavailable']))
        await self.read(self.page([definition]))
        definition['raw'][0].update(present=False);definition['raw'][0].pop('value');definition['mapped']['value']=None
        with self.assertRaises(ToolError):await self.read(self.page([definition]))
        reasons=[*self.reasons,'current_fields_unavailable','custom_iwr_definition_unavailable'];await self.read(self.page([definition],reasons))
        reasons.remove('custom_iwr_definition_unavailable')
        with self.assertRaises(ToolError):await self.read(self.page([definition],reasons))
        with self.assertRaises(ToolError):await self.read(self.page([typ],['other_statistics_pending']))
        string=self.row('/system/attributes/immunities/0/exceptions/0');custom=self.row('/system/attributes/weaknesses/0/exceptions/0/label')
        path='/system/attributes/immunities/0/exceptions/0/label';custom['key']='statistics:'+path;custom['raw'][0]['path']=path;custom['provenance']['contributors'][0]['path']=path;custom['mapped']['concept']='current_immunity_exception_label'
        with self.assertRaises(ToolError):await self.read(self.page([string,custom]))

    async def test_actual_paginated_reader_shared_serialization_and_json_infinity(self):
        script=SCRIPT.replace('console.log(JSON.stringify(creatureSupplementFields(serialized)));','')+r"""
import {readActor} from './foundry-module/scripts/actors.js';
let transformed=0;
const source={type:'npc',name:'Creature',system:{}},actor={documentName:'Actor',id:'a',uuid:'Actor.a',name:'Creature',type:'npc',items:new Map(),folder:null,parent:null,compendium:null,testUserPermission:()=>true,toObject(flag){if(!flag){transformed++;return structuredClone(serialized);}return structuredClone(source);}};
globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map([['a',actor]]),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>uuid===actor.uuid?actor:null}};
await readActor({actor_uuid:actor.uuid});if(transformed!==0)throw Error('Default current serialization');
const pages=[];let cursor;
do{const page=await readActor({actor_uuid:actor.uuid,sections:['statistics'],limit:5,...(cursor?{cursor}:{})});pages.push(page);cursor=page.pagination.next_cursor;}while(cursor);
if(serialized.system.perception.senses[0].range!==Infinity)throw Error('Changed source range');
console.log(JSON.stringify(pages));
"""
        pages=javascript(script);self.assertGreater(len(pages),1);rows=[]
        for page in pages:rows.extend((await self.read(page))['records'])
        selected=[r for r in rows if r['provenance']['mapping']=='pf2e.actor.creature-current.v1']
        self.assertEqual({r['key']:r['raw'] for r in selected},{r['key']:r['raw'] for r in self.rows})
        self.assertTrue(any(r['provenance']['mapping']=='pf2e.actor.current.v1' for r in rows))
        self.assertTrue(any(r['mapped']['value']=={'$number':'Infinity'} for r in selected))
