"""PF2e-specific8.6.1 Build records cross the actual browser/Python boundary."""
import copy
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import AsyncMock

from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import _build_section, _record, _validate, read_actor
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_action import response


class ActorBuildTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        script=r"""
import {actorBuildRecords} from './foundry-module/scripts/actorBuild.js';
globalThis.game={user:{isGM:true}};
const actor={documentName:'Actor',id:'a',uuid:'Actor.a',name:'Actor',type:'character',items:new Map()};
const add=(id,type,system={},flags={})=>{const source={name:id,type,system,flags};const item={id,uuid:actor.uuid+'.Item.'+id,documentName:'Item',type,name:id,parent:actor,testUserPermission:()=>true,toObject:()=>structuredClone(source)};actor.items.set(id,item);};
add('background','background',{trainedSkills:{value:['arc'],lore:['Same']}},{pf2e:{itemGrants:{lore:{id:'lore'},missing:{id:'gone'},action:{id:'action'}}}});
add('lore','lore',{proficient:{value:1}},{pf2e:{grantedBy:{id:'background'}}});
add('feat','feat',{category:'classfeature',level:{value:1,taken:4}},{pf2e:{rulesSelections:{choice:'value',unsupported:{x:1}}}});
add('action','action',{},{});
for(const type of ['ancestry','heritage','class','deity'])add(type,type,{});
console.log(JSON.stringify(actorBuildRecords({document:actor})));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        if process.returncode:raise AssertionError(process.stderr)
        cls.snapshot=json.loads(process.stdout)

    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)
        self.identity=response()['identity'];self.identity.update(document_name='Actor',uuid='Actor.a',type='character')

    async def page(self, rows, reasons=None):
        page=response(section='build');page['identity']=self.identity
        page['records']=rows;page['pagination']['returned']=len(rows)
        page['sections'][0].update(status='partial' if reasons else 'complete',reasons=reasons or [])
        self.manager.call.return_value=page
        return await read_actor.fn(actor_uuid='Actor.a',sections=['build'])

    async def test_actual_records_survive_independent_single_record_pages(self):
        self.assertGreater(len(self.snapshot['records']),150)
        for row in self.snapshot['records']:
            with self.subTest(key=row['key']):
                self.assertTrue(_record(row,['build'],self.identity),row)
                await self.page([row],self.snapshot['reasons'])

    async def test_source_context_value_mapping_owner_and_private_path_forgeries(self):
        source=next(r for r in self.snapshot['records'] if r['key']=='build:source:Actor.a.Item.background:/system/trainedSkills/value/0')
        for mutate in (
            lambda r:r['raw'][0].update(value='class'),
            lambda r:r['raw'][1].update(document_uuid='Actor.other.Item.background'),
            lambda r:r['raw'].pop(0),
            lambda r:r['mapped'].update(value='soc'),
            lambda r:r['provenance'].update(mapping='pf2e.class.source.v1'),
            lambda r:r['raw'][1].update(path='/flags/private'),
        ):
            row=copy.deepcopy(source);mutate(row)
            with self.subTest(row=row),self.assertRaises(ToolError):await self.page([row])

    async def test_reciprocal_claim_cannot_be_fabricated_or_cross_owner(self):
        claim=next(r for r in self.snapshot['records'] if r['mapped']['concept']=='build_grant_claim' and r['mapped']['value']['reciprocity']=='agree')
        for mutate in (
            lambda r:r['raw'].pop(),
            lambda r:r['raw'][2].update(value='another'),
            lambda r:r['raw'][2].update(document_uuid='Actor.other.Item.lore'),
            lambda r:r['mapped']['value'].update(target_uuid='Actor.a.Item.other'),
            lambda r:r['mapped']['value'].update(token_uuid='Scene.s.Token.t'),
        ):
            row=copy.deepcopy(claim);mutate(row)
            with self.subTest(row=row),self.assertRaises(ToolError):await self.page([row])

    async def test_same_page_identity_and_source_types_must_agree(self):
        owned=next(r for r in self.snapshot['records'] if r['key']=='build:item:Actor.a.Item.background')
        source=copy.deepcopy(next(r for r in self.snapshot['records'] if r['key']=='build:source:Actor.a.Item.background:/system/publication/title'))
        template=next(r for r in self.snapshot['records'] if r['key']=='build:source:Actor.a.Item.class:/system/publication/title')
        source['raw'][0]['value']='class'
        source['mapped']=copy.deepcopy(template['mapped'])
        for key in ('mapping','limitations'):source['provenance'][key]=copy.deepcopy(template['provenance'][key])
        self.assertTrue(_record(source,['build'],self.identity))
        with self.assertRaises(ToolError):await self.page([owned,source])

    async def test_same_page_claim_target_identity_must_agree(self):
        owned=next(r for r in self.snapshot['records'] if r['key']=='build:item:Actor.a.Item.lore')
        original=next(r for r in self.snapshot['records'] if r['mapped']['concept']=='build_grant_claim' and r['mapped']['value']['reciprocity']=='agree')
        await self.page([owned,original])
        for changes in ({'type':'feat'},{'name':'Different name'},{'name_truncated':True}):
            claim=copy.deepcopy(original);claim['mapped']['value'].update(changes)
            self.assertTrue(_record(claim,['build'],self.identity))
            with self.subTest(changes=changes),self.assertRaises(ToolError):await self.page([owned,claim])

    async def test_same_page_inverse_source_witness_must_agree(self):
        source=next(r for r in self.snapshot['records'] if r['key']=='build:source:Actor.a.Item.lore:/flags/pf2e/grantedBy/id')
        claim=copy.deepcopy(next(r for r in self.snapshot['records'] if r['mapped']['concept']=='build_grant_claim' and r['mapped']['value']['reciprocity']=='agree'))
        await self.page([source,claim])
        claim['raw'][2]['value']='another'
        claim['mapped']['value']['reciprocity']='disagree'
        self.assertTrue(_record(claim,['build'],self.identity))
        with self.assertRaises(ToolError):await self.page([source,claim])

    def test_repeated_raw_witness_comparison_preserves_boolean_number_types(self):
        row=next(r for r in self.snapshot['records'] if r['key']=='build:source:Actor.a.Item.lore:/system/proficient/value')
        first=copy.deepcopy(row);second=copy.deepcopy(row)
        first['raw'][1]['value']=True;second['raw'][1]['value']=1
        section={'status':'complete','reasons':[]}
        self.assertTrue(_build_section([first,first],section,self.identity))
        self.assertFalse(_build_section([first,second],section,self.identity))

    async def test_unresolved_diagnostics_and_noncharacter_scope(self):
        claim=next(r for r in self.snapshot['records'] if r['mapped']['concept']=='build_grant_claim' and r['mapped']['value']['status']=='missing')
        with self.assertRaises(ToolError):await self.page([claim])
        await self.page([claim],['build_grant_target_missing'])
        for typ in ('npc','familiar'):
            identity=dict(self.identity,type=typ)
            self.assertFalse(_record(self.snapshot['records'][0],['build'],identity))
        page=response(section='build');page['identity']=self.identity;page['runtime']['system_id']='other';page['records']=[];page['pagination']['returned']=0
        self.manager.call.return_value=page
        with self.assertRaises(ToolError):await read_actor.fn(actor_uuid='Actor.a',sections=['build'])

    async def test_actual_reader_paginates_without_donor_identity_dependency(self):
        script=r"""
import {readActor} from './foundry-module/scripts/actors.js';
const actor={documentName:'Actor',id:'a',uuid:'Actor.a',name:'Actor',type:'character',items:new Map(),parent:null,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>({name:'Actor',type:'character',system:{}})};
for(const [id,type,flags] of [['bg','background',{pf2e:{itemGrants:{lore:{id:'lore'}}}}],['lore','lore',{pf2e:{grantedBy:{id:'bg'}}}]]){const source={name:id,type,system:{},flags};actor.items.set(id,{id,uuid:actor.uuid+'.Item.'+id,documentName:'Item',type,name:id,parent:actor,testUserPermission:()=>true,toObject:()=>structuredClone(source)});}
globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map([['a',actor]]),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>uuid==='Actor.a'?actor:null}};
let cursor;const pages=[];do{const page=await readActor({actor_uuid:'Actor.a',sections:['build'],limit:1,max_bytes:8000,...(cursor?{cursor}:{})});pages.push(page);cursor=page.pagination.next_cursor;}while(cursor);console.log(JSON.stringify(pages));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(process.returncode,0,process.stderr)
        pages=json.loads(process.stdout);self.assertGreater(len(pages),30)
        for page in pages:_validate(page,'read',limit=1,max_bytes=8000,sections=['build'])
        rows=[r for p in pages for r in p['records']]
        self.assertEqual(len(rows),len({r['key'] for r in rows}))
