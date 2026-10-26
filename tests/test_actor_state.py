"""PF2e-specific8.6.1 integrated stored state, with application unknown."""
import copy
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import AsyncMock
from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_actor
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_casting import casting


SCRIPT=r"""
import {readActor} from './foundry-module/scripts/actors.js';
const docs=new Map(),actor={documentName:'Actor',uuid:'Actor.a',id:'a',name:'Actor',type:'npc',items:new Map(),folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>({type:'npc',name:'Actor',system:{}})};docs.set(actor.uuid,actor);
const add=(id,type,system,readable=true)=>{const source={type,name:'Same name',system};const item={documentName:'Item',uuid:`Actor.a.Item.${id}`,id,name:'Prepared name',type,parent:actor,folder:null,compendium:null,testUserPermission:()=>readable,toObject:()=>{if(!readable)throw Error('denied source');return structuredClone(source);}};actor.items.set(id,item);docs.set(item.uuid,item);return item;};
add('c','condition',{value:{isValued:true,value:2},persistent:{formula:'1d6',damageType:'fire',dc:15,criticalHit:false},references:{parent:{id:'e'},children:[{id:'missing',type:'condition'}],overrides:[],overriddenBy:[]},overrides:['frightened']});
add('e','effect',{level:{value:1},duration:{value:-1,unit:'encounter',expiry:'turn-end',sustained:false},start:{value:0,initiative:null},badge:{type:'formula',value:'1d4',evaluate:false,reevaluate:null},context:{origin:{actor:'Actor.a',token:null,item:'Actor.a.Item.c'},target:null}});
add('hidden','condition',{},false);add('aff','affliction',{stage:999});
globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map([['a',actor]]),items:new Map()};
globalThis.foundry={utils:{fromUuid:async uuid=>docs.get(uuid)}};
const pages=[];let cursor;
do{const page=await readActor({actor_uuid:actor.uuid,sections:['state'],limit:5,...(cursor?{cursor}:{})});pages.push(page);cursor=page.pagination.next_cursor;}while(cursor);
actor.items.clear();const empty=await readActor({actor_uuid:actor.uuid,sections:['state']});
console.log(JSON.stringify({pages,empty}));
"""


class ActorStateTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        result=subprocess.run(['node','--input-type=module'],input=SCRIPT,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        if result.returncode:raise AssertionError(result.stderr)
        cls.fixture=json.loads(result.stdout)

    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,page,**selectors):
        self.manager.call.return_value=page
        return await read_actor.fn(sections=['state'],**(selectors or dict(actor_uuid='Actor.a')),limit=5 if len(page['records'])<=5 else 100)

    def page(self,rows):
        page=copy.deepcopy(self.fixture['empty']);page['records']=copy.deepcopy(rows);page['pagination']['returned']=len(rows)
        page['sections'][0]['reasons']=['effective_application_not_evaluated','affliction_reading_unsupported','unresolved_state_references','state_items_denied']
        return page

    def rows(self):return [r for p in self.fixture['pages'] for r in p['records']]

    async def test_actual_paginated_javascript_state_and_explicit_empty_capability(self):
        self.assertGreater(len(self.fixture['pages']),1)
        for page in self.fixture['pages']:await self.read(page)
        await self.read(self.fixture['empty'])
        rows=self.rows();items=[r for r in rows if r['key'].startswith('state:item:')]
        self.assertEqual(len(items),2);self.assertEqual(len({r['key'] for r in rows}),len(rows))
        self.assertTrue(all(r['mapped']['value']['application']=='unknown' and r['mapped']['value']['name']=='Same name' for r in items))
        self.assertNotIn('hidden',json.dumps(rows));self.assertFalse(any(r['raw'] and '.Item.aff' in r['raw'][0]['document_uuid'] for r in rows))
        self.assertEqual([r['key'] for r in self.fixture['empty']['records']],['state:capability:affliction'])
        self.assertTrue(any(r['mapped']['concept']=='effect_badge_value' and r['mapped']['value']=='1d4' for r in rows))
        self.assertTrue(any(r['key']=='state:condition:Actor.a.Item.c:/system/references/parent/id' and r['mapped']['value']['target_uuid']=='Actor.a.Item.e' for r in rows))

    async def test_forged_owner_type_identity_application_and_provenance_rejected(self):
        original=next(r for r in self.rows() if r['key']=='state:item:Actor.a.Item.c')
        changes=[lambda r:r['mapped']['value'].update(application='active'),lambda r:r['mapped']['value'].update(type='affliction'),lambda r:r['mapped']['value'].update(name='Invented'),lambda r:r['mapped']['value'].update(name_truncated=0),lambda r:r['mapped']['value'].update(target_uuid='Actor.other.Item.c'),lambda r:r['mapped']['value'].update(token_uuid='Scene.s.Token.t'),lambda r:r['raw'][0].update(document_uuid='Actor.other.Item.c'),lambda r:r['raw'][0].update(basis='transformed'),lambda r:r['provenance'].update(limitations=[]),lambda r:r.update(key='generated:state')]
        for change in changes:
            row=copy.deepcopy(original);change(row)
            with self.subTest(row=row),self.assertRaises(ToolError):await self.read(self.page([row]))
        source=next(r for r in self.rows() if r['provenance']['mapping']=='pf2e.condition.source.v1')
        source=copy.deepcopy(source);source['raw'][0]['document_uuid']='Actor.other.Item.c'
        with self.assertRaises(ToolError):await self.read(self.page([source]))

    async def test_capability_and_partial_diagnostics_are_mandatory_contracts(self):
        for change in [lambda r:r['mapped']['value'].update(status='supported'),lambda r:r['mapped']['value'].update(stage=999),lambda r:r['provenance'].update(limitations=[]),lambda r:r['raw'].append(dict(document_uuid='Actor.a',path='/system/stage',present=True,value=999,basis='source'))]:
            page=copy.deepcopy(self.fixture['empty']);change(page['records'][0])
            with self.assertRaises(ToolError):await self.read(page)
        for reason in ('effective_application_not_evaluated','affliction_reading_unsupported'):
            page=copy.deepcopy(self.fixture['empty']);page['sections'][0]['reasons'].remove(reason)
            with self.assertRaises(ToolError):await self.read(page)
        page=copy.deepcopy(self.fixture['empty']);page['sections'][0]['status']='complete'
        with self.assertRaises(ToolError):await self.read(page)
        denied=next(r for r in self.rows() if r['key']=='state:denied');page=self.page([denied]);page['sections'][0]['reasons'].remove('state_items_denied')
        with self.assertRaises(ToolError):await self.read(page)

    async def test_same_page_type_and_badge_witnesses_cannot_conflict(self):
        identity=copy.deepcopy(next(r for r in self.rows() if r['key']=='state:item:Actor.a.Item.c'))
        source=copy.deepcopy(next(r for r in self.rows() if r['key']=='state:source:Actor.a.Item.e:/system/badge/type'))
        source['key']=source['key'].replace('.Item.e:', '.Item.c:')
        source['raw'][0]['document_uuid']='Actor.a.Item.c';source['provenance']['contributors'][0]['document_uuid']='Actor.a.Item.c'
        with self.assertRaises(ToolError):await self.read(self.page([identity,source]))
        badge=copy.deepcopy(next(r for r in self.rows() if r['key']=='state:source:Actor.a.Item.e:/system/badge/value'))
        badge['raw'][0]['value']=3;badge['mapped']['value']=3
        discriminator=next(r for r in self.rows() if r['key']=='state:source:Actor.a.Item.e:/system/badge/type')
        with self.assertRaises(ToolError):await self.read(self.page([discriminator,badge]))
        await self.read(self.page([badge]))

    async def test_token_context_unresolved_claims_and_denied_metadata_are_strict(self):
        row=copy.deepcopy(next(r for r in self.rows() if r['key']=='state:item:Actor.a.Item.c'))
        page=self.page([row]);prefix='Scene.s.Token.t.Actor.a'
        page['identity'].update(uuid=prefix,source_kind='token',instance=dict(scene_uuid='Scene.s',scene_name='Scene',token_uuid='Scene.s.Token.t',token_name='Token',actor_link=False,base_actor=dict(uuid='Actor.a',name='Base')))
        row=page['records'][0];row['key']=row['key'].replace('Actor.a',prefix)
        row['mapped']['value'].update(target_uuid=prefix+'.Item.c',token_uuid='Scene.s.Token.t')
        for field in row['raw']:field['document_uuid']=prefix+'.Item.c'
        row['provenance']['contributors']=[{k:r[k] for k in ('document_uuid','path','basis')} for r in row['raw']]
        await self.read(page,token_uuid='Scene.s.Token.t')
        row['mapped']['value']['token_uuid']='Scene.other.Token.t'
        with self.assertRaises(ToolError):await self.read(page,token_uuid='Scene.s.Token.t')
        unresolved=next(r for r in self.rows() if r['key']=='state:condition:Actor.a.Item.c:/system/overrides/0')
        page=self.page([unresolved]);page['sections'][0]['reasons'].remove('unresolved_state_references')
        with self.assertRaises(ToolError):await self.read(page)
        denied=copy.deepcopy(next(r for r in self.rows() if r['key']=='state:denied'));denied['mapped']['value']['name']='Secret'
        with self.assertRaises(ToolError):await self.read(self.page([denied]))
