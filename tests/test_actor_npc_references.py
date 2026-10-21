"""PF2e-specific NPC8.6.1 actual owned attack/ability reference boundary."""
import copy
import json
import subprocess
from pathlib import Path
import unittest
from unittest.mock import AsyncMock
from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_actor
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_lore import specialty


def reference(section='strikes',target='Actor.a.Item.attack'):
    result=specialty(target);row=result['records'][0]
    item_type,concept,reason=('melee','npc_attack_item','other_attacks_pending') if section=='strikes' else ('action','npc_ability_item','other_abilities_pending')
    row.update(section=section,key=section+':item:'+target)
    row['raw'][1]['value']=item_type
    row['mapped']['concept']=concept
    row['provenance']['mapping']='pf2e.npc.item-reference.v1'
    result['sections']=[dict(name=section,status='partial',reasons=[reason])]
    return result


class NpcItemReferenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,result):
        self.manager.call.return_value=result
        selectors=dict(token_uuid=result['identity']['instance']['token_uuid']) if result['identity']['instance'] else dict(actor_uuid=result['identity']['uuid'])
        return await read_actor.fn(**selectors,sections=[result['sections'][0]['name']])

    async def test_each_section_requires_actual_immediate_ownership_and_exact_provenance(self):
        for section in ('strikes','abilities'):
            await self.read(reference(section))
            for target in ('Actor.other.Item.attack','Actor.a.Item.attack.Item.nested','Actor.a.Item.','Attack name'):
                with self.subTest(section=section,target=target),self.assertRaises(ToolError):await self.read(reference(section,target))
            changes=[lambda r:r['raw'][1].update(value='feat'),lambda r:r['raw'][0].update(document_uuid='Actor.other.Item.attack'),lambda r:r['raw'][0].update(present=False),lambda r:r['raw'][0].update(value=23),lambda r:r['mapped'].update(concept='lore_specialty'),lambda r:r['mapped']['value'].update(status='unverified'),lambda r:r['mapped']['value'].update(token_uuid='Scene.s.Token.t'),lambda r:r['mapped']['value'].update(name='private'),lambda r:r['provenance'].update(contributors=[]),lambda r:r['provenance'].update(mapping='pf2e.lore.specialty.v1'),lambda r:r['provenance'].update(limitations=[]),lambda r:r.update(key='wrong')]
            for change in changes:
                bad=reference(section);change(bad['records'][0])
                with self.subTest(section=section,change=change),self.assertRaises(ToolError):await self.read(bad)
            for actor_type in ('character','familiar'):
                bad=reference(section);bad['identity']['type']=actor_type
                with self.assertRaises(ToolError):await self.read(bad)

    async def test_linked_and_synthetic_token_reference_selectors_are_exact(self):
        for section in ('strikes','abilities'):
            for linked in (True,False):
                uuid='Actor.a' if linked else 'Scene.s.Token.t.Actor.a'
                result=reference(section,uuid+'.Item.attack')
                result['identity'].update(uuid=uuid,source_kind='token',instance=dict(scene_uuid='Scene.s',scene_name='Scene',token_uuid='Scene.s.Token.t',token_name='Token',actor_link=linked,base_actor=dict(uuid='Actor.a',name='Base')))
                result['records'][0]['mapped']['value']['token_uuid']='Scene.s.Token.t'
                await self.read(result)
                for token in (None,'Scene.s.Token.wrong'):
                    bad=copy.deepcopy(result)
                    if token is None:del bad['records'][0]['mapped']['value']['token_uuid']
                    else:bad['records'][0]['mapped']['value']['token_uuid']=token
                    with self.assertRaises(ToolError):await self.read(bad)

    async def test_denied_marker_has_no_identity_or_selector_leaks(self):
        for section in ('strikes','abilities'):
            result=reference(section);row=result['records'][0]
            row.update(key=section+':items:denied',raw=[])
            row['mapped']['value']=dict(target_uuid=None,status='denied')
            row['provenance']['contributors']=[]
            result['sections'][0]['reasons'].append('related_items_denied')
            await self.read(result)
            for key,value in [('target_uuid','Actor.a.Item.private'),('token_uuid','Scene.s.Token.t'),('name','Secret')]:
                bad=copy.deepcopy(result);bad['records'][0]['mapped']['value'][key]=value
                with self.assertRaises(ToolError):await self.read(bad)

    async def test_partial_status_is_required_even_for_empty_sections(self):
        for section in ('strikes','abilities'):
            result=reference(section);result['records']=[];result['pagination']['returned']=0
            await self.read(result)
            for status,reasons in [('complete',[]),('partial',[]),('unsupported',['not_implemented'])]:
                bad=copy.deepcopy(result);bad['sections'][0].update(status=status,reasons=reasons)
                with self.assertRaises(ToolError):await self.read(bad)

    async def test_actual_browser_references_preserve_duplicate_and_token_ownership(self):
        script=r"""
import {readActor} from './foundry-module/scripts/actors.js';
const docs=new Map();globalThis.game={version:'14.369',system:{id:'pf2e',version:'8.6.1'},ready:true,user:{isGM:true},actors:new Map(),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>docs.get(uuid)}};
const owner=uuid=>({id:'a',uuid,name:'NPC',type:'npc',documentName:'Actor',folder:null,compendium:null,items:new Map(),testUserPermission:()=>true,toObject:()=>({name:'NPC',type:'npc',system:{}})});
const populate=actor=>{for(const type of ['melee','action'])for(const id of ['one','two']){const item={id:type+id,uuid:`${actor.uuid}.Item.${type+id}`,name:'Same name',type,documentName:'Item',parent:actor,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>({name:'Same name',type,system:{}})};actor.items.set(item.id,item);docs.set(item.uuid,item);}};
const base=owner('Actor.a');populate(base);docs.set(base.uuid,base);game.actors.set(base.id,base);
const pages=[];for(const section of ['strikes','abilities'])pages.push(await readActor({actor_uuid:base.uuid,sections:[section]}));
for(const linked of [true,false]){const actor=linked?base:owner('Scene.s.Token.synthetic.Actor.a');if(!linked)populate(actor);const scene={id:'s',uuid:'Scene.s',name:'Scene',documentName:'Scene',testUserPermission:()=>true};const token={id:linked?'linked':'synthetic',uuid:linked?'Scene.s.Token.linked':'Scene.s.Token.synthetic',name:'Token',documentName:'Token',parent:scene,actor,baseActor:base,isLinked:linked,testUserPermission:()=>true};if(!linked)actor.token=token;docs.set(token.uuid,token);for(const section of ['strikes','abilities'])pages.push(await readActor({token_uuid:token.uuid,sections:[section]}));}
console.log(JSON.stringify(pages));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(process.returncode,0,process.stderr)
        pages=json.loads(process.stdout)
        self.assertEqual(len(pages),6)
        for page in pages:
            await self.read(page)
            self.assertEqual(len(page['records']),2)
            self.assertEqual(len({r['mapped']['value']['target_uuid'] for r in page['records']}),2)
            self.assertEqual(page['sections'][0]['status'],'partial')
            instance=page['identity']['instance']
            if instance:
                for row in page['records']:self.assertEqual(row['mapped']['value']['token_uuid'],instance['token_uuid'])
