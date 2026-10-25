"""PF2e-specific effect8.6.1 explicit context relationship boundary regressions."""
import json
import subprocess
from pathlib import Path
import unittest
from unittest.mock import AsyncMock
from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_item, EFFECT_REFERENCE_ROLES, EFFECT_REFERENCE_PATHS
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_action import response


def relationship(role='origin_actor', status='resolved', target='Actor.origin', token=None):
    result=response(section='relationships',item_type='effect');row=result['records'][0]
    values=['Actor.origin',None,'Item.origin','Actor.target',None]
    values[EFFECT_REFERENCE_ROLES.index(role)]=target
    if role=='origin_item' and '.Item.' in target and not target.startswith('Compendium.'):values[0]=target.rsplit('.Item.',1)[0]
    if token is not None:values[1 if role.startswith('origin') else 4]=token
    raw=[dict(document_uuid='Item.a',path=path,present=True,value=value,basis='source') for path,value in zip(EFFECT_REFERENCE_PATHS,values)]
    mapped=dict(status=status,target_uuid=target if status=='resolved' else None)
    if status=='resolved':
        mapped.update(document_name={'actor':'Actor','token':'Token','item':'Item'}[role.split('_')[1]],name='Exact target 😀',name_truncated=False)
        if token is not None:mapped['token_uuid']=token
        if role.endswith('_token'):mapped['token_uuid']=target
    row.update(key='relationships:effect:'+role,kind='relationship',raw=raw,mapped=dict(concept='effect_'+role+'_reference',value=mapped,unit=None))
    row['provenance'].update(mapping='pf2e.effect.context-reference.v1',contributors=[{k:r[k] for k in ('document_uuid','path','basis')} for r in raw],limitations=['Source reference, not activation.'])
    return result


class ActorEffectRelationshipTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,result):
        self.manager.call.return_value=result
        return await read_item.fn(item_uuid='Item.a',sections=['relationships'])

    async def test_each_role_status_and_missing_context(self):
        for role,target in [('origin_actor','Actor.origin'),('origin_token','Scene.s.Token.o'),('origin_item','Actor.origin.Item.i'),('target_actor','Compendium.scope.nested.pack.Actor.target'),('target_token','Scene.s.Token.t')]:
            await self.read(relationship(role,target=target))
            for status in ('missing','denied','unsupported','unverified'):
                result=relationship(role,status,target)
                await self.read(result)
                for raw in result['records'][0]['raw']:raw.pop('value');raw['present']=False
                if status=='missing':await self.read(result)
                else:
                    with self.assertRaises(ToolError):await self.read(result)

    async def test_absent_null_and_empty_selected_reference_require_missing(self):
        for role in EFFECT_REFERENCE_ROLES:
            for present,value in ((False,None),(True,None),(True,'')):
                for status in ('missing','denied','unsupported','unverified'):
                    result=relationship(role,status)
                    raw=result['records'][0]['raw'][EFFECT_REFERENCE_ROLES.index(role)]
                    raw['present']=present
                    if present:raw['value']=value
                    else:raw.pop('value')
                    with self.subTest(role=role,present=present,value=value,status=status):
                        if status=='missing':await self.read(result)
                        else:
                            with self.assertRaises(ToolError):await self.read(result)

    async def test_synthetic_and_linked_context_keep_explicit_selector(self):
        for role,target in [('origin_actor','Scene.s.Token.t.Actor.a'),('target_actor','Scene.s.Token.t.Actor.a'),('origin_item','Scene.s.Token.t.Actor.a.Item.i'),('origin_actor','Actor.origin'),('origin_item','Actor.origin.Item.i')]:
            await self.read(relationship(role,target=target,token='Scene.s.Token.t'))
        bad=relationship(target='Scene.s.Token.t.Actor.a')
        with self.assertRaises(ToolError):await self.read(bad)
        for role,target in [('origin_token','Scene.s.Token.t'),('target_token','Scene.s.Token.t')]:
            bad=relationship(role,target=target);bad['records'][0]['mapped']['value']['token_uuid']='Scene.other.Token.other'
            with self.assertRaises(ToolError):await self.read(bad)
        bad=relationship('origin_item',target='Actor.origin.Item.i')
        bad['records'][0]['raw'][0]['value']='Actor.other'
        with self.assertRaises(ToolError):await self.read(bad)


    async def test_exact_role_context_and_origin_provenance(self):
        mutations=[lambda r:r.update(key='relationships:effect:unknown'),lambda r:r.update(kind='field'),lambda r:r['mapped'].update(concept='effect_active'),lambda r:r['raw'].reverse(),lambda r:r['raw'].pop(),lambda r:r['raw'][0].update(value=3),lambda r:r['raw'][0].update(document_uuid='Item.other'),lambda r:r['provenance']['contributors'].pop(),lambda r:r['provenance'].update(mapping='pf2e.effect.source.v1'),lambda r:r['provenance'].update(limitations=[]),lambda r:r['mapped']['value'].update(target_uuid='Actor.other'),lambda r:r['mapped']['value'].update(document_name='Item'),lambda r:r['mapped']['value'].update(name='x'*257),lambda r:r['mapped']['value'].update(name_truncated=0),lambda r:r['mapped']['value'].update(secret='never'),lambda r:r['mapped']['value'].update(token_uuid='Scene.other.Token.other')]
        for mutate in mutations:
            result=relationship();mutate(result['records'][0])
            with self.subTest(mutation=mutations.index(mutate)),self.assertRaises(ToolError):await self.read(result)
        for target in ['An actor name','Actor.a#anchor','Actor.a.extra','Scene.s.Token.t','Actor.a Item.i','Compendium.scope.pack.JournalEntry.id']:
            with self.subTest(target=target),self.assertRaises(ToolError):await self.read(relationship(target=target))

    async def test_denied_and_unresolved_rows_cannot_disclose_resolved_metadata(self):
        for status in ('missing','denied','unsupported','unverified'):
            for extra in [dict(target_uuid='Actor.secret'),dict(name='Secret'),dict(document_name='Actor'),dict(token_uuid='Scene.s.Token.t'),dict(name_truncated=False)]:
                result=relationship(status=status);result['records'][0]['mapped']['value'].update(extra)
                with self.subTest(status=status,extra=extra),self.assertRaises(ToolError):await self.read(result)
        result=relationship();result['identity']['type']='condition'
        with self.assertRaises(ToolError):await self.read(result)

    async def test_actual_node_relationship_pages_cross_python_boundary(self):
        script=r"""
import {readItem} from './foundry-module/scripts/actors.js';
const docs=new Map();
globalThis.game={version:'14.369',system:{id:'pf2e',version:'8.6.1'},ready:true,user:{isGM:true},actors:new Map(),items:docs};
globalThis.foundry={utils:{fromUuid:async uuid=>docs.get(uuid)}};
function doc(kind,id,type,parent=null){const d={id,uuid:parent?parent.uuid+'.Item.'+id:kind+'.'+id,name:'Exact '+id,type,documentName:kind,parent,folder:null,compendium:null,testUserPermission:()=>true};docs.set(d.uuid,d);return d;}
const origin=doc('Actor','origin','npc'),target=doc('Actor','target','npc'),item=doc('Item','origin','action'),effect=doc('Item','a','effect');
const source={name:'Effect',type:'effect',system:{context:{origin:{actor:origin.uuid,token:null,item:item.uuid},target:{actor:target.uuid,token:null}}}};
effect.toObject=()=>structuredClone(source);
const pages=[];let cursor;do{const page=await readItem({item_uuid:'Item.a',sections:['relationships'],limit:2,...(cursor?{cursor}:{})});pages.push(page);cursor=page.pagination.next_cursor;}while(cursor);
const normalPages=pages.length;
for(const context of [null,{origin:{actor:'',token:null,item:''},target:{actor:null,token:''}},undefined]){source.system.context=context;pages.push(await readItem({item_uuid:'Item.a',sections:['relationships']}));}
console.log(JSON.stringify({pages,normalPages}));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(process.returncode,0,process.stderr)
        fixture=json.loads(process.stdout);pages=fixture['pages']
        for page in pages:await self.read(page)
        rows=[row for page in pages[:fixture['normalPages']] for row in page['records']]
        self.assertEqual(len(rows),5)
        self.assertEqual([row['mapped']['value']['status'] for row in rows],['resolved','missing','resolved','resolved','missing'])
        self.assertTrue(all(row['mapped']['value']['status']=='missing' for page in pages[fixture['normalPages']:] for row in page['records']))
