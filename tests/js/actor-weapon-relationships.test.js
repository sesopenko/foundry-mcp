import test from 'node:test';
import assert from 'node:assert/strict';
import {readItem} from '../../foundry-module/scripts/actors.js';
function fixture(synthetic=false){
 const docs=new Map();const actor={documentName:'Actor',uuid:synthetic?'Scene.s.Token.t.Actor.a':'Actor.a',id:'a',name:'Owner',type:'npc',folder:null,compendium:null,items:new Map(),testUserPermission:()=>true};
 const source={name:'Weapon',type:'weapon',system:{selectedAmmoId:'ammo'}};
 const weapon={documentName:'Item',uuid:actor.uuid+'.Item.weapon',id:'weapon',name:'Weapon',type:'weapon',parent:actor,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
 const ammo={...weapon,uuid:actor.uuid+'.Item.ammo',id:'ammo',name:'Stored ammo',type:'ammo',toObject(){throw Error('target source forbidden');}};
 for(const item of [weapon,ammo]){actor.items.set(item.id,item);docs.set(item.uuid,item);}docs.set(actor.uuid,actor);
 const scene={documentName:'Scene',uuid:'Scene.s',name:'Scene',testUserPermission:()=>true};
 const token={documentName:'Token',uuid:'Scene.s.Token.t',id:'t',name:'Token',actor,baseActor:actor,parent:scene,isLinked:!synthetic,testUserPermission:()=>true};docs.set(token.uuid,token);
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map(),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>docs.get(uuid)}};
 return {actor,weapon,ammo,token,source,docs};
}
test('stored ammunition selection resolves actual ammo or weapon identity with token follow-up',async()=>{
 for(const synthetic of [false,true])for(const type of ['ammo','weapon']){
  const f=fixture(synthetic);f.ammo.type=type;
  const page=await readItem({item_uuid:f.weapon.uuid,token_uuid:f.token.uuid,sections:['relationships']});
  const row=page.records[0],value=row.mapped.value;assert.equal(value.status,'resolved');assert.equal(value.target_uuid,f.ammo.uuid);assert.equal(value.token_uuid,f.token.uuid);assert.equal(value.type,type);assert.equal(row.provenance.mapping,'pf2e.weapon.selected-ammo.v1');
  assert.equal(row.raw[0].value,'ammo');assert.equal(page.sections[0].status,'complete');
  f.ammo.toObject=()=>({name:f.ammo.name,type});assert.equal((await readItem({item_uuid:value.target_uuid,token_uuid:value.token_uuid,sections:['identity']})).identity.uuid,f.ammo.uuid);
 }
});
test('stored ammunition missing denied unsupported and standalone states do not expose target metadata',async()=>{
 for(const [change,status]of [[f=>f.source.system.selectedAmmoId=null,'missing'],[f=>delete f.source.system.selectedAmmoId,'missing'],[f=>f.actor.items.delete('ammo'),'missing'],[f=>f.ammo.testUserPermission=()=>false,'denied'],[f=>f.ammo.type='consumable','unsupported']]){
  const f=fixture();change(f);const row=(await readItem({item_uuid:f.weapon.uuid,sections:['relationships']})).records[0];assert.deepEqual(row.mapped.value,{status,target_uuid:null});
 }
 const f=fixture();f.weapon.parent=null;f.weapon.uuid='Item.weapon';f.docs.set(f.weapon.uuid,f.weapon);
 assert.deepEqual((await readItem({item_uuid:f.weapon.uuid,sections:['relationships']})).records[0].mapped.value,{status:'unverified',target_uuid:null});
});
test('weapon source reads do not inspect ammo and relationship snapshots detect concurrent target changes',async()=>{
 const f=fixture();const items=f.actor.items;f.actor.items={values(){throw Error('source-only must not inspect owner Items');}};
 await readItem({item_uuid:f.weapon.uuid,sections:['source']});f.actor.items=items;
 let reads=0;const original=f.weapon.toObject;f.weapon.toObject=()=>{if(++reads===2)f.ammo.name='Changed';return original();};
 await assert.rejects(readItem({item_uuid:f.weapon.uuid,sections:['relationships']}),e=>e.rpcError.code==='ContentChanged');
 f.source.system.selectedAmmoId={secret:'hidden'};
 await assert.rejects(readItem({item_uuid:f.weapon.uuid,sections:['relationships']}),e=>e.rpcError.code==='ReadFailed'&&!e.message.includes('hidden'));
});
