"""PF2e action source, activation and self-effect MCP boundary regressions."""
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from fastmcp.exceptions import ToolError

from foundry_mcp_server.mcp_server.actors import read_item
from foundry_mcp_server.mcp_server.tools import register_foundry_manager


def response(path='/system/actionType/value',value='passive',*,present=True,item_type='action',mapped=None,section='source'):
    raw=dict(document_uuid='Item.a',path=path,present=present,basis='source')
    if present:raw['value']=value
    mapping={'action':'action_or_activity','free':'free_action','reaction':'reaction','passive':'passive_ability'}
    expected=mapping.get(value,value) if path=='/system/actionType/value' and isinstance(value,str) else value
    record=dict(key='source.field',section=section,kind='field',raw=[raw],mapped=dict(concept='activation_kind',value=expected if mapped is None else mapped,unit=None),provenance=dict(contributors=[{key:raw[key] for key in ('document_uuid','path','basis')}],mapping='pf2e.action.source.v1',limitations=[]))
    return dict(contract_version=1,runtime=dict(core_version='14.369',system_id='pf2e',system_version='8.6.1'),identity=dict(document_name='Item',id='a',uuid='Item.a',name='Action',type=item_type,source_kind='world',folder=None,pack=None,actor=None,instance=None),revision='revision',sections=[dict(name=section,status='complete',reasons=[])],records=[record],pagination=dict(complete=True,next_cursor=None,returned=1),limitations=[])


def relationship(status='unverified',target_uuid=None):
    result=response(section='relationships');record=result['records'][0]
    record.update(key='relationships:selfEffect',kind='relationship',raw=[dict(document_uuid='Item.a',path='/system/selfEffect/'+key,present=True,value=value,basis='source') for key,value in [('uuid','Item.effect'),('name','Effect')]],mapped=dict(concept='self_effect',value=dict(target_uuid=target_uuid,status=status),unit=None))
    record['provenance'].update(mapping='pf2e.action.self_effect.v1',contributors=[{key:raw[key] for key in ('document_uuid','path','basis')} for raw in record['raw']])
    return result


class ActorActionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,result,section='source'):
        self.manager.call.return_value=result
        return await read_item.fn(item_uuid='Item.a',sections=[section])

    async def test_activation_discriminator_survives_null_count_and_unknown_code(self):
        for code,label in [('passive','passive_ability'),('free','free_action'),('reaction','reaction'),('action','action_or_activity'),('custom','custom')]:
            result=await self.read(response(value=code));self.assertEqual(result['records'][0]['mapped']['value'],label)
            result=await self.read(response('/system/actions/value',None));self.assertIsNone(result['records'][0]['raw'][0]['value'])
        with self.assertRaises(ToolError):await self.read(response(value='reaction',mapped='free_action'))

    async def test_nullable_optional_records_zero_frequency_and_traits_are_source(self):
        for path,value in [('/system/frequency',None),('/system/selfEffect',None),('/system/frequency/value',0),('/system/frequency/max',3),('/system/frequency/per','day'),('/system/traits/value',[]),('/system/traits/value/0','custom-trait'),('/system/traits/otherTags',[]),('/system/category',None),('/system/publication/remaster',False)]:
            with self.subTest(path=path):self.assertEqual((await self.read(response(path,value)))['records'][0]['raw'][0]['value'],value)
        missing=response('/system/frequency/value',None,present=False)
        self.assertNotIn('value',(await self.read(missing))['records'][0]['raw'][0])

    async def test_schema_types_private_paths_and_other_item_boundaries(self):
        for path,value in [('/system/actions/value',True),('/system/deathNote',0),('/system/frequency',{}),('/system/selfEffect',{}),('/system/frequency/value',None),('/system/traits/value',['secret']),('/system/traits/value/0',0),('/system/traits/value/00','bad-index'),('/system/traits/private',[]),('/system/publication/remaster','false'),('/system/_migration',{}),('/flags/secret','never')]:
            with self.subTest(path=path),self.assertRaises(ToolError):await self.read(response(path,value))
        with self.assertRaises(ToolError):await self.read(response(item_type='spell'))

    async def test_named_relationship_retains_origin_and_canonical_resolution_only(self):
        for status,target in [('unverified',None),('missing',None),('denied',None),('unsupported',None),('resolved','Item.effect')]:
            result=await self.read(relationship(status,target),'relationships')
            self.assertEqual(result['records'][0]['raw'][0]['document_uuid'],'Item.a')
            self.assertEqual(result['records'][0]['mapped']['value']['target_uuid'],target)
        for result in [relationship('denied','Item.effect'),relationship('resolved',None),relationship('resolved','Effect name'),relationship('unknown',None)]:
            with self.assertRaises(ToolError):await self.read(result,'relationships')
        result=relationship();result['records'][0]['provenance']['contributors'][0]['document_uuid']='Item.effect'
        with self.assertRaises(ToolError):await self.read(result,'relationships')
        synthetic=relationship('resolved','Scene.s.Token.t.Actor.a.Item.effect')
        synthetic['records'][0]['mapped']['value']['token_uuid']='Scene.s.Token.t'
        await self.read(synthetic,'relationships')
        for status,target,token in [('resolved','Scene.s.Token.t.Actor.a.Item.effect',None),('resolved','Scene.s.Token.t.Actor.a.Item.effect','Scene.s.Token.wrong'),('resolved','Item.effect','Scene.s.Token.t'),('missing',None,'Scene.s.Token.t')]:
            bad=relationship(status,target)
            if token is not None:bad['records'][0]['mapped']['value']['token_uuid']=token
            with self.subTest(target=target,token=token),self.assertRaises(ToolError):await self.read(bad,'relationships')
        result=relationship();result['records'][0]['mapped']['value']['secret']='never'
        with self.assertRaises(ToolError):await self.read(result,'relationships')

    async def test_actual_browser_source_relationship_and_description_dtos(self):
        script=r"""
import {readItem} from './foundry-module/scripts/actors.js';
const description='<p>Reaction 😀 requirements &amp; exceptions</p>'.repeat(700);
const source={name:'Action',type:'action',system:{actionType:{value:'reaction'},actions:{value:null},category:'familiar',frequency:{value:0,max:3,per:'day'},selfEffect:{uuid:'Item.effect',name:'Stored effect'},traits:{value:['custom-trait'],otherTags:[]},publication:{title:'Test',authors:'Author',license:'ORC',remaster:true},description:{value:description,gm:'never'},rules:[{secret:'never'}]},flags:{private:'never'}};
const make=(id,type,source)=>({id,uuid:`Item.${id}`,name:source.name,type,documentName:'Item',parent:null,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)});
const action=make('a','action',source);const effect=make('effect','effect',{name:'Actual effect',type:'effect',system:{}});
const docs=new Map([[action.uuid,action],[effect.uuid,effect]]);
let resolutions=[];
globalThis.game={version:'14.369',system:{id:'pf2e',version:'8.6.1'},ready:true,user:{isGM:true},actors:new Map(),items:docs};globalThis.foundry={utils:{fromUuid:async uuid=>{resolutions.push(uuid);return docs.get(uuid);}}};
const sourcePages=[];let cursor;
do{const page=await readItem({item_uuid:'Item.a',sections:['source'],limit:10,max_bytes:8000,...(cursor?{cursor}:{})});sourcePages.push(page);cursor=page.pagination.next_cursor;}while(cursor);
const sourceResolutions=[...resolutions];
const unsupported=await readItem({item_uuid:'Item.a',sections:['effective']});
const relationships=await readItem({item_uuid:'Item.a',sections:['relationships']});
const base={uuid:'Actor.base',id:'base',documentName:'Actor',type:'npc',name:'Base',folder:null,compendium:null,testUserPermission:()=>true};
const scene={uuid:'Scene.s',id:'s',documentName:'Scene',name:'Scene',testUserPermission:()=>true};
const owner={...base,uuid:'Scene.s.Token.t.Actor.base',items:new Map()};
const token={uuid:'Scene.s.Token.t',id:'t',documentName:'Token',name:'Token',parent:scene,actor:owner,baseActor:base,isLinked:false,testUserPermission:()=>true};owner.token=token;
const syntheticEffect={...effect,id:'fx',uuid:'Scene.s.Token.t.Actor.base.Item.fx',parent:owner};owner.items.set('fx',syntheticEffect);
docs.set(token.uuid,token);docs.set(syntheticEffect.uuid,syntheticEffect);source.system.selfEffect.uuid=syntheticEffect.uuid;
const syntheticRelationship=await readItem({item_uuid:'Item.a',sections:['relationships']});
const selector=syntheticRelationship.records[0].mapped.value;
const syntheticFollowup=await readItem({item_uuid:selector.target_uuid,token_uuid:selector.token_uuid,sections:['identity']});
const textPages=[];
do{const page=await readItem({item_uuid:'Item.a',sections:['description'],limit:2,max_bytes:8000,...(cursor?{cursor}:{})});textPages.push(page);cursor=page.pagination.next_cursor;}while(cursor);
console.log(JSON.stringify({sourcePages,relationships,syntheticRelationship,syntheticFollowup,textPages,description,sourceResolutions,unsupported}));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(process.returncode,0,process.stderr)
        fixture=json.loads(process.stdout);records=[]
        self.assertNotIn('Item.effect',fixture['sourceResolutions'])
        unsupported=await self.read(fixture['unsupported'],'effective')
        self.assertEqual(unsupported['sections'][0]['status'],'unsupported')
        self.assertEqual(unsupported['records'],[])
        for page in fixture['sourcePages']:
            records.extend((await self.read(page))['records']);self.assertNotIn('never',json.dumps(page))
        fields={r['raw'][0]['path']:r for r in records}
        self.assertEqual(fields['/system/actionType/value']['mapped']['value'],'reaction')
        self.assertIsNone(fields['/system/actions/value']['raw'][0]['value'])
        self.assertEqual(fields['/system/frequency/value']['raw'][0]['value'],0)
        relation=await self.read(fixture['relationships'],'relationships')
        self.assertEqual(relation['records'][0]['mapped']['value'],dict(status='resolved',target_uuid='Item.effect'))
        synthetic=await self.read(fixture['syntheticRelationship'],'relationships')
        selector=synthetic['records'][0]['mapped']['value']
        self.assertEqual(selector,dict(status='resolved',target_uuid='Scene.s.Token.t.Actor.base.Item.fx',token_uuid='Scene.s.Token.t'))
        self.manager.call.return_value=fixture['syntheticFollowup']
        followup=await read_item.fn(item_uuid=selector['target_uuid'],token_uuid=selector['token_uuid'],sections=['identity'])
        self.assertEqual(followup['identity']['instance']['token_uuid'],'Scene.s.Token.t')
        fragments=[]
        for page in fixture['textPages']:
            fragments.extend(record['raw'][0]['value'] for record in (await self.read(page,'description'))['records'])
        self.assertEqual(''.join(fragments),fixture['description'])
