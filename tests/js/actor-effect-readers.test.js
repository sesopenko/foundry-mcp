import test from 'node:test';
import assert from 'node:assert/strict';
import {readItem,getActorTypes} from '../../foundry-module/scripts/actors.js';
function fixture(){
 const source={name:'Tracking effect',type:'effect',system:{level:{value:1},duration:{value:-1,unit:'unlimited',expiry:null,sustained:false},start:{value:0,initiative:null},badge:{type:'formula',value:'1d4+2',evaluate:true,reevaluate:null,labels:null},context:null,fromSpell:true,unidentified:false,description:{value:'<p>Stored effect 😀</p>'}}};
 const item={documentName:'Item',uuid:'Item.e',id:'e',name:source.name,type:'effect',folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},items:new Map([['e',item]]),actors:new Map()};
 globalThis.foundry={utils:{fromUuid:async uuid=>uuid===item.uuid?item:null}};
 return {source,item};
}
test('effect source preserves stored duration and formula through bounded pages without rolling',async()=>{
 const f=fixture(),before=JSON.stringify(f.source);let cursor,rows=[];
 do{const page=await readItem({item_uuid:f.item.uuid,sections:['source','effective'],limit:5,max_bytes:8000,...(cursor?{cursor}:{})});
 assert.equal(page.sections[1].status,'unsupported');rows.push(...page.records);cursor=page.pagination.next_cursor;}while(cursor);
 for(const [path,value]of [['/system/duration/value',-1],['/system/duration/unit','unlimited'],['/system/badge/type','formula'],['/system/badge/value','1d4+2'],['/system/fromSpell',true]]){
  const row=rows.find(r=>r.raw[0].path===path);assert.equal(row.raw[0].value,value);assert.equal(row.provenance.mapping,'pf2e.effect.source.v1');
 }
 assert.equal(JSON.stringify(f.source),before);assert.ok(!rows.some(r=>r.raw[0].path.includes('expired')));
 const desc=await readItem({item_uuid:f.item.uuid,sections:['description']});assert.equal(desc.records[0].raw[0].value,f.source.system.description.value);
});
test('effect continuations reject source changes and invalid badge discriminators remain actionable',async()=>{
 const f=fixture();const first=await readItem({item_uuid:f.item.uuid,sections:['source'],limit:1});
 f.source.system.duration.unit='encounter';
 await assert.rejects(readItem({item_uuid:f.item.uuid,sections:['source'],limit:1,cursor:first.pagination.next_cursor}),e=>e.rpcError.code==='ContentChanged');
 f.source.system.badge.type='private-unknown';
 await assert.rejects(readItem({item_uuid:f.item.uuid,sections:['source']}),e=>e.rpcError.code==='ReadFailed'&&!e.message.includes('private-unknown'));
});
test('effect source respects denied and unsupported-system boundaries without reading source',async()=>{
 const f=fixture();game.system.id='other';
 f.item.toObject=()=>{throw Error('must not read');};
 await assert.rejects(readItem({item_uuid:f.item.uuid}),e=>e.rpcError.code==='UnsupportedSystem');
 game.system.id='pf2e';f.item.testUserPermission=()=>false;
 await assert.rejects(readItem({item_uuid:f.item.uuid}),e=>e.rpcError.code==='PermissionDenied');
});

test('effect discovery reports delivered source mappings and unsupported effective state',async()=>{
 fixture();const entry=(await getActorTypes()).item_types.find(entry=>entry.type==='effect');
 assert.equal(entry.mapped_supported,true);assert.equal(entry.effective_supported,false);assert.equal(entry.verification.live.status,'passed');
 assert.match(entry.limitations.join(' '),/unverified/);
});
