import test from 'node:test';
import assert from 'node:assert/strict';
import {readItem,getActorTypes} from '../../foundry-module/scripts/actors.js';
function fixture(){
 const source={name:'Stored condition',type:'condition',system:{slug:'persistent-damage',value:{isValued:false,value:null},persistent:{formula:'1d6',damageType:'fire',dc:15,criticalHit:false},references:{parent:null,children:[],overrides:[],overriddenBy:[{id:'other',type:'condition'}]},overrides:['dying'],fromSpell:false,description:{value:'<p>Stored condition 🙂</p>'}}};
 const item={documentName:'Item',uuid:'Item.c',id:'c',name:source.name,type:'condition',folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map(),items:new Map([['c',item]])};
 globalThis.foundry={utils:{fromUuid:async uuid=>uuid===item.uuid?item:null}};return {source,item};
}
test('condition source preserves unvalued value, persistent damage and override references through pages',async()=>{
 const f=fixture(),before=JSON.stringify(f.source);let cursor,rows=[];
 do{const page=await readItem({item_uuid:f.item.uuid,sections:['source','effective'],limit:5,max_bytes:8000,...(cursor?{cursor}:{})});assert.equal(page.sections[1].status,'unsupported');rows.push(...page.records);cursor=page.pagination.next_cursor;}while(cursor);
 for(const [path,value]of [['/system/value/isValued',false],['/system/value/value',null],['/system/persistent/formula','1d6'],['/system/persistent/damageType','fire'],['/system/references/overriddenBy/0/id','other'],['/system/overrides/0','dying']]){
  const row=rows.find(r=>r.raw[0].path===path);assert.equal(row.raw[0].value,value);assert.equal(row.provenance.mapping,'pf2e.condition.source.v1');
 }
 assert.ok(!rows.some(r=>/\/active$|\/suppressed$|\/expectedValue$/.test(r.raw[0].path)));assert.equal(JSON.stringify(f.source),before);
 assert.equal((await readItem({item_uuid:f.item.uuid,sections:['description']})).records[0].raw[0].value,f.source.system.description.value);
});
test('condition continuation changes and malformed selected data fail without prepared fallback',async()=>{
 const f=fixture();const first=await readItem({item_uuid:f.item.uuid,sections:['source'],limit:1});
 f.source.system.persistent.damageType='cold';
 await assert.rejects(readItem({item_uuid:f.item.uuid,sections:['source'],limit:1,cursor:first.pagination.next_cursor}),e=>e.rpcError.code==='ContentChanged');
 f.source.system.value.value={secret:'hidden'};
 await assert.rejects(readItem({item_uuid:f.item.uuid,sections:['source']}),e=>e.rpcError.code==='ReadFailed'&&!e.message.includes('hidden'));
});
test('condition reading rejects non-PF2e and denied sources before extraction',async()=>{
 const f=fixture();f.item.toObject=()=>{throw Error('must not read');};game.system.id='other';
 await assert.rejects(readItem({item_uuid:f.item.uuid}),e=>e.rpcError.code==='UnsupportedSystem');
 game.system.id='pf2e';f.item.testUserPermission=()=>false;
 await assert.rejects(readItem({item_uuid:f.item.uuid}),e=>e.rpcError.code==='PermissionDenied');
});

test('condition discovery distinguishes delivered persisted source from unsupported state',async()=>{
 fixture();const entry=(await getActorTypes()).item_types.find(row=>row.type==='condition');
 assert.equal(entry.mapped_supported,true);assert.equal(entry.effective_supported,false);assert.equal(entry.verification.live.status,'passed');assert.match(entry.limitations.join(' '),/suppression/);
});
