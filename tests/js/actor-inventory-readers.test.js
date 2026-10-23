import test from 'node:test';
import assert from 'node:assert/strict';
import {readActor,getActorTypes} from '../../foundry-module/scripts/actors.js';
function fixture(synthetic=false,type='npc'){
 const source={name:'Owner',type,system:{}};
 const actor={documentName:'Actor',uuid:synthetic?'Scene.s.Token.t.Actor.a':'Actor.a',id:'a',name:source.name,type,folder:null,compendium:null,items:new Map(),testUserPermission:()=>true,toObject:basis=>{assert.equal(basis,true);return structuredClone(source);}};
 const docs=new Map([[actor.uuid,actor]]),sources=new Map();
 const rows=[['bag','backpack',{containerId:null}],['inner','backpack',{containerId:'bag'}],['coins','treasure',{containerId:'inner',quantity:21,price:{value:{gp:1},per:10}}],['bow','weapon',{containerId:null,selectedAmmoId:'ammo',subitems:[{_id:'ammo',name:'Attachment',type:'weapon'}]}],['ammo','ammo',{containerId:'bag',quantity:9}],['other','ammo',{containerId:null,quantity:7}],['kit','kit',{}]];
 for(const [id,itemType,system]of rows){const data={name:'Same name',type:itemType,system};sources.set(id,data);const item={documentName:'Item',uuid:actor.uuid+'.Item.'+id,id,name:data.name,type:itemType,parent:actor,folder:null,compendium:null,testUserPermission:()=>true,toObject:basis=>{assert.equal(basis,true);return structuredClone(data);}};actor.items.set(id,item);docs.set(item.uuid,item);}
 const scene={documentName:'Scene',uuid:'Scene.s',name:'Scene',testUserPermission:()=>true},token={documentName:'Token',uuid:'Scene.s.Token.t',id:'t',name:'Token',parent:scene,actor,baseActor:actor,isLinked:!synthetic,testUserPermission:()=>true};docs.set(token.uuid,token);
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map([['a',actor]]),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>docs.get(uuid)}};return {source,actor,sources,token};
}
async function all(f,token=false){let cursor,rows=[],last;do{last=await readActor({...(token?{token_uuid:f.token.uuid}:{actor_uuid:f.actor.uuid}),sections:['inventory','effective'],limit:7,max_bytes:8000,...(cursor?{cursor}:{})});assert.equal(last.sections[1].status,'unsupported');rows.push(...last.records);cursor=last.pagination.next_cursor;}while(cursor);return {rows,last};}
test('inventory pagination keeps unique possessions and token selectors, nested containers, stock and serialized attachment separate',async()=>{
 for(const synthetic of [false,true]){const f=fixture(synthetic),before=JSON.stringify([...f.sources]),{rows,last}=await all(f,true);
 assert.equal(new Set(rows.map(r=>r.key)).size,rows.length);
 const refs=rows.filter(r=>r.mapped.concept==='inventory_item');assert.equal(refs.length,6);assert.ok(refs.every(r=>r.mapped.value.token_uuid===f.token.uuid));
 const coins=f.actor.items.get('coins').uuid,quantity=rows.find(r=>r.raw[0]?.document_uuid===coins&&r.raw[0].path==='/system/quantity');assert.equal(quantity.raw[0].value,21);
 assert.equal(rows.find(r=>r.raw[0]?.document_uuid===coins&&r.raw[0].path==='/system/price/per').raw[0].value,10);
 assert.equal(rows.find(r=>r.key==='inventory:container:'+coins).mapped.value.target_uuid,f.actor.items.get('inner').uuid);
 assert.equal(rows.find(r=>r.mapped.concept==='inventory_selected_ammunition').mapped.value.target_uuid,f.actor.items.get('ammo').uuid);
 assert.equal(rows.filter(r=>r.raw[0]?.path==='/system/subitems/0/_id').length,1);assert.equal(JSON.stringify([...f.sources]),before);
 assert.ok(!last.sections[0].reasons.includes('section_not_implemented'));
 }
});
test('inventory hides denied Item metadata and cursor invalidates on source, membership and permission changes',async()=>{
 for(const change of ['source','relationship','membership','permission']){const f=fixture(),first=await readActor({actor_uuid:f.actor.uuid,sections:['inventory'],limit:1});
 if(change==='source')f.sources.get('coins').system.quantity=30;
 if(change==='relationship')f.sources.get('coins').system.containerId='bag';
 if(change==='membership')f.actor.items.delete('coins');
 if(change==='permission')f.actor.items.get('coins').testUserPermission=()=>false;
 await assert.rejects(readActor({actor_uuid:f.actor.uuid,sections:['inventory'],limit:1,cursor:first.pagination.next_cursor}),e=>e.rpcError.code==='ContentChanged');}
 const f=fixture();const item=f.actor.items.get('coins');item.testUserPermission=()=>false;item.toObject=()=>{throw Error('denied source');};const {rows,last}=await all(f);assert.ok(!JSON.stringify(rows).includes(item.uuid));assert.ok(last.sections[0].reasons.includes('inventory_items_denied'));
});
test('inventory malformed fields fail closed, other systems reject, and discovery describes source-only support',async()=>{
 const f=fixture();f.sources.get('coins').system.quantity='21';await assert.rejects(readActor({actor_uuid:f.actor.uuid,sections:['inventory']}),e=>e.rpcError.code==='ReadFailed');
 game.system.id='other';await assert.rejects(readActor({actor_uuid:f.actor.uuid,sections:['inventory']}),e=>e.rpcError.code==='UnsupportedSystem');fixture();const row=(await getActorTypes()).actor_sections.find(r=>r.name==='inventory');assert.equal(row.source_supported,true);assert.equal(row.mapped_supported,true);assert.equal(row.effective_supported,false);
});
