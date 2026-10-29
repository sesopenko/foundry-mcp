"""PF2e-specific character action/feat navigation, not effective benefit claims."""
import copy
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import AsyncMock
from fastmcp import Client
from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import _record, read_actor
from foundry_mcp_server.mcp_server.server import mcp
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_casting import casting


def ability(name='😀'*257,typ='feat'):
    uuid='Actor.a.Item.feature'
    raw=[dict(document_uuid=uuid,path=path,present=True,value=value,basis='source') for path,value in [('/name',name),('/type',typ)]]
    return dict(key='abilities:item:'+uuid,section='abilities',kind='relationship',raw=raw,mapped=dict(concept='character_ability_item',value=dict(status='resolved',target_uuid=uuid,type=typ,name=name[:256],name_truncated=len(name)>256),unit=None),provenance=dict(contributors=[{k:r[k] for k in ('document_uuid','path','basis')} for r in raw],mapping='pf2e.character.ability-reference.v1',limitations=['owned_item_reference_not_complete_or_active_ability']))


class CharacterAbilityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)
        self.identity=casting()['identity'];self.identity['type']='character'

    def page(self,rows):
        page=casting();page['identity']=copy.deepcopy(self.identity);page['records']=copy.deepcopy(rows)
        page['sections']=[dict(name='abilities',status='partial',reasons=['other_abilities_not_enumerated'])]
        page['pagination'].update(returned=len(rows),complete=True,next_cursor=None)
        return page

    async def test_exact_source_identity_unicode_and_type_scope(self):
        for typ in ('action','feat'):
            row=ability(typ=typ);self.assertTrue(_record(row,['abilities'],self.identity))
            self.manager.call.return_value=self.page([row]);await read_actor.fn(actor_uuid='Actor.a',sections=['abilities'])
        for typ in ('npc','familiar'):
            self.assertFalse(_record(ability(),['abilities'],dict(self.identity,type=typ)))

    async def test_forged_owner_token_names_types_limits_and_status_rejected(self):
        for change in (lambda r:r['raw'][0].update(document_uuid='Actor.other.Item.feature'),lambda r:r['mapped']['value'].update(token_uuid='Scene.s.Token.t'),lambda r:r['mapped']['value'].update(name_truncated=1),lambda r:r['mapped']['value'].update(name='invented'),lambda r:r['raw'][1].update(value='effect'),lambda r:r['provenance'].update(limitations=[]),lambda r:r['raw'][0].update(value='😀'*3001)):
            row=ability();change(row);self.assertFalse(_record(row,['abilities'],self.identity))
        selected=ability();prefix='Scene.s.Token.t.Actor.a';identity=copy.deepcopy(self.identity)
        identity.update(uuid=prefix,instance=dict(token_uuid='Scene.s.Token.t'))
        for raw in selected['raw']:raw['document_uuid']=raw['document_uuid'].replace('Actor.a',prefix)
        selected['key']='abilities:item:'+prefix+'.Item.feature'
        selected['mapped']['value'].update(target_uuid=prefix+'.Item.feature',token_uuid='Scene.s.Token.t')
        selected['provenance']['contributors']=[{k:r[k] for k in ('document_uuid','path','basis')} for r in selected['raw']]
        self.assertTrue(_record(selected,['abilities'],identity))
        selected['mapped']['value']['token_uuid']='Scene.s.Token.other'
        self.assertFalse(_record(selected,['abilities'],identity))

    async def test_actual_helper_dtos_preserve_source_labels_and_aggregate_denial(self):
        script=r"""
import {characterAbilityRecords} from './foundry-module/scripts/actorCharacterAbilities.js';
const actor={documentName:'Actor',uuid:'Actor.a',id:'a',type:'character',name:'Actor',items:new Map(),testUserPermission:()=>true};
for(const [id,type,allowed]of [['act','action',true],['feature','feat',true],['hidden','feat',false],['gear','equipment',true]]){
 const item={documentName:'Item',uuid:actor.uuid+'.Item.'+id,id,type,parent:actor,name:'Prepared label',folder:null,compendium:null,testUserPermission:()=>allowed,toObject(){if(!allowed)throw Error('Denied source');return Object.assign(Object.create({unrelated:'ignored'}),{type,name:'😀'.repeat(257)});}};actor.items.set(id,item);
}
globalThis.game={user:{isGM:true}};
console.log(JSON.stringify(characterAbilityRecords({document:actor,token:null})));
"""
        completed=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1],check=True)
        result=json.loads(completed.stdout);self.assertEqual(len(result['records']),3)
        self.assertIn('ability_items_denied',result['reasons'])
        for row in result['records']:self.assertTrue(_record(row,['abilities'],self.identity))

    async def test_actual_paginated_actor_reader_preserves_every_owned_ability_once(self):
        script=r"""
import {readActor} from './foundry-module/scripts/actors.js';
const actor={documentName:'Actor',uuid:'Actor.a',id:'a',type:'character',name:'Actor',folder:null,compendium:null,items:new Map(),testUserPermission:()=>true,toObject:()=>({type:'character',name:'Actor',system:{}})};
for(const [id,type,allowed]of [['act','action',true],['feat','feat',true],['feature','feat',true],['hidden','action',false],['gear','equipment',true]]){
 const item={documentName:'Item',uuid:actor.uuid+'.Item.'+id,id,type,parent:actor,name:'Display',folder:null,compendium:null,testUserPermission:()=>allowed,toObject(){if(!allowed)throw Error('Denied source');return {type,name:'Same source',system:{}};}};actor.items.set(id,item);
}
globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map([['a',actor]]),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>uuid===actor.uuid?actor:actor.items.get(uuid.split('.').at(-1))}};
const defaults=await readActor({actor_uuid:actor.uuid,sections:['identity']});
const pages=[];let cursor;do{const page=await readActor({actor_uuid:actor.uuid,sections:['abilities'],limit:2,max_bytes:8000,...(cursor?{cursor}:{})});pages.push(page);cursor=page.pagination.next_cursor;}while(cursor);
console.log(JSON.stringify({pages,defaults}));
"""
        completed=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1],check=True)
        result=json.loads(completed.stdout);self.assertGreater(len(result['pages']),1)
        rows=[]
        for page in result['pages']:
            self.manager.call.return_value=page
            rows.extend((await read_actor.fn(actor_uuid='Actor.a',sections=['abilities'],limit=2,max_bytes=8000))['records'])
        self.assertEqual(len({row['key'] for row in rows}),4)
        self.assertEqual(sorted(row['mapped']['value'].get('type','denied') for row in rows),['action','denied','feat','feat'])
        self.assertTrue(all(row['section']!='abilities' for row in result['defaults']['records']))

    async def test_empty_and_denied_sections_require_explicit_partial_diagnostics(self):
        page=self.page([]);self.manager.call.return_value=page;await read_actor.fn(actor_uuid='Actor.a',sections=['abilities'])
        page['sections'][0]['status']='complete';self.manager.call.return_value=page
        with self.assertRaises(ToolError):await read_actor.fn(actor_uuid='Actor.a',sections=['abilities'])
        denied=ability();denied.update(key='abilities:items:denied',raw=[]);denied['provenance']['contributors']=[];denied['mapped']['value']=dict(status='denied',target_uuid=None)
        page=self.page([denied]);self.manager.call.return_value=page
        with self.assertRaises(ToolError):await read_actor.fn(actor_uuid='Actor.a',sections=['abilities'])
        page['sections'][0]['reasons'].append('ability_items_denied');self.manager.call.return_value=page;await read_actor.fn(actor_uuid='Actor.a',sections=['abilities'])

    async def test_actual_discovery_describes_navigation_and_exclusions(self):
        async with Client(mcp) as client:tool=next(tool for tool in await client.list_tools() if tool.name=='read_actor')
        for text in ('owned references','not every possible action','read_item source and description'):
            self.assertIn(text,tool.description)
        self.assertIn('abilities',tool.inputSchema['$defs']['ActorSelect']['properties']['details']['items']['enum'])
