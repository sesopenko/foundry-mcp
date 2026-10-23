"""PF2e-specific familiar8.6.1 source and relationship boundary regression checks."""
import copy
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_actor, _familiar_spec, FAMILIAR_LIMIT
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_character import character


def familiar(path,value,present=True,section='source'):
    page=character(path,value,present,section)
    page['identity']['type']='familiar'
    row=page['records'][0];spec=_familiar_spec(path)
    row['mapped']=dict(concept=spec[0] if spec else 'familiar_creature_description_source',value=value if present and section=='source' else None,unit=None)
    row['provenance'].update(mapping='pf2e.familiar.'+('notes' if section=='description' else 'source')+'.v1',limitations=list(FAMILIAR_LIMIT))
    return page


class FamiliarBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,page):
        self.manager.call.return_value=page
        return await read_actor.fn(actor_uuid='Actor.a',sections=[s['name'] for s in page['sections']])

    async def test_source_omissions_null_unknown_codes_and_large_integral_float(self):
        for path,value in [('/system/master/id',None),('/system/master/id','local'),('/system/master/ability','unknown'),('/system/master/ability',None),('/system/attributes/hp/value',0),('/system/attributes/hp/value',1e21),('/system/attributes/hp/temp',2),('/system/attributes/hp/tempSource','item')]:
            with self.subTest(path=path,value=value):await self.read(familiar(path,value))
        for path in ('/system/master/id','/system/master/ability','/system/attributes/hp/tempSource'):
            await self.read(familiar(path,None,False))

    async def test_invalid_source_types_paths_and_provenance(self):
        for path,value in [('/system/attributes/hp/value',True),('/system/attributes/hp/value',None),('/system/attributes/hp/value',-1),('/system/attributes/hp/value',0.5),('/system/attributes/hp/tempSource','  '),('/system/attributes/hp/max',30),('/system/master/level',2),('/system/abilities/str/mod',2),('/system/master/ability',3),('/system/details/creature/value','prose')]:
            with self.subTest(path=path,value=value),self.assertRaises(ToolError):await self.read(familiar(path,value))
        original=familiar('/system/master/ability','unknown')
        for mutate in [lambda p:p['records'][0]['provenance'].update(limitations=[]),lambda p:p['records'][0]['provenance'].update(mapping='pf2e.character.source.v1'),lambda p:p['records'][0]['raw'][0].update(document_uuid='Actor.other'),lambda p:p['records'][0]['mapped'].update(value='str')]:
            page=copy.deepcopy(original);mutate(page)
            with self.assertRaises(ToolError):await self.read(page)
        page=copy.deepcopy(original);page['runtime']['system_id']='other'
        with self.assertRaises(ToolError):await self.read(page)

    async def test_creature_description_exact_and_fragment_bound(self):
        await self.read(familiar('/system/details/creature/value','😀 exact',section='description'))
        await self.read(familiar('/system/details/creature/value',None,False,'description'))
        with self.assertRaises(ToolError):await self.read(familiar('/system/details/creature/value','x'*6001,section='description'))

    async def test_master_status_claim_and_followup_validation(self):
        for status,claim,present in [('missing',None,False),('missing','',True),('unassociated',None,True),('denied','m',True),('unsupported','m',True),('unverified','m',True),('missing','m',True),('resolved','m',True)]:
            page=familiar('/system/master/id',claim,present)
            row=page['records'][0]
            value=dict(status=status,target_uuid=None)
            if status=='resolved':value.update(target_uuid='Actor.m',document_name='Actor',type='character',name='Master',name_truncated=False,next_call=dict(tool='read_actor',arguments=dict(actor_uuid='Actor.m')))
            row.update(key='identity:familiar_master',section='identity',kind='relationship',mapped=dict(concept='familiar_master',value=value,unit=None))
            row['provenance'].update(mapping='pf2e.familiar.master.v1',limitations=['stored_master_reference_not_current_statistics'])
            page['sections']=[dict(name='identity',status='complete' if status=='resolved' else 'partial',reasons=[] if status=='resolved' else ['familiar_master_'+status])]
            await self.read(page)
            for mutate in [lambda p:p['sections'][0].update(reasons=['unrelated']),lambda p:p['records'][0]['raw'][0].update(document_uuid='Actor.other'),lambda p:p['records'][0]['mapped']['value'].update(target_uuid='Actor.guess')]:
                bad=copy.deepcopy(page);mutate(bad)
                with self.assertRaises(ToolError):await self.read(bad)
            if status=='resolved':
                bad=copy.deepcopy(page);bad['records'][0]['mapped']['value']['next_call']['arguments']['actor_uuid']='Actor.other'
                with self.assertRaises(ToolError):await self.read(bad)
            # Section diagnostics describe the whole snapshot, not only this page.
            page['records']=[];page['pagination']['returned']=0
            await self.read(page)

    async def test_actual_relationship_helper_descriptors(self):
        script=r"""
import {familiarMasterRelationship,familiarAbilityRecords} from './foundry-module/scripts/actorFamiliarRelationships.js';
const identity={uuid:'Actor.a',type:'familiar',document_name:'Actor',instance:null};
const item={id:'i',uuid:'Actor.a.Item.i',name:'Ability',type:'action',documentName:'Item',testUserPermission:()=>true,toObject:()=>({name:'😀'.repeat(257),type:'action',system:{traits:{value:['familiar','master','custom']}}})};
const actor={uuid:'Actor.a',type:'familiar',documentName:'Actor',items:new Map([['i',item]])};item.parent=actor;
globalThis.game={user:{isGM:true},actors:new Map()};
const target={identity,document:actor,token:null};
console.log(JSON.stringify({master:await familiarMasterRelationship(target,{path:'/system/master/id',present:true,value:null}),abilities:familiarAbilityRecords(target)}));
"""
        proc=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(proc.returncode,0,proc.stderr)
        data=json.loads(proc.stdout)
        for name,key in [('identity','master'),('abilities','abilities')]:
            page=familiar('/system/master/id',None)
            value=data[key];page['sections']=[dict(name=name,status='partial',reasons=value['reasons'])]
            page['records']=[value['record']] if key=='master' else value['records']
            page['pagination']['returned']=len(page['records'])
            await self.read(page)
            forged=copy.deepcopy(page);forged['records'][0]['provenance']['contributors']=[]
            with self.assertRaises(ToolError):await self.read(forged)
            if name=='abilities':
                for mutation in [lambda r:r['mapped']['value'].update(ability_kind='master_ability'),lambda r:r['raw'][2].update(path='/system/traits/value/1'),lambda r:r['mapped']['value'].update(target_uuid='Actor.other.Item.i')]:
                    forged=copy.deepcopy(page);mutation(forged['records'][0])
                    with self.assertRaises(ToolError):await self.read(forged)

    async def test_actual_paginated_reader_and_utf16_description(self):
        script=r"""
import {readActor} from './foundry-module/scripts/actors.js';
const prose='<p>😀 Exact familiar</p>'.repeat(700);
const source={name:'Familiar',type:'familiar',system:{master:{id:'m',ability:'unknown'},attributes:{hp:{value:1e21,temp:0,tempSource:'i',max:999}},details:{creature:{value:prose}}}};
const actor={id:'a',uuid:'Actor.a',name:'Familiar',type:'familiar',documentName:'Actor',folder:null,compendium:null,items:new Map(),testUserPermission:()=>true,toObject:()=>structuredClone(source)};
const master={id:'m',uuid:'Actor.m',name:'Master',type:'character',documentName:'Actor',folder:null,compendium:null,items:new Map(),testUserPermission:()=>true,toObject:()=>({name:'Master',type:'character',system:{}})};
for(let i=0;i<4;i++){
 const item={id:'i'+i,uuid:'Actor.a.Item.i'+i,name:'Ability '+i,type:'action',documentName:'Item',parent:actor,testUserPermission:()=>true,toObject:()=>({name:'Ability '+i,type:'action',system:{category:'familiar',traits:{value:i?['familiar','master','unknown']:[]}}})};actor.items.set(item.id,item);
}
const denied={id:'denied',type:'action',testUserPermission:()=>false};actor.items.set('denied',denied);
globalThis.game={version:'14.369',system:{id:'pf2e',version:'8.6.1'},ready:true,user:{isGM:true},items:new Map(),actors:new Map([['a',actor],['m',master]])};
globalThis.foundry={utils:{fromUuid:async uuid=>uuid==='Actor.m'?master:actor}};
const pages=[];let cursor=null;do{const page=await readActor({actor_uuid:'Actor.a',sections:['identity','source','description','abilities','statistics'],limit:2,...(cursor?{cursor}:{})});pages.push(page);cursor=page.pagination.next_cursor;}while(cursor);console.log(JSON.stringify(pages));
"""
        proc=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(proc.returncode,0,proc.stderr)
        pages=json.loads(proc.stdout)
        self.assertGreater(len(pages),5)
        for page in pages:await self.read(page)
        records=[r for page in pages for r in page['records']]
        master=[r for r in records if r['key']=='identity:familiar_master']
        self.assertEqual(len(master),1)
        self.assertEqual(master[0]['mapped']['value']['next_call'],dict(tool='read_actor',arguments=dict(actor_uuid='Actor.m')))
        notes=[r for r in records if r['section']=='description']
        self.assertGreater(len(notes),1)
        self.assertEqual(''.join(r['raw'][0]['value'] for r in notes),'<p>😀 Exact familiar</p>'*700)
        abilities=[r for r in records if r['section']=='abilities']
        self.assertEqual(len(abilities),5)
        self.assertTrue(all(r['mapped']['value']['ability_kind']=='unclassified' for r in abilities if r['mapped']['value']['status']=='resolved'))
        self.assertFalse(any(r['section']=='statistics' or any(raw['path']=='/system/attributes/hp/max' for raw in r['raw']) for r in records))
        self.assertTrue(all(next(s for s in p['sections'] if s['name']=='statistics')==dict(name='statistics',status='unsupported',reasons=['master_current_contract_pending']) for p in pages))
