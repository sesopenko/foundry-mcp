import test from 'node:test';
import assert from 'node:assert/strict';
import {getActorTypes,readItem,listActorItems} from '../../foundry-module/scripts/actors.js';
function fixture(){
 const actor={documentName:'Actor',uuid:'Actor.a',id:'a',type:'npc',name:'Owner',items:new Map(),folder:null,compendium:null,testUserPermission:()=>true};
 const item={documentName:'Item',uuid:'Actor.a.Item.affliction',id:'affliction',name:'Unsupported',type:'affliction',parent:actor,folder:null,compendium:null,testUserPermission:()=>true,toObject(){throw Error('must not read unsupported source');}};actor.items.set(item.id,item);
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map([['a',actor]]),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>uuid===actor.uuid?actor:uuid===item.uuid?item:null}};
 return {actor,item};
}
test('production affliction admission is explicitly unsupported before source extraction',async()=>{
 const {item}=fixture();await assert.rejects(readItem({item_uuid:item.uuid}),e=>e.rpcError.code==='UnsupportedType'&&e.message.includes('production'));
 const entry=(await getActorTypes()).item_types.find(row=>row.type==='affliction');
 assert.equal(entry.source_supported,false);assert.equal(entry.mapped_supported,false);assert.equal(entry.effective_supported,false);assert.equal(entry.verification.live.status,'not_run');
});
test('unsupported afflictions do not break other owned Item navigation',async()=>{
 const {actor}=fixture();const page=await listActorItems({actor_uuid:actor.uuid});assert.equal(page.unsupported_count,1);assert.deepEqual(page.nodes,[]);
});
test('condition parent reference to runtime-disabled affliction stays explicitly unsupported',async()=>{
 const {actor,item}=fixture();const condition={...item,id:'condition',uuid:actor.uuid+'.Item.condition',type:'condition',toObject:()=>({name:'Condition',type:'condition',system:{references:{parent:{id:item.id}}}})};actor.items.set(condition.id,condition);
 const resolve=foundry.utils.fromUuid;foundry.utils.fromUuid=async uuid=>uuid===condition.uuid?condition:resolve(uuid);
 const page=await readItem({item_uuid:condition.uuid,sections:['relationships']});
 assert.deepEqual(page.records[0].mapped.value,{status:'unsupported',target_uuid:null});
});
