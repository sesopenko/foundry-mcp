import test from 'node:test';
import assert from 'node:assert/strict';
import {readItem,getActorTypes} from '../../foundry-module/scripts/actors.js';
function fixture(){
 const source={name:'Held shield',type:'shield',system:{baseItem:'steel-shield',equipped:{carryType:'held',handsHeld:1},acBonus:2,speedPenalty:0,hp:{value:0,max:20},hardness:5,runes:{reinforcing:1},specific:null,traits:{value:[],otherTags:[],rarity:'common',integrated:null},publication:{title:'GM Core',authors:'Author',license:'ORC',remaster:true},description:{value:'<p>Exact shield 🙂</p>'}}};
 const item={documentName:'Item',uuid:'Item.s',id:'s',name:source.name,type:'shield',folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map(),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>uuid===item.uuid?item:null}};return {source,item};
}
test('held shield source keeps defenses durability runes and provenance without effective raised/block state',async()=>{
 const f=fixture(),before=JSON.stringify(f.source);let cursor,rows=[];
 do{const page=await readItem({item_uuid:f.item.uuid,sections:['source','effective'],limit:7,max_bytes:8000,...(cursor?{cursor}:{})});assert.equal(page.sections[1].status,'unsupported');rows.push(...page.records);cursor=page.pagination.next_cursor;}while(cursor);
 assert.equal(new Set(rows.map(r=>r.raw[0].path)).size,rows.length);
 for(const [path,value]of [['/system/acBonus',2],['/system/hp/value',0],['/system/hardness',5],['/system/equipped/carryType','held'],['/system/runes/reinforcing',1],['/system/publication/title','GM Core']])assert.equal(rows.find(r=>r.raw[0].path===path).raw[0].value,value);
 assert.equal(rows.find(r=>r.raw[0].path==='/system/runes/reinforcing').provenance.mapping,'pf2e.shield.source.v1');assert.equal(rows.find(r=>r.raw[0].path==='/system/hp/value').provenance.mapping,'pf2e.physical.source.v1');assert.ok(!rows.some(r=>/raised|broken|ShieldBlock|\/usage\//.test(r.raw[0].path)));assert.equal(JSON.stringify(f.source),before);
 assert.equal((await readItem({item_uuid:f.item.uuid,sections:['description']})).records[0].raw[0].value,f.source.system.description.value);
});
test('shield source changes malformed fields and runtime permissions remain actionable',async()=>{
 const f=fixture();const first=await readItem({item_uuid:f.item.uuid,sections:['source'],limit:1});f.source.system.hp.value=1;
 await assert.rejects(readItem({item_uuid:f.item.uuid,sections:['source'],limit:1,cursor:first.pagination.next_cursor}),e=>e.rpcError.code==='ContentChanged');
 f.source.system.traits.integrated=[];await assert.rejects(readItem({item_uuid:f.item.uuid,sections:['source']}),e=>e.rpcError.code==='ReadFailed');
 game.system.id='other';await assert.rejects(readItem({item_uuid:f.item.uuid}),e=>e.rpcError.code==='UnsupportedSystem');game.system.id='pf2e';f.item.testUserPermission=()=>false;await assert.rejects(readItem({item_uuid:f.item.uuid}),e=>e.rpcError.code==='PermissionDenied');
});
test('reinforced source HP above source maximum is retained without clamping or broken-state inference',async()=>{
 const f=fixture();f.source.system.hp={value:56,max:12};f.source.system.hardness=3;
 let cursor,rows=[];do{const page=await readItem({item_uuid:f.item.uuid,sections:['source'],limit:100,...(cursor?{cursor}:{})});rows.push(...page.records);cursor=page.pagination.next_cursor;}while(cursor);
 assert.equal(rows.find(r=>r.raw[0].path==='/system/hp/value').raw[0].value,56);assert.equal(rows.find(r=>r.raw[0].path==='/system/hp/max').raw[0].value,12);assert.equal(rows.find(r=>r.raw[0].path==='/system/hardness').raw[0].value,3);assert.ok(!rows.some(r=>/broken|threshold|effective/i.test(r.raw[0].path)));
});

test('shield discovery keeps effective state unsupported and live scope explicit',async()=>{
 fixture();const entry=(await getActorTypes()).item_types.find(row=>row.type==='shield');assert.equal(entry.mapped_supported,true);assert.equal(entry.effective_supported,false);assert.equal(entry.verification.live.status,'passed');assert.match(entry.limitations.join(' '),/compendium sources only/);
});
