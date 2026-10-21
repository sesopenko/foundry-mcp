import test from 'node:test';
import assert from 'node:assert/strict';
import {readItem,getActorTypes} from '../../foundry-module/scripts/actors.js';
function fixture(){
 const source={name:'Carried weapon',type:'weapon',system:{quantity:1,baseItem:'longsword',equipped:{carryType:'stowed',handsHeld:0},category:'martial',group:'sword',damage:{dice:1,die:'d8',damageType:'slashing',modifier:0,persistent:null},range:null,reload:{value:null},ammo:null,selectedAmmoId:null,runes:{potency:0,striking:0,property:[]},description:{value:'<p>Exact weapon 🙂</p>'}}};
 const item={documentName:'Item',uuid:'Item.w',id:'w',name:source.name,type:'weapon',folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},items:new Map([['w',item]]),actors:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>uuid===item.uuid?item:null}};return {source,item};
}
test('weapon definition and common physical source paginate with unique paths and no effective Strike',async()=>{
 const f=fixture(),before=JSON.stringify(f.source);let cursor,rows=[];
 do{const page=await readItem({item_uuid:f.item.uuid,sections:['source','effective'],limit:8,max_bytes:8000,...(cursor?{cursor}:{})});assert.equal(page.sections[1].status,'unsupported');rows.push(...page.records);cursor=page.pagination.next_cursor;}while(cursor);
 assert.equal(new Set(rows.map(r=>r.raw[0].path)).size,rows.length);
 for(const [path,value]of [['/system/equipped/carryType','stowed'],['/system/equipped/handsHeld',0],['/system/baseItem','longsword'],['/system/damage/die','d8'],['/system/runes/potency',0],['/system/range',null]])assert.equal(rows.find(r=>r.raw[0].path===path).raw[0].value,value);
 assert.equal(rows.find(r=>r.raw[0].path==='/system/damage/die').provenance.mapping,'pf2e.weapon.source.v1');
 assert.equal(rows.find(r=>r.raw[0].path==='/system/baseItem').provenance.mapping,'pf2e.physical.source.v1');assert.equal(JSON.stringify(f.source),before);
 assert.equal((await readItem({item_uuid:f.item.uuid,sections:['description']})).records[0].raw[0].value,f.source.system.description.value);
});
test('weapon source changes and malformed fields fail without prepared defaults',async()=>{
 const f=fixture();const first=await readItem({item_uuid:f.item.uuid,sections:['source'],limit:1});f.source.system.damage.dice=2;
 await assert.rejects(readItem({item_uuid:f.item.uuid,sections:['source'],limit:1,cursor:first.pagination.next_cursor}),e=>e.rpcError.code==='ContentChanged');
 f.source.system.damage.damageType={secret:true};await assert.rejects(readItem({item_uuid:f.item.uuid,sections:['source']}),e=>e.rpcError.code==='ReadFailed');
});
test('weapon denied and non-PF2e sources are rejected before extraction',async()=>{
 const f=fixture();f.item.toObject=()=>{throw Error('must not read');};game.system.id='other';
 await assert.rejects(readItem({item_uuid:f.item.uuid}),e=>e.rpcError.code==='UnsupportedSystem');game.system.id='pf2e';f.item.testUserPermission=()=>false;
 await assert.rejects(readItem({item_uuid:f.item.uuid}),e=>e.rpcError.code==='PermissionDenied');
});
test('weapon nested attachments retain source-path identity without fabricated document UUIDs',async()=>{
 const f=fixture();f.source.system.subitems=[{_id:'attachment',name:'Attached blade',type:'weapon',system:{damage:{secret:'unselected'}},flags:{secret:'unselected'}}];
 const rows=[];let cursor;do{const page=await readItem({item_uuid:f.item.uuid,sections:['source'],limit:100,...(cursor?{cursor}:{})});rows.push(...page.records);cursor=page.pagination.next_cursor;}while(cursor);
 const attached=rows.filter(r=>r.raw[0].path.startsWith('/system/subitems/'));
 assert.deepEqual(attached.map(r=>r.raw[0].value),['attachment','Attached blade','weapon']);assert.ok(attached.every(r=>r.raw[0].document_uuid===f.item.uuid));
 assert.ok(!JSON.stringify(rows).includes('unselected'));assert.ok(!JSON.stringify(attached).includes('Item.attachment'));
});

test('weapon discovery reports source support separately from effective attacks',async()=>{
 fixture();const entry=(await getActorTypes()).item_types.find(row=>row.type==='weapon');assert.equal(entry.mapped_supported,true);assert.equal(entry.effective_supported,false);assert.equal(entry.verification.live.status,'passed');assert.match(entry.limitations.join(' '),/usability/);
});
