import test from 'node:test';
import assert from 'node:assert/strict';
import {readItem,getActorTypes} from '../../foundry-module/scripts/actors.js';
function fixture(){
 const source={name:'Ammunition',type:'ammo',system:{baseItem:null,quantity:0,uses:{value:0,max:10,autoDestroy:false},craftableAs:[],traits:{value:['magical'],otherTags:[],rarity:'uncommon'},description:{value:'<p>Exact special ammunition 🙂</p>'},rules:[{secret:'not automatically applied'}]}};
 const item={documentName:'Item',uuid:'Item.a',id:'a',name:source.name,type:'ammo',folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map(),items:new Map([['a',item]])};globalThis.foundry={utils:{fromUuid:async uuid=>uuid===item.uuid?item:null}};return {source,item};
}
test('ammunition stock and uses stay separate with unique source paths and no effective attack',async()=>{
 const f=fixture(),before=JSON.stringify(f.source);let cursor,rows=[];
 do{const page=await readItem({item_uuid:f.item.uuid,sections:['source','effective','rules'],limit:6,max_bytes:8000,...(cursor?{cursor}:{})});assert.ok(page.sections.slice(1).every(s=>s.status==='unsupported'));rows.push(...page.records);cursor=page.pagination.next_cursor;}while(cursor);
 assert.equal(new Set(rows.map(r=>r.raw[0].path)).size,rows.length);
 for(const [path,value]of [['/system/quantity',0],['/system/baseItem',null],['/system/uses/value',0],['/system/uses/max',10],['/system/uses/autoDestroy',false]])assert.equal(rows.find(r=>r.raw[0].path===path).raw[0].value,value);
 assert.deepEqual(rows.find(r=>r.raw[0].path==='/system/craftableAs').raw[0].value,[]);
 assert.equal(rows.find(r=>r.raw[0].path==='/system/uses/value').provenance.mapping,'pf2e.ammo.source.v1');assert.equal(JSON.stringify(f.source),before);assert.ok(!JSON.stringify(rows).includes('not automatically applied'));
 assert.equal((await readItem({item_uuid:f.item.uuid,sections:['description']})).records[0].raw[0].value,f.source.system.description.value);
});
test('ammunition malformed source stale continuations and runtime permissions remain actionable',async()=>{
 const f=fixture();const first=await readItem({item_uuid:f.item.uuid,sections:['source'],limit:1});f.source.system.uses.value=2;
 await assert.rejects(readItem({item_uuid:f.item.uuid,sections:['source'],limit:1,cursor:first.pagination.next_cursor}),e=>e.rpcError.code==='ContentChanged');
 f.source.system.craftableAs={secret:true};await assert.rejects(readItem({item_uuid:f.item.uuid,sections:['source']}),e=>e.rpcError.code==='ReadFailed');
 game.system.id='other';await assert.rejects(readItem({item_uuid:f.item.uuid}),e=>e.rpcError.code==='UnsupportedSystem');game.system.id='pf2e';f.item.testUserPermission=()=>false;
 await assert.rejects(readItem({item_uuid:f.item.uuid}),e=>e.rpcError.code==='PermissionDenied');
});
test('two carried ammo stacks do not both contribute to an explicit weapon selection',async()=>{
 const f=fixture();const owner={documentName:'Actor',uuid:'Actor.owner',id:'owner',name:'Owner',type:'npc',items:new Map(),folder:null,compendium:null,testUserPermission:()=>true};
 f.item.parent=owner;f.item.uuid=owner.uuid+'.Item.a';owner.items.set('a',f.item);
 const other={...f.item,id:'other',uuid:owner.uuid+'.Item.other',toObject(){throw Error('unselected stack source must not be read');}};owner.items.set(other.id,other);
 const weapon={...f.item,id:'weapon',uuid:owner.uuid+'.Item.weapon',type:'weapon',toObject:()=>({name:'Weapon',type:'weapon',system:{selectedAmmoId:'a'}})};owner.items.set(weapon.id,weapon);
 const docs=new Map([...owner.items.values()].map(item=>[item.uuid,item]));docs.set(owner.uuid,owner);foundry.utils.fromUuid=async uuid=>docs.get(uuid);
 const link=(await readItem({item_uuid:weapon.uuid,sections:['relationships']})).records[0].mapped.value;assert.equal(link.target_uuid,f.item.uuid);
 const selected=await readItem({item_uuid:link.target_uuid,sections:['identity']});assert.equal(selected.identity.uuid,f.item.uuid);
 owner.items.delete('a');assert.equal((await readItem({item_uuid:weapon.uuid,sections:['relationships']})).records[0].mapped.value.status,'missing');
});

test('ammo discovery separates delivered source from unsupported compatibility and effects',async()=>{
 fixture();const entry=(await getActorTypes()).item_types.find(row=>row.type==='ammo');assert.equal(entry.mapped_supported,true);assert.equal(entry.effective_supported,false);assert.equal(entry.verification.live.status,'passed');assert.match(entry.limitations.join(' '),/compatibility/);
});
