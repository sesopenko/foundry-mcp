import test from 'node:test';
import assert from 'node:assert/strict';
import {actorInventoryRecords} from '../../foundry-module/scripts/actorInventory.js';
function fixture(type='npc',synthetic=false){
 globalThis.game={user:{isGM:true}};
 const actor={documentName:'Actor',id:'a',uuid:synthetic?'Scene.s.Token.t.Actor.a':'Actor.a',name:'Actor',type,items:new Map(),testUserPermission:()=>true};
 const target={document:actor};
 if(synthetic)target.token={uuid:'Scene.s.Token.t',name:'Token',parent:{uuid:'Scene.s',name:'Scene'},isLinked:false,baseActor:null};
 const add=(id,type,system={})=>{const source={name:id,type,system};let reads=0;const item={id,uuid:actor.uuid+'.Item.'+id,documentName:'Item',type,name:id,parent:actor,testUserPermission:()=>true,toObject:()=>{reads++;return structuredClone(source);}};actor.items.set(id,item);return {item,source,get reads(){return reads;}};};
 return {actor,target,add};
}
const rows=(result,concept)=>result.records.filter(r=>r.mapped.concept===concept);
const byId=(result,concept,id)=>rows(result,concept).find(r=>r.raw[0]?.document_uuid.endsWith('.Item.'+id));
test('owner-wide nested and disconnected possessions appear once without recursive hydration or valuation',()=>{
 const f=fixture(),outer=f.add('outer','backpack',{containerId:null}),inner=f.add('inner','backpack',{containerId:'outer'}),coins=f.add('coins','treasure',{containerId:'inner',quantity:21,price:{value:{gp:1,sp:0},per:10},equipped:{carryType:'stowed'}}),loose=f.add('loose','equipment',{containerId:null,equipped:{invested:false,handsHeld:0}});
 const before=JSON.stringify([outer.source,inner.source,coins.source,loose.source]),result=actorInventoryRecords(f.target);
 assert.equal(rows(result,'inventory_item').length,4);assert.equal(new Set(result.records.map(r=>r.key)).size,result.records.length);
 assert.equal(byId(result,'inventory_container','inner').mapped.value.target_uuid,outer.item.uuid);assert.equal(byId(result,'inventory_container','coins').mapped.value.target_uuid,inner.item.uuid);
 assert.equal(byId(result,'quantity','coins').raw[0].value,21);assert.equal(byId(result,'price_per_quantity','coins').raw[0].value,10);assert.equal(byId(result,'price_gold','coins').raw[0].value,1);assert.equal(byId(result,'investment_state','loose').raw[0].value,false);
 assert.deepEqual(result.reasons,[]);assert.deepEqual([outer.reads,inner.reads,coins.reads,loose.reads],[1,1,1,1]);assert.equal(JSON.stringify([outer.source,inner.source,coins.source,loose.source]),before);
 assert.ok(!JSON.stringify(result).includes('sale_price'));
});
test('cycles including rootless components and incoming tails stay explicit; all actual identities occur once',()=>{
 const f=fixture();f.add('a','backpack',{containerId:'b'});f.add('b','backpack',{containerId:'a'});f.add('tail','equipment',{containerId:'b'});f.add('self','backpack',{containerId:'self'});f.add('plain','equipment',{containerId:null});
 const result=actorInventoryRecords(f.target);
 for(const id of ['a','b','tail','self'])assert.equal(byId(result,'inventory_container',id).mapped.value.cycle,true);
 assert.equal(byId(result,'inventory_container','plain').mapped.value.cycle,false);assert.equal(rows(result,'inventory_item').length,5);assert.deepEqual(result.reasons,['containment_cycle']);
});
test('orphan denied and unsupported parent claims preserve raw IDs without target identity leakage',()=>{
 const f=fixture();f.add('orphan','equipment',{containerId:'gone'});const denied=f.add('secret','backpack');denied.item.testUserPermission=()=>false;denied.item.toObject=()=>{throw Error('denied source');};f.add('deniedchild','ammo',{containerId:'secret'});f.add('wrong','action');f.add('wrongchild','treasure',{containerId:'wrong'});
 const result=actorInventoryRecords(f.target);
 for(const [id,status,claim]of [['orphan','missing','gone'],['deniedchild','denied','secret'],['wrongchild','unsupported','wrong']]){const row=byId(result,'inventory_container',id);assert.deepEqual(row.mapped.value,{status,target_uuid:null,cycle:false});assert.equal(row.raw[0].value,claim);}
 assert.equal(rows(result,'inventory_item').length,3);assert.deepEqual(rows(result,'inventory_scope')[0].raw,[]);assert.deepEqual(rows(result,'inventory_scope')[0].mapped.value,{status:'denied',target_uuid:null});assert.ok(!result.records.some(r=>r.raw.some(v=>v.document_uuid===denied.item.uuid)));
 assert.deepEqual(result.reasons,['container_parent_denied','container_parent_missing','container_parent_unsupported','inventory_items_denied']);
});
test('selected ammunition is explicit same-owner evidence while multiple stacks retain individual identities',()=>{
 const f=fixture(),ammo1=f.add('ammo1','ammo',{quantity:20}),ammo2=f.add('ammo2','ammo',{quantity:3});f.add('weapon','weapon',{selectedAmmoId:'ammo2'});f.add('other','weapon',{});
 const result=actorInventoryRecords(f.target);assert.equal(rows(result,'inventory_item').length,4);assert.equal(byId(result,'inventory_selected_ammunition','weapon').mapped.value.target_uuid,ammo2.item.uuid);assert.deepEqual(byId(result,'inventory_selected_ammunition','other').mapped.value,{status:'missing',target_uuid:null});assert.equal(byId(result,'quantity','ammo1').raw[0].value,20);assert.equal(ammo1.reads,1);assert.deepEqual(result.reasons,[]);
 for(const [id,status]of [['gone','missing'],['otherType','unsupported'],['hidden','denied']]){const fx=fixture();fx.add('weapon','weapon',{selectedAmmoId:id});if(status==='unsupported')fx.add(id,'equipment');if(status==='denied')fx.add(id,'ammo').item.testUserPermission=()=>false;assert.deepEqual(byId(actorInventoryRecords(fx.target),'inventory_selected_ammunition','weapon').mapped.value,{status,target_uuid:null});}
});
test('serialized attachment IDs and actual Items or kit component IDs never merge',()=>{
 const f=fixture();f.add('weapon','weapon',{subitems:[{_id:'same',name:'Serialized same',type:'weapon',system:{private:'excluded'}}]});const actual=f.add('same','weapon',{quantity:2});const kit=f.add('kit','kit',{items:{same:{pack:'secret',id:'same'}}});f.add('book','book');
 const result=actorInventoryRecords(f.target);assert.equal(rows(result,'inventory_item').length,3);assert.equal(rows(result,'inventory_kit_definition').length,1);assert.equal(rows(result,'inventory_kit_definition')[0].mapped.value.target_uuid,kit.item.uuid);assert.equal(rows(result,'attachment_local_id')[0].raw[0].value,'same');assert.equal(rows(result,'inventory_item').filter(r=>r.mapped.value.target_uuid===actual.item.uuid).length,1);assert.ok(!JSON.stringify(result).includes('secret'));assert.ok(!JSON.stringify(result).includes('private'));assert.deepEqual(result.reasons,['book_interpretation_pending','kit_interpretation_pending']);
});
test('synthetic/linked token context remains explicit, only supported Actor types admitted',()=>{
 for(const type of ['character','npc','familiar']){const f=fixture(type,true);f.add('bag','backpack');f.add('child','equipment',{containerId:'bag'});const result=actorInventoryRecords(f.target);for(const row of rows(result,'inventory_item')){assert.equal(row.mapped.value.token_uuid,f.target.token.uuid);assert.ok(row.mapped.value.target_uuid.startsWith(f.actor.uuid+'.Item.'));}assert.equal(byId(result,'inventory_container','child').mapped.value.token_uuid,f.target.token.uuid);}
 const f=fixture('loot');assert.throws(()=>actorInventoryRecords(f.target),/supported Actor/);
});
test('empty and denied scopes are distinct; absent null empty and zero stay exact',()=>{
 const f=fixture();const nonphysical=f.add('spell','spell');nonphysical.item.toObject=()=>{throw Error('no hydration');};assert.deepEqual(rows(actorInventoryRecords(f.target),'inventory_scope')[0].mapped.value,{status:'empty',target_uuid:null});
 for(const [system,present,value]of [[{},false,undefined],[{containerId:null},true,null],[{containerId:''},true,'']]){const fx=fixture();fx.add('item','equipment',system);const row=byId(actorInventoryRecords(fx.target),'inventory_container','item');assert.equal(row.raw[0].present,present);assert.equal(Object.hasOwn(row.raw[0],'value'),present);assert.equal(row.raw[0].value,value);}
 const denied=f.add('denied','equipment');denied.item.testUserPermission=()=>false;assert.deepEqual(rows(actorInventoryRecords(f.target),'inventory_scope')[0].mapped.value,{status:'denied',target_uuid:null});
});
test('malformed selected source fails closed; arbitrary getters and unrelated objects are not used',()=>{
 const f=fixture(),item=f.add('item','equipment',{containerId:42});assert.throws(()=>actorInventoryRecords(f.target),/containerId/);item.source.system.containerId=null;item.source.system.quantity='2';assert.throws(()=>actorInventoryRecords(f.target),/unexpected type/);
 item.source.system.quantity=2;item.item.toObject=()=>{const source=structuredClone(item.source);for(const key of ['rules','description','flags','contents'])Object.defineProperty(source.system,key,{get(){throw Error('unselected '+key);}});return source;};assert.equal(rows(actorInventoryRecords(f.target),'inventory_item').length,1);
});
test('unidentified alternate description stays in explicit Item prose; input ordering does not change output',()=>{
 const f=fixture();f.add('z','equipment',{identification:{unidentified:{data:{description:{value:'unidentified_prose_sentinel_783f'}}}}});f.add('a','treasure',{quantity:2});const first=actorInventoryRecords(f.target);assert.ok(!JSON.stringify(first).includes('unidentified_prose_sentinel_783f'));assert.equal(rows(first,'unidentified_description').length,0);f.actor.items=new Map([...f.actor.items].reverse());assert.deepEqual(actorInventoryRecords(f.target),first);
});
test('unsupported physical parent cycles preserve diagnostic rather than implying a valid container',()=>{
 const f=fixture();f.add('a','equipment',{containerId:'b'});f.add('b','equipment',{containerId:'a'});const result=actorInventoryRecords(f.target);for(const row of rows(result,'inventory_container'))assert.deepEqual(row.mapped.value,{status:'unsupported',target_uuid:null,cycle:true});assert.deepEqual(result.reasons,['container_parent_unsupported','containment_cycle']);
});
test('inventory labels use cached persisted names rather than prepared physical display names',()=>{
 const f=fixture(),bag=f.add('bag','backpack'),ammo=f.add('ammo','ammo'),weapon=f.add('weapon','weapon',{containerId:'bag',selectedAmmoId:'ammo'}),kit=f.add('kit','kit');
 for(const entry of [bag,ammo,weapon,kit])entry.item.name='Prepared magic '+entry.source.name;
 ammo.source.name='😀'.repeat(257);
 const result=actorInventoryRecords(f.target);
 for(const [entry,concept]of [[bag,'inventory_item'],[weapon,'inventory_item'],[kit,'inventory_kit_definition']]){const row=rows(result,concept).find(row=>row.mapped.value.target_uuid===entry.item.uuid);assert.equal(row.mapped.value.name,entry.source.name);assert.equal(row.mapped.value.name_truncated,false);}
 assert.equal(byId(result,'inventory_container','weapon').mapped.value.name,bag.source.name);
 assert.equal(byId(result,'inventory_selected_ammunition','weapon').mapped.value.name,'😀'.repeat(256));assert.equal(byId(result,'inventory_selected_ammunition','weapon').mapped.value.name_truncated,true);
 assert.deepEqual([bag.reads,ammo.reads,weapon.reads,kit.reads],[1,1,1,1]);
});
