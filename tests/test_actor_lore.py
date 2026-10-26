"""PF2e-specific Lore source and Actor skill reference boundary,8.6.1."""
import json
import subprocess
from pathlib import Path
import unittest
from unittest.mock import AsyncMock
from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_item,read_actor
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_action import response


def lore(path='/system/proficient/value',value=2,owner=None,present=True):
    result=response(path,value,item_type='lore',present=present)
    row=result['records'][0];row['provenance']['mapping']='pf2e.lore.source.v1'
    if owner is not None:result['identity']['actor']=dict(uuid='Actor.owner',name='Owner',type=owner)
    if path=='/system/proficient/value':row['mapped'].update(concept='character_lore_proficiency_rank' if owner=='character' else 'stored_lore_proficiency_rank',value=dict(rank=value,label=['Untrained','Trained','Expert','Master','Legendary'][value]) if present and type(value) is int and 0<=value<=4 else None)
    if path=='/system/mod/value':row['mapped']['concept']='npc_lore_authored_modifier' if owner=='npc' else 'stored_lore_modifier'
    return result


def specialty(target='Actor.a.Item.lore'):
    result=response(section='skills');result['identity'].update(document_name='Actor',type='npc',uuid='Actor.a')
    raw=[dict(document_uuid=target,path=path,present=True,value=value,basis='source') for path,value in [('/name','Underworld Lore'),('/type','lore')]]
    result['records'][0].update(key='skills:lore:'+target,kind='relationship',raw=raw,mapped=dict(concept='lore_specialty',value=dict(target_uuid=target,status='resolved'),unit=None),provenance=dict(contributors=[{k:r[k] for k in ('document_uuid','path','basis')} for r in raw],mapping='pf2e.lore.specialty.v1',limitations=['lore_item_reference_not_full_skill_total']))
    result['sections'][0].update(status='partial',reasons=['other_skills_pending'])
    return result


class ActorLoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,result):
        self.manager.call.return_value=result
        return await read_item.fn(item_uuid='Item.a',sections=['source'])

    async def actor(self,result):
        self.manager.call.return_value=result
        return await read_actor.fn(actor_uuid='Actor.a',sections=['skills'])

    async def test_owner_dependent_rank_and_mod_are_never_effective_totals(self):
        for owner in [None,'character','npc','familiar']:
            for rank in range(5):
                self.assertEqual((await self.read(lore(value=rank,owner=owner)))['records'][0]['mapped']['value']['rank'],rank)
            await self.read(lore('/system/mod/value',0,owner))
            await self.read(lore(owner=owner,present=False))
        for value in [-1,5,True,2.0,None,'2']:
            with self.subTest(value=value),self.assertRaises(ToolError):await self.read(lore(value=value))
        bad=lore(owner='character');bad['records'][0]['mapped']['concept']='stored_lore_proficiency_rank'
        with self.assertRaises(ToolError):await self.read(bad)
        bad=lore(owner='vehicle')
        with self.assertRaises(ToolError):await self.read(bad)

    async def test_variants_allow_escaped_primitive_leaves_and_empty_markers(self):
        for path,value in [('/system/variants',{}),('/system/variants/a~1~0/label','Specialty'),('/system/variants//options','action:recall-knowledge'),('/system/traits/otherTags',[]),('/system/traits/otherTags/0','tag'),('/system/slug',None),('/system/publication/remaster',False)]:
            await self.read(lore(path,value))
        for path,value in [('/system/variants',{'secret':1}),('/system/variants/a/label',[]),('/system/variants/a~2/options','bad'),('/system/variants/a/private','bad'),('/system/traits/value',[]),('/system/mod/value',True),('/system/publication/remaster',0)]:
            with self.subTest(path=path),self.assertRaises(ToolError):await self.read(lore(path,value))

    async def test_skill_relationship_membership_and_provenance(self):
        await self.actor(specialty())
        for target in ['Actor.other.Item.lore','Actor.a.Item.lore.Item.nested','Lore name']:
            with self.subTest(target=target),self.assertRaises(ToolError):await self.actor(specialty(target))
        for change in [lambda r:r['mapped']['value'].update(status='unverified'),lambda r:r['raw'][1].update(value='feat'),lambda r:r['provenance'].update(limitations=[]),lambda r:r['mapped']['value'].update(token_uuid='Scene.s.Token.t')]:
            bad=specialty();change(bad['records'][0])
            with self.assertRaises(ToolError):await self.actor(bad)

    async def test_token_specialty_requires_matching_token_selector(self):
        for linked in [False,True]:
            actor_uuid='Actor.a' if linked else 'Scene.s.Token.t.Actor.a'
            result=specialty(actor_uuid+'.Item.lore')
            result['identity'].update(uuid=actor_uuid,source_kind='token',instance=dict(scene_uuid='Scene.s',scene_name='Scene',token_uuid='Scene.s.Token.t',token_name='Token',actor_link=linked,base_actor=dict(uuid='Actor.a',name='Base')))
            result['records'][0]['mapped']['value']['token_uuid']='Scene.s.Token.t'
            self.manager.call.return_value=result
            await read_actor.fn(token_uuid='Scene.s.Token.t',sections=['skills'])
            result['records'][0]['mapped']['value']['token_uuid']='Scene.s.Token.wrong'
            with self.assertRaises(ToolError):
                await read_actor.fn(token_uuid='Scene.s.Token.t',sections=['skills'])

    async def test_denied_specialty_marker_contains_no_private_identity(self):
        result=specialty();row=result['records'][0]
        row.update(key='skills:lore:denied',raw=[],mapped=dict(concept='lore_specialty',value=dict(target_uuid=None,status='denied'),unit=None))
        row['provenance'].update(contributors=[],limitations=['related_item_permission_denied'])
        result['sections'][0]['reasons'].append('related_items_denied')
        await self.actor(result)
        self.assertNotIn('Underworld',json.dumps(result))
        self.assertNotIn('Item.lore',json.dumps(result))
        for key,value in [('target_uuid','Actor.a.Item.private'),('token_uuid','Scene.s.Token.t')]:
            bad=json.loads(json.dumps(result));bad['records'][0]['mapped']['value'][key]=value
            with self.assertRaises(ToolError):await self.actor(bad)

    async def test_actual_browser_lore_owner_and_skills_dtos(self):
        script=r"""
import {readItem,readActor} from './foundry-module/scripts/actors.js';
const docs=new Map();globalThis.game={version:'14.369',system:{id:'pf2e',version:'8.6.1'},ready:true,user:{isGM:true},actors:new Map(),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>docs.get(uuid)}};
const make=(owner,id)=>{const source={name:'Underworld Lore',type:'lore',system:{mod:{value:12},proficient:{value:2},variants:{'a/~':{label:'Special use',options:'action:recall-knowledge'}},traits:{otherTags:[]},description:{value:'<p>Exact</p>',gm:'secret'},rules:[{secret:true}]}};const item={id,uuid:owner?`${owner.uuid}.Item.${id}`:`Item.${id}`,name:source.name,type:'lore',documentName:'Item',parent:owner,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};docs.set(item.uuid,item);owner?.items.set(id,item);return item;};
const items=[];const skills=[];
for(const type of ['character','npc','familiar']){const owner={id:type,uuid:`Actor.${type}`,name:type,type,documentName:'Actor',folder:null,compendium:null,items:new Map(),testUserPermission:()=>true,toObject:()=>({name:type,type,system:{}})};docs.set(owner.uuid,owner);game.actors.set(owner.id,owner);const item=make(owner,'a');make(owner,'b');items.push(await readItem({item_uuid:item.uuid,sections:['source']}));skills.push(await readActor({actor_uuid:owner.uuid,sections:['skills']}));}
const detached=make(null,'world');items.push(await readItem({item_uuid:detached.uuid,sections:['source']}));
const tokenSkills=[];
for(const linked of [true,false]){const base=docs.get('Actor.npc');const owner=linked?base:{...base,uuid:'Scene.s.Token.synthetic.Actor.npc',items:new Map()};if(!linked){make(owner,'a');make(owner,'b');}const scene={id:'s',uuid:'Scene.s',name:'Scene',documentName:'Scene',testUserPermission:()=>true};const token={id:linked?'linked':'synthetic',uuid:linked?'Scene.s.Token.linked':'Scene.s.Token.synthetic',name:'Token',documentName:'Token',parent:scene,actor:owner,baseActor:base,isLinked:linked,testUserPermission:()=>true};if(!linked)owner.token=token;docs.set(token.uuid,token);tokenSkills.push(await readActor({token_uuid:token.uuid,sections:['skills']}));}
console.log(JSON.stringify({items,skills,tokenSkills}));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(process.returncode,0,process.stderr)
        fixture=json.loads(process.stdout)
        for page in fixture['items']:
            self.manager.call.return_value=page
            await read_item.fn(item_uuid=page['identity']['uuid'],sections=['source'])
            self.assertNotIn('secret',json.dumps(page))
            fields={r['raw'][0]['path']:r for r in page['records']}
            owner=(page['identity']['actor'] or {}).get('type')
            self.assertEqual(fields['/system/proficient/value']['mapped']['concept'],'character_lore_proficiency_rank' if owner=='character' else 'stored_lore_proficiency_rank')
            self.assertEqual(fields['/system/mod/value']['mapped']['concept'],'npc_lore_authored_modifier' if owner=='npc' else 'stored_lore_modifier')
            self.assertEqual(fields['/system/variants/a~1~0/options']['raw'][0]['value'],'action:recall-knowledge')
        for page in fixture['skills']:
            self.manager.call.return_value=page
            await read_actor.fn(actor_uuid=page['identity']['uuid'],sections=['skills'])
            source_lore=[r for r in page['records'] if r['provenance']['mapping']=='pf2e.lore.specialty.v1']
            self.assertEqual(len(source_lore),2)
            self.assertEqual(len({r['mapped']['value']['target_uuid'] for r in source_lore}),2)
            self.assertEqual(page['sections'][0]['status'],'partial')

        for page in fixture['tokenSkills']:
            token=page['identity']['instance']['token_uuid']
            self.manager.call.return_value=page
            await read_actor.fn(token_uuid=token,sections=['skills'])
            source_lore=[r for r in page['records'] if r['provenance']['mapping']=='pf2e.lore.specialty.v1']
            self.assertEqual(len(source_lore),2)
            for row in source_lore:self.assertEqual(row['mapped']['value']['token_uuid'],token)
