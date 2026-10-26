"""PF2e-specific declared Strike fields and generated origin strict boundary."""
import copy
import json
from pathlib import Path
import subprocess
import unittest
from fastmcp import Client
from unittest.mock import AsyncMock
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from foundry_mcp_server.mcp_server.actors import read_actor
from foundry_mcp_server.mcp_server.server import mcp
from foundry_mcp_server.mcp_server.actors import _record, _strike_section
from test_actor_casting import casting


def field(path='/system/actions/0/totalModifier',value=12,concept='current_strike_attack_modifier'):
    raw=dict(document_uuid='Actor.a',path=path,present=True,value=value,basis='transformed')
    return dict(key='strikes:current:'+path,section='strikes',kind='field',raw=[raw],mapped=dict(concept=concept,value=value,unit=None),provenance=dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.actor.strike-current.v1',limitations=['current_strike_not_target_context']))


class StrikeCurrentTests(unittest.TestCase):
    def setUp(self):
        self.identity=casting()['identity'];self.identity['type']='character'

    def test_declared_primitive_field_and_closed_paths(self):
        self.assertTrue(_record(field(),['strikes'],self.identity))
        for path in ('/system/actions/256/label','/system/actions/00/label','/system/actions/0/modifiers','/system/actions/0/variants/16/label','/system/actions/0/altUsages/0/altUsages/0/altUsages/0/altUsages/0/altUsages/0/label'):
            self.assertFalse(_record(field(path,'label','current_strike_label'),['strikes'],self.identity))
        for value in (True,'12',float('inf')):
            self.assertFalse(_record(field(value=value),['strikes'],self.identity))

    def test_generated_origin_has_no_document_selector(self):
        row=field('/system/actions/0/type','strike','current_strike_type');row.update(key='strikes:origin:/system/actions/0',kind='relationship')
        row['mapped']=dict(concept='current_strike_origin',value=dict(status='generated',target_uuid=None),unit=None)
        row['provenance']['mapping']='pf2e.actor.strike-origin.v1'
        self.assertTrue(_record(row,['strikes'],self.identity))
        row['mapped']['value']['target_uuid']='Actor.a.Item.generated'
        self.assertFalse(_record(row,['strikes'],self.identity))

    def test_source_origin_unicode_and_canonical_owner_token_are_strict(self):
        row=field('/system/actions/0/type','strike','current_strike_type');row.update(key='strikes:origin:/system/actions/0',kind='relationship')
        name='😀'*257;uuid='Actor.a.Item.weapon'
        row['raw'] += [dict(document_uuid=uuid,path='/name',present=True,value=name,basis='source'),dict(document_uuid=uuid,path='/type',present=True,value='weapon',basis='source')]
        row['mapped']=dict(concept='current_strike_origin',value=dict(status='resolved',target_uuid=uuid,type='weapon',name='😀'*256,name_truncated=True),unit=None)
        row['provenance'].update(mapping='pf2e.actor.strike-origin.v1',contributors=[{k:r[k] for k in ('document_uuid','path','basis')} for r in row['raw']])
        self.assertTrue(_record(row,['strikes'],self.identity))
        for key,value in [('target_uuid','Actor.other.Item.weapon'),('type','melee'),('name_truncated',1),('token_uuid','Scene.s.Token.t')]:
            bad=copy.deepcopy(row);bad['mapped']['value'][key]=value
            self.assertFalse(_record(bad,['strikes'],self.identity))
        token_identity=copy.deepcopy(self.identity);prefix='Scene.s.Token.t.Actor.a'
        token_identity.update(uuid=prefix,instance=dict(token_uuid='Scene.s.Token.t'))
        selected=copy.deepcopy(row)
        for witness in selected['raw']:witness['document_uuid']=witness['document_uuid'].replace('Actor.a',prefix)
        selected['mapped']['value'].update(target_uuid=prefix+'.Item.weapon',token_uuid='Scene.s.Token.t')
        selected['provenance']['contributors']=[{k:r[k] for k in ('document_uuid','path','basis')} for r in selected['raw']]
        self.assertTrue(_record(selected,['strikes'],token_identity))
        selected['mapped']['value']['token_uuid']='Scene.s.Token.other'
        self.assertFalse(_record(selected,['strikes'],token_identity))

    def test_diagnostics_are_mandatory_without_offpage_requirements(self):
        row=field();section=dict(name='strikes',status='partial',reasons=['target_context_not_evaluated','current_strike_damage_unsupported'])
        self.assertTrue(_strike_section([row],section,self.identity))
        section['reasons'].remove('target_context_not_evaluated')
        self.assertFalse(_strike_section([row],section,self.identity))
        npc=copy.deepcopy(self.identity);npc['type']='npc'
        self.assertTrue(_strike_section([],dict(status='partial',reasons=['other_attacks_pending']),npc))
        marker=field('/system/actions/0/variants',[],'current_strike_variants');marker['mapped']['value']=None
        child=field('/system/actions/0/variants/0/penalty',-5,'current_strike_map_penalty')
        section['reasons'].append('target_context_not_evaluated')
        self.assertFalse(_strike_section([marker,child],section,self.identity))

    def test_accessor_capability_is_distinct_from_absent(self):
        path='/system/actions/0/variants/0/label'
        row=field(path);row.update(key='strikes:unavailable:'+path,raw=[])
        row['mapped']=dict(concept='current_strike_field_support',value=dict(status='unsupported',reason='accessor_not_read',path=path),unit=None)
        row['provenance'].update(mapping='pf2e.actor.strike-capability.v1',contributors=[])
        self.assertTrue(_record(row,['strikes'],self.identity))
        row['mapped']['value']['reason']='anything'
        self.assertFalse(_record(row,['strikes'],self.identity))

    def test_text_fragments_use_exact_utf16_positions(self):
        path='/system/actions/0/description';row=field(path,'😀abc','current_strike_description')
        row.update(key='strikes:current:'+path+':text:0',kind='text',text=dict(path=path,start=0,end=5,total=1005,complete=False))
        row['mapped']['value']=None
        self.assertTrue(_record(row,['strikes'],self.identity))
        for change in (lambda r:r['text'].update(end=4),lambda r:r['text'].update(complete=True),lambda r:r.update(key='strikes:current:'+path+':text:-1')):
            bad=copy.deepcopy(row);change(bad);self.assertFalse(_record(bad,['strikes'],self.identity))

    def test_actual_helper_rows_cross_strict_boundary_for_character_and_npc(self):
        script=r"""
import {actorStrikeSnapshot} from './foundry-module/scripts/actorStrikes.js';
const results=[];globalThis.game={user:{isGM:true}};
for(const type of ['character','npc']){
 const actor={documentName:'Actor',type,uuid:'Actor.a',id:'a',name:'Actor',items:new Map(),testUserPermission:()=>true};
 const item={documentName:'Item',id:'w',uuid:'Actor.a.Item.w',name:'Display',type:type==='character'?'weapon':'melee',parent:actor,testUserPermission:()=>true,toObject:()=>({type:type==='character'?'weapon':'melee',name:'Source'})};actor.items.set('w',item);
 const action={type:'strike',slug:'strike',label:'Strike',glyph:'A',description:'😀'.repeat(600),breakdown:'Attack',ready:true,canAttack:true,totalModifier:12,item,visible:true,handsAvailable:false,sourceId:'w',attackRollType:'attack',options:['duplicate','duplicate'],domains:[],traits:[{name:'attack',label:'Attack',description:null}],weaponTraits:[],variants:[{penalty:0,label:'First'}],altUsages:[]};
 Object.defineProperty(action.variants[0],'label',{get(){throw Error('Getter prohibited');}});
 const generated={...action,item:{...item,id:'ephemeral'},variants:[],description:''};
 action.altUsages=[generated];actor.system={actions:[action,{type:'area-fire'}]};
 results.push({type,...actorStrikeSnapshot({document:actor,token:null})});
}
console.log(JSON.stringify(results));
"""
        result=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1],check=True)
        for snapshot in json.loads(result.stdout):
            identity=copy.deepcopy(self.identity);identity['type']=snapshot['type']
            for row in snapshot['records']:
                with self.subTest(type=snapshot['type'],key=row['key']):self.assertTrue(_record(row,['strikes'],identity))
            self.assertTrue(any(row['kind']=='text' for row in snapshot['records']))
            self.assertTrue(any(row['key'].startswith('strikes:unavailable:') for row in snapshot['records']))


class StrikeDiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_integrated_pages_preserve_npc_source_and_current_views(self):
        script=r"""
import {readActor} from './foundry-module/scripts/actors.js';
const results=[];
for(const type of ['character','npc']){
 const actor={documentName:'Actor',uuid:'Actor.a',id:'a',type,name:'Actor',folder:null,compendium:null,items:new Map(),testUserPermission:()=>true,toObject:()=>({type,name:'Actor',system:{}})};
 const kind=type==='character'?'weapon':'melee',item={documentName:'Item',uuid:'Actor.a.Item.w',id:'w',type:kind,name:'Display',parent:actor,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>({type:kind,name:'😀'.repeat(257),system:{}})};actor.items.set('w',item);
 const generated={...item,id:'generated'};
 actor.system={actions:[{type:'strike',slug:'basic',label:'Basic',item:generated,altUsages:[]},{type:'strike',slug:'owned',label:'Owned',item,description:'😀'.repeat(600),altUsages:[]}]};
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map([['a',actor]]),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>uuid===actor.uuid?actor:item}};
 const pages=[];let cursor;do{const page=await readActor({actor_uuid:actor.uuid,sections:['strikes'],limit:3,max_bytes:8000,...(cursor?{cursor}:{})});pages.push(page);cursor=page.pagination.next_cursor;}while(cursor);
 results.push({type,pages});
}
console.log(JSON.stringify(results));
"""
        completed=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1],check=True)
        manager=AsyncMock();register_foundry_manager(manager)
        for snapshot in json.loads(completed.stdout):
            rows=[]
            for page in snapshot['pages']:
                manager.call.return_value=page
                rows.extend((await read_actor.fn(actor_uuid='Actor.a',sections=['strikes'],limit=3,max_bytes=8000))['records'])
            self.assertGreater(len(snapshot['pages']),1)
            self.assertEqual(len([r for r in rows if r['mapped']['concept']=='npc_attack_item']),1 if snapshot['type']=='npc' else 0)
            origins=[r for r in rows if r['provenance']['mapping']=='pf2e.actor.strike-origin.v1']
            self.assertEqual([r['mapped']['value']['status'] for r in origins],['generated','resolved'])
            self.assertTrue(origins[-1]['mapped']['value']['name_truncated'])

    async def test_actual_discovery_publishes_complete_current_contract(self):
        async with Client(mcp) as client:
            tool=next(tool for tool in await client.list_tools() if tool.name=='read_actor')
        for text in ('pf2e.actor.strike-current.v1','pf2e.actor.strike-origin.v1','pf2e.actor.strike-capability.v1','strikes:unavailable:<path>','current_strike_damage_unsupported','300000 UTF-16','target_uuid:null','never invented UUIDs'):
            self.assertIn(text,tool.description)
