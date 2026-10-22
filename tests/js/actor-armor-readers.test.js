import test from 'node:test';
import assert from 'node:assert/strict';
import {readItem,getActorTypes} from '../../foundry-module/scripts/actors.js';
function fixture(){
 const source={name:'Unworn armor',type:'armor',system:{baseItem:'leather',equipped:{carryType:'stowed',inSlot:false,invested:false},category:'light',group:'leather',acBonus:1,strength:0,dexCap:4,checkPenalty:-1,speedPenalty:0,runes:{potency:1,resilient:1,property:[]},specific:null,description:{value:'<p>Exact armor 🙂</p>'}}};
 const item={documentName:'Item',uuid:'Item.armor',id:'armor',name:source.name,type:'armor',folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},items:new Map(),actors:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>uuid===item.uuid?item:null}};return {source,item};
}
test('unworn armor source retains bonuses constraints and carrying state without total AC',async()=>{
 const f=fixture(),before=JSON.stringify(f.source);let cursor,rows=[];
 do{const page=await readItem({item_uuid:f.item.uuid,sections:['source','effective'],limit:7,max_bytes:8000,...(cursor?{cursor}:{})});assert.equal(page.sections[1].status,'unsupported');rows.push(...page.records);cursor=page.pagination.next_cursor;}while(cursor);
 assert.equal(new Set(rows.map(r=>r.raw[0].path)).size,rows.length);
 for(const [path,value]of [['/system/acBonus',1],['/system/strength',0],['/system/dexCap',4],['/system/checkPenalty',-1],['/system/equipped/carryType','stowed'],['/system/equipped/invested',false]])assert.equal(rows.find(r=>r.raw[0].path===path).raw[0].value,value);
 assert.equal(rows.find(r=>r.raw[0].path==='/system/acBonus').provenance.mapping,'pf2e.armor.source.v1');assert.equal(rows.find(r=>r.raw[0].path==='/system/baseItem').provenance.mapping,'pf2e.physical.source.v1');assert.ok(!rows.some(r=>r.raw[0].path==='/system/usage/value'));assert.equal(JSON.stringify(f.source),before);
 assert.equal((await readItem({item_uuid:f.item.uuid,sections:['description']})).records[0].raw[0].value,f.source.system.description.value);
});
test('missing null and zero armor Strength differ and source changes invalidate continuations',async()=>{
 for(const value of [undefined,null,0]){
  const f=fixture();if(value===undefined)delete f.source.system.strength;else f.source.system.strength=value;
  let cursor,row;do{const page=await readItem({item_uuid:f.item.uuid,sections:['source'],limit:100,...(cursor?{cursor}:{})});row??=page.records.find(r=>r.raw[0].path==='/system/strength');cursor=page.pagination.next_cursor;}while(cursor);
  assert.equal(row.raw[0].present,value!==undefined);assert.equal(row.raw[0].value,value);
 }
 const f=fixture();const first=await readItem({item_uuid:f.item.uuid,sections:['source'],limit:1});f.source.system.acBonus=2;
 await assert.rejects(readItem({item_uuid:f.item.uuid,sections:['source'],limit:1,cursor:first.pagination.next_cursor}),e=>e.rpcError.code==='ContentChanged');
 f.source.system.runes.potency={secret:true};await assert.rejects(readItem({item_uuid:f.item.uuid,sections:['source']}),e=>e.rpcError.code==='ReadFailed');
});
test('armor permission and non-PF2e boundaries stop source extraction',async()=>{
 const f=fixture();f.item.toObject=()=>{throw Error('must not read');};game.system.id='other';await assert.rejects(readItem({item_uuid:f.item.uuid}),e=>e.rpcError.code==='UnsupportedSystem');game.system.id='pf2e';f.item.testUserPermission=()=>false;await assert.rejects(readItem({item_uuid:f.item.uuid}),e=>e.rpcError.code==='PermissionDenied');
});
test('armor serialized attachments retain source identity and no implicit child document',async()=>{
 const f=fixture();f.source.system.subitems=[{_id:'attached',name:'Attached adjustment',type:'equipment',system:{secret:'unselected'}}];
 let cursor,rows=[];do{const page=await readItem({item_uuid:f.item.uuid,sections:['source'],limit:100,...(cursor?{cursor}:{})});rows.push(...page.records);cursor=page.pagination.next_cursor;}while(cursor);
 const attached=rows.filter(row=>row.raw[0].path.startsWith('/system/subitems/'));assert.deepEqual(attached.map(row=>row.raw[0].value),['attached','Attached adjustment','equipment']);assert.ok(attached.every(row=>row.raw[0].document_uuid===f.item.uuid));assert.ok(!JSON.stringify(attached).includes('Item.attached'));assert.ok(!JSON.stringify(rows).includes('unselected'));
});

test('armor discovery distinguishes delivered source from unsupported actor defenses',async()=>{
 fixture();const entry=(await getActorTypes()).item_types.find(row=>row.type==='armor');assert.equal(entry.mapped_supported,true);assert.equal(entry.effective_supported,false);assert.equal(entry.verification.live.status,'passed');assert.match(entry.limitations.join(' '),/Actor AC/);
});
