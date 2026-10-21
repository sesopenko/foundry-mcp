"""PF2e-specific weapon8.6.1 stored selected-ammunition DTO regressions."""
import json
import subprocess
from pathlib import Path
import unittest
from unittest.mock import AsyncMock
from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_item
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_action import response


def relationship(status='resolved', owner=True, local_id='target', present=True):
    result=response(section='relationships',item_type='weapon');row=result['records'][0]
    if owner: result['identity']['actor']=dict(uuid='Actor.owner',name='Owner',type='npc')
    raw=dict(document_uuid='Item.a',path='/system/selectedAmmoId',present=present,basis='source')
    if present: raw['value']=local_id
    value=dict(status=status,target_uuid='Actor.owner.Item.target' if status=='resolved' else None)
    if status=='resolved':value.update(document_name='Item',type='ammo',name='Ammo',name_truncated=False)
    row.update(key='relationships:weapon:selectedAmmoId',kind='relationship',raw=[raw],mapped=dict(concept='stored_selected_ammunition_reference',value=value,unit=None))
    row['provenance'].update(mapping='pf2e.weapon.selected-ammo.v1',contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],limitations=['Stored reference only.'])
    return result


class WeaponRelationshipTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,result):
        self.manager.call.return_value=result
        return await read_item.fn(item_uuid=result['identity']['uuid'],sections=['relationships'],token_uuid=result['identity']['instance']['token_uuid'] if result['identity']['instance'] else None)

    async def test_source_markers_owner_and_target_types(self):
        for status in ('resolved','missing','denied','unsupported','unverified'): await self.read(relationship(status))
        for value,present in [(None,True),('',True),(None,False)]:await self.read(relationship('missing',local_id=value,present=present))
        await self.read(relationship('unverified',owner=False))
        result=relationship();result['records'][0]['mapped']['value']['type']='weapon';await self.read(result)
        for result in (relationship(owner=False),relationship('denied',owner=False),relationship('unverified',local_id=''),relationship(local_id='target.child'),relationship(local_id=None)):
            with self.assertRaises(ToolError):await self.read(result)

    async def test_exact_type_provenance_and_owner_boundary(self):
        mutations=[lambda r:r.update(key='forged'),lambda r:r.update(kind='field'),lambda r:r['raw'][0].update(document_uuid='Item.other'),lambda r:r['raw'][0].update(value=1),lambda r:r['mapped'].update(concept='current_ammunition'),lambda r:r['mapped']['value'].update(target_uuid='Actor.other.Item.target'),lambda r:r['mapped']['value'].update(type='equipment'),lambda r:r['mapped']['value'].update(name='x'*257),lambda r:r['mapped']['value'].update(name_truncated=1),lambda r:r['mapped']['value'].update(token_uuid='Scene.s.Token.t'),lambda r:r['provenance'].update(limitations=[]),lambda r:r['provenance'].update(mapping='pf2e.weapon.source.v1'),lambda r:r['provenance']['contributors'].clear()]
        for mutation in mutations:
            result=relationship();mutation(result['records'][0])
            with self.subTest(mutation=mutations.index(mutation)),self.assertRaises(ToolError):await self.read(result)

    async def test_unresolved_targets_exclude_metadata(self):
        for status in ('missing','denied','unsupported','unverified'):
            for extra in (dict(name='Secret'),dict(type='ammo'),dict(document_name='Item'),dict(target_uuid='Item.secret'),dict(token_uuid='Scene.s.Token.t')):
                result=relationship(status);result['records'][0]['mapped']['value'].update(extra)
                with self.assertRaises(ToolError):await self.read(result)

    async def test_linked_and_synthetic_token_context(self):
        for linked in (True,False):
            result=relationship();identity=result['identity'];identity['source_kind']='token'
            owner_uuid='Actor.owner' if linked else 'Scene.s.Token.t.Actor.owner'
            identity['actor']['uuid']=owner_uuid
            identity['instance']=dict(scene_uuid='Scene.s',scene_name='Scene',token_uuid='Scene.s.Token.t',token_name='Token',actor_link=linked,base_actor=dict(uuid='Actor.owner',name='Owner'))
            value=result['records'][0]['mapped']['value'];value.update(target_uuid=owner_uuid+'.Item.target',token_uuid='Scene.s.Token.t')
            await self.read(result)
            value['token_uuid']='Scene.other.Token.t'
            with self.assertRaises(ToolError):await self.read(result)

    async def test_actual_node_owned_detached_and_token_pages(self):
        script=r"""
import {readItem} from './foundry-module/scripts/actors.js';
const docs=new Map();
globalThis.game={version:'14.369',system:{id:'pf2e',version:'8.6.1'},ready:true,user:{isGM:true},actors:new Map(),items:new Map()};
globalThis.foundry={utils:{fromUuid:async uuid=>docs.get(uuid)}};
function owner(uuid){const actor={id:'a',uuid,name:'Owner',type:'npc',documentName:'Actor',parent:null,folder:null,compendium:null,items:new Map(),testUserPermission:()=>true};docs.set(uuid,actor);return actor;}
function item(actor,id,type,system={}){const d={id,uuid:actor?actor.uuid+'.Item.'+id:'Item.'+id,name:'Same name',type,documentName:'Item',parent:actor,folder:null,compendium:null,testUserPermission:()=>id!=='denied',toObject:()=>({name:'Weapon',type,system:structuredClone(system)})};docs.set(d.uuid,d);if(actor)actor.items.set(id,d);else game.items.set(id,d);return d;}
const pages=[];
for(const kind of ['owned','detached','linked','synthetic']){
 const actor=kind==='detached'?null:owner(kind==='synthetic'?'Scene.s.Token.t.Actor.a':'Actor.'+kind);
 if(actor){item(actor,'target','ammo');item(actor,'weapon','weapon');item(actor,'denied','ammo');item(actor,'wrong','action');}
 if(kind==='linked'||kind==='synthetic'){
 const scene={uuid:'Scene.s',documentName:'Scene',name:'Scene',testUserPermission:()=>true};
 const token={id:'t',uuid:'Scene.s.Token.t',name:'Token',documentName:'Token',parent:scene,actor,baseActor:actor,isLinked:kind==='linked',testUserPermission:()=>true};docs.set(token.uuid,token);if(kind==='synthetic')actor.token=token;
 }
 for(const id of ['target','weapon','denied','wrong','absent','',null,undefined]){
 const weapon=item(actor,'a','weapon',id===undefined?{}:{selectedAmmoId:id});
 pages.push(await readItem({item_uuid:weapon.uuid,sections:['relationships'],limit:1,...(kind==='linked'||kind==='synthetic'?{token_uuid:'Scene.s.Token.t'}:{})}));
 }
}
console.log(JSON.stringify(pages));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(process.returncode,0,process.stderr)
        pages=json.loads(process.stdout)
        for page in pages:await self.read(page)
        statuses={r['mapped']['value']['status'] for p in pages for r in p['records']}
        self.assertEqual(statuses,{'resolved','denied','unsupported','unverified','missing'})
