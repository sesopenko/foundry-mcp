"""PF2e-specific8.6.1 persisted feat claims, never active-benefit assertions."""
import copy
import unittest
from unittest.mock import AsyncMock
from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_item, _validate
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_feat import feat_source, javascript
from test_actor_action import response


def reference(path='/system/selfEffect/uuid', claim='Item.effect', status='unverified', *, present=True, target=None):
    result=response(path,claim,present=present,item_type='feat',section='relationships')
    row=result['records'][0]
    concept=('feat_granted_by_reference' if '/grantedBy' in path else 'feat_grant_reference' if '/itemGrants' in path else 'feat_suppressed_feature_reference' if '/suppressedFeatures' in path else 'feat_self_effect_reference')
    row.update(key='relationships:feat:'+path,kind='relationship',mapped=dict(concept=concept,value=target or dict(status=status,target_uuid=None),unit=None))
    row['provenance'].update(mapping='pf2e.feat.reference.v1',limitations=['persisted_reference_not_active_benefit'])
    return result


class ActorFeatGrantTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,result,section='relationships'):
        self.manager.call.return_value=result
        return await read_item.fn(item_uuid='Item.a',sections=[section])

    async def test_empty_opaque_grant_key_is_a_source_key(self):
        from foundry_mcp_server.mcp_server.actors import _feat_spec
        self.assertEqual(_feat_spec('/flags/pf2e/itemGrants//id')[0],'feat_grant_item_id')
        self.assertIsNotNone(_feat_spec('/flags/pf2e/itemGrants//nested'))
        await self.read(feat_source('/flags/pf2e/itemGrants//id','local'),'source')
        await self.read(reference('/flags/pf2e/itemGrants//id','local','unowned'))

    async def test_selected_flag_source_and_empty_markers(self):
        for path,value in [('/flags/pf2e/itemGrants',{}),('/flags/pf2e/itemGrants/a~1b~0c/id','local'),('/flags/pf2e/itemGrants/a/onDelete','future'),('/flags/pf2e/itemGrants/a/nested',False),('/flags/pf2e/itemGrants/a/nested',None),('/flags/pf2e/grantedBy',None),('/flags/pf2e/grantedBy/id','local'),('/flags/pf2e/grantedBy/onDelete','cascade')]:
            await self.read(feat_source(path,value),'source')
        for path,value in [('/flags/pf2e/itemGrants',None),('/flags/pf2e/itemGrants',{'a':{}}),('/flags/pf2e/itemGrants/a~2/id','local'),('/flags/pf2e/itemGrants/a/id',None),('/flags/pf2e/itemGrants/a/nested','false'),('/flags/pf2e/privateSelection',{}),('/flags/pf2e/grantedBy',{})]:
            with self.subTest(path=path),self.assertRaises(ToolError):await self.read(feat_source(path,value),'source')

    async def test_relationship_markers_and_unowned_claims(self):
        for path,claim,status,present in [('/flags/pf2e/itemGrants',{},'empty',True),('/flags/pf2e/itemGrants',None,'missing',False),('/flags/pf2e/grantedBy',None,'unassociated',True),('/system/selfEffect',None,'unassociated',True),('/system/subfeatures/suppressedFeatures',[],'empty',True),('/flags/pf2e/itemGrants/a/id','local','unowned',True),('/flags/pf2e/grantedBy/id','local','unowned',True),('/system/selfEffect/uuid','','unsupported',True)]:
            await self.read(reference(path,claim,status,present=present))
        for status in ('missing','denied','unsupported','unverified'):
            await self.read(reference(status=status))

    async def test_resolved_uuid_identity_and_forgery_rejection(self):
        target=dict(status='resolved',target_uuid='Item.effect',document_name='Item',type='effect',name='Effect',name_truncated=False)
        await self.read(reference(target=target))
        for modify in [lambda r:r['mapped']['value'].update(target_uuid='Item.other'),lambda r:r['mapped']['value'].update(type='feat'),lambda r:r['mapped']['value'].update(token_uuid='Scene.a.Token.b'),lambda r:r['raw'][0].update(document_uuid='Item.other'),lambda r:r['provenance'].update(limitations=[]),lambda r:r.update(key='forged')]:
            bad=reference(target=copy.deepcopy(target));modify(bad['records'][0])
            with self.assertRaises(ToolError):await self.read(bad)
        target.update(target_uuid='Scene.s.Token.t.Actor.a.Item.e',token_uuid='Scene.s.Token.t')
        await self.read(reference(claim=target['target_uuid'],target=target))
        bad=reference(claim=target['target_uuid'],target=copy.deepcopy(target));bad['records'][0]['mapped']['value']['token_uuid']='Scene.s.Token.other'
        with self.assertRaises(ToolError):await self.read(bad)

    async def test_non_pf2e_boundary_and_discovery_contract(self):
        bad=reference();bad['runtime']['system_id']='other'
        with self.assertRaises(ToolError):await self.read(bad)
        for token in ('feat_grant_reference','feat_granted_by_reference','feat_self_effect_reference','feat_suppressed_feature_reference','unowned','200','No recursive expansion','persisted_reference_not_active_benefit'):
            self.assertIn(token,read_item.fn.__doc__)

    async def test_actual_javascript_flag_descriptors(self):
        fields=javascript("""
import {featGrantFields} from './foundry-module/scripts/actorFeatGrants.js';
console.log(JSON.stringify([...featGrantFields({type:'feat',flags:{pf2e:{itemGrants:{'a/b~c':{id:'local',onDelete:'custom',nested:null}},grantedBy:{id:'parent',onDelete:'detach'}}}}),...featGrantFields({type:'feat'}),...featGrantFields({type:'feat',flags:{pf2e:{itemGrants:{},grantedBy:null}}})]));
""")
        for field in fields:
            row=feat_source(field['path'],field.get('value'),present=field['present'])
            row['records'][0]['mapped'].update(concept=field['concept'],value=field.get('value'))
            await self.read(row,'source')

    async def test_actual_paginated_owned_reader_and_owner_isolation(self):
        pages=javascript(r"""
import {readItem} from './foundry-module/scripts/actors.js';
const actor={id:'owner',uuid:'Actor.owner',name:'Owner',type:'character',documentName:'Actor',parent:null,folder:null,compendium:null,testUserPermission:()=>true,items:new Map()};
const source={name:'Feat',type:'feat',system:{selfEffect:{uuid:'Item.effect',name:'Effect'},subfeatures:{suppressedFeatures:['Item.otherfeat']}},flags:{pf2e:{itemGrants:{'a/b~c':{id:'benefit',onDelete:'detach',nested:true}},grantedBy:{id:'parent',onDelete:'cascade'}}}};
function item(id,type,parent=null){return {id,uuid:parent?parent.uuid+'.Item.'+id:'Item.'+id,name:id,type,documentName:'Item',parent,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>{if(id!=='a')throw Error('target source must never be read');return structuredClone(source);}};}
const feat=item('a','feat',actor),benefit=item('benefit','action',actor),parent=item('parent','feat',actor),effect=item('effect','effect'),other=item('otherfeat','feat');
for(const doc of [feat,benefit,parent])actor.items.set(doc.id,doc);
const docs=new Map([actor,feat,benefit,parent,effect,other].map(d=>[d.uuid,d]));
globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map([['owner',actor]]),items:new Map([['effect',effect],['otherfeat',other]])};globalThis.foundry={utils:{fromUuid:async uuid=>docs.get(uuid)??null}};
let cursor;const pages=[];do{const page=await readItem({item_uuid:feat.uuid,sections:['source','relationships'],limit:3,max_bytes:8000,...(cursor?{cursor}:{})});pages.push(page);cursor=page.pagination.next_cursor;}while(cursor);console.log(JSON.stringify(pages));
""")
        self.assertGreater(len(pages),3)
        for page in pages:_validate(page,'read',limit=3,max_bytes=8000,sections=['source','relationships'])
        rows=[row for page in pages for row in page['records']]
        refs={row['mapped']['concept']:row for row in rows if row['section']=='relationships'}
        self.assertEqual(refs['feat_grant_reference']['mapped']['value']['target_uuid'],'Actor.owner.Item.benefit')
        self.assertEqual(refs['feat_granted_by_reference']['mapped']['value']['target_uuid'],'Actor.owner.Item.parent')
        self.assertEqual(refs['feat_self_effect_reference']['mapped']['value']['type'],'effect')
        self.assertEqual(refs['feat_suppressed_feature_reference']['mapped']['value']['type'],'feat')
        self.assertTrue(any(row['raw'][0]['path']=='/flags/pf2e/itemGrants/a~1b~0c/nested' for row in rows))
        original=next(page for page in pages if any(row['mapped']['concept']=='feat_grant_reference' for row in page['records']))
        bad=copy.deepcopy(original)
        next(row for row in bad['records'] if row['mapped']['concept']=='feat_grant_reference')['mapped']['value']['target_uuid']='Actor.other.Item.benefit'
        with self.assertRaises(ToolError):_validate(bad,'read',limit=3,max_bytes=8000,sections=['source','relationships'])
