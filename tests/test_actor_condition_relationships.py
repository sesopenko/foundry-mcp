"""PF2e-specific condition8.6.1 source-local relationship DTO regressions."""
import json
import subprocess
from pathlib import Path
import unittest
from unittest.mock import AsyncMock
from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_item
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_action import response


def relationship(role='parent', status='resolved', owner=True, marker=False):
    bases={'parent':'/system/references/parent','children':'/system/references/children','overrides':'/system/references/overrides','overriddenBy':'/system/references/overriddenBy','slug':'/system/overrides'}
    concepts={'parent':'parent_reference','children':'child_reference','overrides':'override_reference','overriddenBy':'overridden_by_reference','slug':'override_slug'}
    path=bases[role]+('' if marker else '/id' if role=='parent' else '/0' if role=='slug' else '/0/id')
    result=response(section='relationships',item_type='condition');row=result['records'][0]
    if owner:result['identity']['actor']=dict(uuid='Actor.owner',name='Owner',type='npc')
    raw=[dict(document_uuid='Item.a',path=path,present=True,value=None if marker and role=='parent' else [] if marker else 'target',basis='source')]
    if not marker and role not in ('parent','slug'):raw.append(dict(raw[0],path=path[:-2]+'type',value='condition'))
    value=dict(status=status,target_uuid='Actor.owner.Item.target' if status=='resolved' else None)
    if status=='resolved':value.update(document_name='Item',type='condition',name='Target',name_truncated=False)
    row.update(key='relationships:condition:'+path,kind='relationship',raw=raw,mapped=dict(concept='condition_'+concepts[role],value=value,unit=None))
    row['provenance'].update(mapping='pf2e.condition.reference.v1',contributors=[{k:r[k] for k in ('document_uuid','path','basis')} for r in raw],limitations=['Source reference only.'])
    return result


class ConditionRelationshipTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,result):
        self.manager.call.return_value=result
        return await read_item.fn(item_uuid='Item.a',sections=['relationships'],token_uuid=result['identity']['instance']['token_uuid'] if result['identity']['instance'] else None)

    async def test_roles_markers_and_unresolved_states(self):
        for role in ('parent','children','overrides','overriddenBy'):
            await self.read(relationship(role))
            for status in ('missing','denied','unsupported','unverified'):await self.read(relationship(role,status))
            await self.read(relationship(role,'unverified',owner=False))
        await self.read(relationship('slug','unverified'))
        for role in ('parent','children','overrides','overriddenBy','slug'):
            result=relationship(role,'missing',marker=True);await self.read(result)
            raw=result['records'][0]['raw'][0];raw['present']=False;raw.pop('value');await self.read(result)

    async def test_same_owner_targets_exact_types_and_provenance(self):
        mutations=[lambda r:r.update(key='relationships:condition:wrong'),lambda r:r.update(kind='field'),lambda r:r['raw'][0].update(document_uuid='Item.other'),lambda r:r['mapped'].update(concept='condition_active'),lambda r:r['mapped']['value'].update(target_uuid='Actor.other.Item.target'),lambda r:r['mapped']['value'].update(type='spell'),lambda r:r['mapped']['value'].update(name='x'*257),lambda r:r['mapped']['value'].update(name_truncated=1),lambda r:r['mapped']['value'].update(token_uuid='Scene.s.Token.t'),lambda r:r['provenance'].update(limitations=[]),lambda r:r['provenance']['contributors'].pop(),lambda r:r['raw'][1].update(value='effect'),lambda r:r['raw'].pop()]
        for mutate in mutations:
            result=relationship('children');mutate(result['records'][0])
            with self.subTest(mutation=mutations.index(mutate)),self.assertRaises(ToolError):await self.read(result)
        result=relationship();result['records'][0]['mapped']['value']['type']='effect';await self.read(result)
        for result in (relationship(owner=False),relationship('slug'),relationship('parent','resolved',marker=True)):
            with self.assertRaises(ToolError):await self.read(result)

    async def test_token_context_cannot_cross_actor_or_token_boundary(self):
        result=relationship()
        result['identity']['source_kind']='token'
        result['identity']['instance']=dict(scene_uuid='Scene.s',scene_name='Scene',token_uuid='Scene.s.Token.t',token_name='Token',actor_link=True,base_actor=dict(uuid='Actor.owner',name='Owner'))
        result['records'][0]['mapped']['value']['token_uuid']='Scene.s.Token.t'
        await self.read(result)
        result['records'][0]['mapped']['value']['token_uuid']='Scene.other.Token.t'
        with self.assertRaises(ToolError):await self.read(result)

    async def test_unresolved_rows_do_not_disclose_target_metadata(self):
        for status in ('missing','denied','unsupported','unverified'):
            for extra in [dict(name='Secret'),dict(type='condition'),dict(target_uuid='Item.private'),dict(document_name='Item')]:
                result=relationship(status=status);result['records'][0]['mapped']['value'].update(extra)
                with self.assertRaises(ToolError):await self.read(result)
        for result in (relationship('slug','denied'),relationship(status='denied',owner=False),relationship(status='unverified',marker=True)):
            with self.assertRaises(ToolError):await self.read(result)

    async def test_actual_node_owned_detached_and_token_pages(self):
        script=r"""
import {readItem} from './foundry-module/scripts/actors.js';
const docs=new Map();
globalThis.game={version:'14.369',system:{id:'pf2e',version:'8.6.1'},ready:true,user:{isGM:true},actors:new Map(),items:new Map()};
globalThis.foundry={utils:{fromUuid:async uuid=>docs.get(uuid)}};
function owner(uuid){const actor={id:'a',uuid,name:'Owner',type:'npc',documentName:'Actor',parent:null,folder:null,compendium:null,items:new Map(),testUserPermission:()=>true};docs.set(uuid,actor);return actor;}
function item(actor,id,type,system={}){const d={id,uuid:actor?actor.uuid+'.Item.'+id:'Item.'+id,name:'Same name',type,documentName:'Item',parent:actor,folder:null,compendium:null,testUserPermission:()=>id!=='denied',toObject:()=>({name:'Condition',type,system:structuredClone(system)})};docs.set(d.uuid,d);if(actor)actor.items.set(id,d);else game.items.set(id,d);return d;}
const pages=[];
for(const kind of ['owned','detached','linked','synthetic']){
 const actor=kind==='detached'?null:owner(kind==='synthetic'?'Scene.s.Token.t.Actor.a':'Actor.'+kind);
 if(actor){item(actor,'target','condition');item(actor,'parent','effect');item(actor,'denied','condition');item(actor,'wrong','action');}
 if(kind==='linked'||kind==='synthetic'){
 const scene={uuid:'Scene.s',documentName:'Scene',name:'Scene',testUserPermission:()=>true};
 const token={id:'t',uuid:'Scene.s.Token.t',name:'Token',documentName:'Token',parent:scene,actor,baseActor:actor,isLinked:kind==='linked',testUserPermission:()=>true};docs.set(token.uuid,token);if(kind==='synthetic')actor.token=token;
 }
 const condition=item(actor,'a','condition',{references:{parent:{id:'parent'},children:[{id:'target',type:'condition'},{id:'target'},{id:'denied',type:'condition'},{id:'wrong',type:'condition'}],overrides:[],overriddenBy:[{id:'absent',type:'condition'}]},overrides:['frightened','frightened']});
 let cursor;do{const page=await readItem({item_uuid:condition.uuid,sections:['relationships'],limit:2,...(kind==='linked'||kind==='synthetic'?{token_uuid:'Scene.s.Token.t'}:{}),...(cursor?{cursor}:{})});pages.push(page);cursor=page.pagination.next_cursor;}while(cursor);
}
console.log(JSON.stringify(pages));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(process.returncode,0,process.stderr)
        pages=json.loads(process.stdout)
        for page in pages:
            self.manager.call.return_value=page
            selectors=dict(item_uuid=page['identity']['uuid'],sections=['relationships'])
            if page['identity']['instance']:selectors['token_uuid']=page['identity']['instance']['token_uuid']
            await read_item.fn(**selectors)
        self.assertGreater(len(pages),4)
        self.assertTrue(any(row['mapped']['value']['status']=='denied' for page in pages for row in page['records']))
