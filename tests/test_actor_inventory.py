"""PF2e-specific8.6.1 Actor inventory source graph strict transport boundary."""
import copy
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import AsyncMock

from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_actor, _record, INVENTORY_LIMIT
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_action import response


def inventory(row=None):
    page=response(section='inventory')
    page['identity'].update(document_name='Actor',uuid='Actor.a',type='npc')
    page['records']=[row or relationship()]
    reasons=[]
    r=page['records'][0];concept=r['mapped']['concept'];value=r['mapped']['value']
    if concept=='inventory_kit_definition':reasons.append('kit_interpretation_pending')
    if concept=='inventory_scope' and value.get('status')=='denied':reasons.append('inventory_items_denied')
    if concept in ('inventory_container','inventory_selected_ammunition'):
        if value.get('cycle'):reasons.append('containment_cycle')
        if r['raw'][0].get('value') and value['status']!='resolved':reasons.append(('container_parent_' if concept=='inventory_container' else 'selected_ammunition_')+value['status'])
    page['sections'][0].update(status='partial' if reasons else 'complete',reasons=reasons)
    return page


def relationship(concept='inventory_item',status='resolved'):
    uuid='Actor.a.Item.item'
    if concept in ('inventory_item','inventory_kit_definition'):
        typ='kit' if concept=='inventory_kit_definition' else 'weapon'
        raw=[dict(document_uuid=uuid,path='/'+p,present=True,value=v,basis='source') for p,v in [('name','Item'),('type',typ)]]
        key='inventory:'+('kit' if typ=='kit' else 'item')+':'+uuid
        value=dict(status='resolved',target_uuid=uuid,document_name='Item',type=typ,name='Item',name_truncated=False)
    elif concept=='inventory_scope':
        raw=[];key='inventory:scope';value=dict(status=status,target_uuid=None)
    else:
        container=concept=='inventory_container'
        raw=[dict(document_uuid=uuid,path='/system/'+('containerId' if container else 'selectedAmmoId'),present=True,value='target',basis='source')]
        key='inventory:'+('container' if container else 'ammunition')+':'+uuid
        value=dict(status=status,target_uuid=None)
        if status=='resolved':value.update(target_uuid='Actor.a.Item.target',document_name='Item',type='backpack' if container else 'ammo',name='Target',name_truncated=False)
        if container:value['cycle']=False
    return dict(key=key,section='inventory',kind='relationship',raw=raw,mapped=dict(concept=concept,value=value,unit=None),provenance=dict(mapping='pf2e.actor.inventory-source.v1',limitations=INVENTORY_LIMIT.copy(),contributors=[{k:r[k] for k in ('document_uuid','path','basis')} for r in raw]))


def field(path='/system/quantity',value=0,typ='weapon',concept='quantity',present=True):
    uuid='Actor.a.Item.item';raw=dict(document_uuid=uuid,path=path,present=present,basis='source')
    if present:raw['value']=value
    return dict(key='inventory:source:'+typ+':'+uuid+':'+path,section='inventory',kind='field',raw=[raw],mapped=dict(concept=concept,value=value if present else None,unit=None),provenance=dict(mapping='pf2e.physical.source.v1',limitations=['source_only_no_effective_calculation'],contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}]))


class ActorInventoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,row):
        self.manager.call.return_value=inventory(row)
        return await read_actor.fn(actor_uuid='Actor.a',sections=['inventory'])

    async def test_canonical_items_kit_refs_and_explicit_unresolved_claims(self):
        for concept in ('inventory_item','inventory_kit_definition'):
            await self.read(relationship(concept))
        for concept in ('inventory_container','inventory_selected_ammunition'):
            for status in ('resolved','missing','denied','unsupported'):
                await self.read(relationship(concept,status))
        for status in ('empty','denied'):
            await self.read(relationship('inventory_scope',status))
        row=relationship('inventory_container');row['mapped']['value']['cycle']=True
        await self.read(row)

    async def test_physical_source_null_zero_absence_price_basis_and_type_overrides(self):
        for row in (field(),field('/system/price/per',10,concept='price_per_quantity'),field('/system/equipped/invested',None,concept='investment_state'),field('/system/quantity',present=False)):
            await self.read(row)
        for typ,path,concept in [('treasure','/system/equipped/invested','investment_state'),('armor','/system/usage/value','usage_code'),('shield','/system/usage/value','usage_code')]:
            row=field(path,None,typ,concept)
            if path.endswith('/usage/value'):row['provenance']['limitations']=[]
            with self.subTest(typ=typ,path=path),self.assertRaises(ToolError):await self.read(row)

    async def test_source_values_concepts_limitations_and_private_paths_are_strict(self):
        changes=[lambda r:r['mapped'].update(concept='effective_quantity'),lambda r:r['mapped'].update(value=4),lambda r:r['provenance'].update(limitations=[]),lambda r:r['raw'][0].update(value=True),lambda r:r['raw'][0].update(document_uuid='Actor.other.Item.item'),lambda r:r['raw'][0].update(path='/flags/private'),lambda r:r.update(key='inventory:source:kit:Actor.a.Item.item:/system/quantity')]
        for mutate in changes:
            row=field();mutate(row)
            with self.subTest(row=row),self.assertRaises(ToolError):await self.read(row)
        for path in ('/system/description/value','/system/identification/unidentified/data/description/value','/system/subitems/0/system/quantity'):
            with self.subTest(path=path),self.assertRaises(ToolError):await self.read(field(path,'secret'))

    async def test_cross_owner_mismatched_claims_denied_metadata_and_noncanonical_ids_rejected(self):
        changes=[lambda r:r['mapped']['value'].update(target_uuid='Actor.other.Item.target'),lambda r:r['mapped']['value'].update(target_uuid='Actor.a.Item.wrong'),lambda r:r['mapped']['value'].update(name='x'*257),lambda r:r['mapped']['value'].update(token_uuid='Scene.s.Token.t'),lambda r:r['mapped']['value'].update(eligible=True),lambda r:r['provenance'].update(mapping='pf2e.actor.casting-source.v1')]
        for mutate in changes:
            row=relationship('inventory_container');mutate(row)
            with self.subTest(row=row),self.assertRaises(ToolError):await self.read(row)
        row=relationship('inventory_container','denied');row['mapped']['value']['name']='Secret'
        with self.assertRaises(ToolError):await self.read(row)
        for suffix in ('bad id','bad#id','nested.Item.id','x'*513):
            row=field();uuid='Actor.a.Item.'+suffix;row['key']='inventory:source:weapon:'+uuid+':/system/quantity';row['raw'][0]['document_uuid']=uuid;row['provenance']['contributors'][0]['document_uuid']=uuid
            with self.subTest(suffix=suffix),self.assertRaises(ToolError):await self.read(row)

    async def test_token_context_and_empty_claims_cannot_fabricate_resolution(self):
        identity=inventory()['identity'];identity.update(uuid='Scene.s.Token.t.Actor.a',instance=dict(token_uuid='Scene.s.Token.t'))
        row=relationship('inventory_container');row['key']=row['key'].replace('Actor.a','Scene.s.Token.t.Actor.a');row['raw'][0]['document_uuid']='Scene.s.Token.t.Actor.a.Item.item';row['provenance']['contributors'][0]['document_uuid']=row['raw'][0]['document_uuid'];row['mapped']['value'].update(target_uuid='Scene.s.Token.t.Actor.a.Item.target',token_uuid='Scene.s.Token.t')
        self.assertTrue(_record(row,['inventory'],identity))
        for token in (None,'Scene.wrong.Token.t'):
            bad=copy.deepcopy(row)
            if token is None:bad['mapped']['value'].pop('token_uuid')
            else:bad['mapped']['value']['token_uuid']=token
            self.assertFalse(_record(bad,['inventory'],identity))
        for present,value in ((True,None),(True,''),(False,None)):
            for status in ('resolved','denied','unsupported'):
                row=relationship('inventory_container',status);raw=row['raw'][0];raw['present']=present
                if present:raw['value']=value
                else:raw.pop('value')
                with self.subTest(present=present,value=value,status=status),self.assertRaises(ToolError):await self.read(row)

    async def test_serialized_attachment_retains_parent_source_identity(self):
        row=field('/system/subitems/0/_id','same-as-owned-id',concept='attachment_local_id')
        row['provenance']['limitations']=['serialized_source_not_document','attachment_interpretation_pending']
        await self.read(row)
        row['mapped']['value']={'target_uuid':'Actor.a.Item.same-as-owned-id'}
        with self.assertRaises(ToolError):await self.read(row)

    async def test_actual_javascript_records_cross_strict_boundary_for_all_actor_types(self):
        script=r"""
import {actorInventoryRecords} from './foundry-module/scripts/actorInventory.js';
globalThis.game={user:{isGM:true}};
const results=[];
for(const type of ['character','npc','familiar']){
 const actor={documentName:'Actor',id:'a',uuid:'Actor.a',name:'Actor',type,items:new Map(),testUserPermission:()=>true};
 const add=(id,type,system={},allowed=true)=>{const source={name:id,type,system};const item={id,uuid:actor.uuid+'.Item.'+id,documentName:'Item',type,name:'Prepared '+id,parent:actor,testUserPermission:()=>allowed,toObject:()=>structuredClone(source)};actor.items.set(id,item);};
 add('pack','backpack',{containerId:'pack2'});add('pack2','backpack',{containerId:'pack'});
 add('tail','weapon',{quantity:0,price:{per:10,value:{gp:2}},equipped:{invested:null},containerId:'pack',selectedAmmoId:'ammo',subitems:[{_id:'ammo',name:'Serialized',type:'weapon'}]});
 add('ammo','ammo',{containerId:'missing'});add('book','book',{});add('kit','kit',{});add('denied','equipment',{},false);
 add('wrong','equipment',{containerId:'wrong2'});add('wrong2','equipment',{containerId:'wrong'});
 results.push({type,...actorInventoryRecords({document:actor})});
}
console.log(JSON.stringify(results));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(process.returncode,0,process.stderr)
        results=json.loads(process.stdout)
        for result in results:
            identity=inventory()['identity'];identity['type']=result['type']
            self.assertGreater(len(result['records']),150)
            self.assertIn('kit_interpretation_pending',result['reasons'])
            for row in result['records']:
                with self.subTest(type=result['type'],key=row['key']):self.assertTrue(_record(row,['inventory'],identity),row)

    async def test_diagnostic_partial_status_cannot_be_forged_complete(self):
        for row in (relationship('inventory_container','denied'),relationship('inventory_kit_definition'),relationship('inventory_scope','denied')):
            page=inventory(row);page['sections'][0].update(status='complete',reasons=[])
            self.manager.call.return_value=page
            with self.assertRaises(ToolError):await read_actor.fn(actor_uuid='Actor.a',sections=['inventory'])
        page=inventory();page['sections'][0].update(status='partial',reasons=[])
        self.manager.call.return_value=page
        with self.assertRaises(ToolError):await read_actor.fn(actor_uuid='Actor.a',sections=['inventory'])
