import test from 'node:test';
import assert from 'node:assert/strict';
import {readItem,getActorTypes} from '../../foundry-module/scripts/actors.js';
function fixture(mode='prepared'){
 const source={name:'Casting group',type:'spellcastingEntry',system:{tradition:{value:'arcane'},prepared:{value:mode,flexible:false},ability:{value:'int'},proficiency:{value:2},spelldc:{value:14,dc:24},autoHeightenLevel:{value:null},slots:{slot4:{value:0,max:2,prepared:[{id:'spell',expended:false},{id:'spell',expended:true},{id:null} ]},slot11:{value:0,max:0,prepared:[]}},description:{value:'<p>Exact caster exceptions 🙂</p>'}}};
 const item={documentName:'Item',uuid:'Item.c',id:'c',name:source.name,type:'spellcastingEntry',folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map(),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>uuid===item.uuid?item:null}};return {source,item};
}
async function rows(f){let cursor,records=[],last;do{last=await readItem({item_uuid:f.item.uuid,sections:['source','effective','relationships'],limit:9,max_bytes:8000,...(cursor?{cursor}:{})});assert.ok(last.sections.slice(1).every(row=>row.status==='unsupported'));records.push(...last.records);cursor=last.pagination.next_cursor;}while(cursor);return {records,last};}
test('prepared source zero slots and repeated preparations do not imply exhaustion or a computed cast resource',async()=>{
 const f=fixture(),before=JSON.stringify(f.source),{records,last}=await rows(f);assert.equal(last.sections[0].status,'complete');
 for(const [path,value]of [['prepared/value','prepared'],['slots/slot4/value',0],['slots/slot4/prepared/0/id','spell'],['slots/slot4/prepared/1/id','spell'],['slots/slot4/prepared/0/expended',false],['slots/slot4/prepared/1/expended',true],['slots/slot11/value',0]])assert.equal(records.find(r=>r.raw[0].path==='/system/'+path).raw[0].value,value);
 assert.equal(records.find(r=>r.raw[0].path==='/system/slots/slot4/prepared/2/expended').raw[0].present,false);assert.equal(new Set(records.map(r=>r.raw[0].path)).size,records.length);assert.equal(JSON.stringify(f.source),before);assert.ok(!records.some(r=>/exhausted|castable|rank11|focus_pool/.test(r.raw[0].path)));
 assert.equal((await readItem({item_uuid:f.item.uuid,sections:['description']})).records[0].raw[0].value,f.source.system.description.value);
});
test('casting modes preserve exact codes without flattening resources',async()=>{
 for(const mode of ['focus','innate','spontaneous','items','future-mode']){const f=fixture(mode),{records}=await rows(f);assert.equal(records.find(r=>r.raw[0].path==='/system/prepared/value').raw[0].value,mode);assert.ok(!records.some(r=>r.kind==='relationship'));}
});
test('legacy preparations remain partial with explicit source paths and no raw coercion',async()=>{
 const f=fixture();f.source.system.slots.slot4.prepared={0:{id:'spell',expended:false}};const {records,last}=await rows(f);assert.equal(last.sections[0].status,'partial');assert.ok(last.sections[0].reasons.length);assert.ok(last.limitations.some(s=>s.includes('/system/slots/slot4/prepared')));assert.ok(!records.some(r=>r.raw[0].path.startsWith('/system/slots/slot4/prepared')));assert.equal(records.find(r=>r.raw[0].path==='/system/slots/slot4/value').raw[0].value,0);
});
test('casting entry stale malformed scalar permissions and system boundaries remain actionable',async()=>{
 const f=fixture(),first=await readItem({item_uuid:f.item.uuid,sections:['source'],limit:1});f.source.system.slots.slot4.prepared[0].expended=true;await assert.rejects(readItem({item_uuid:f.item.uuid,sections:['source'],limit:1,cursor:first.pagination.next_cursor}),e=>e.rpcError.code==='ContentChanged');
 f.source.system.spelldc.value={secret:true};await assert.rejects(readItem({item_uuid:f.item.uuid,sections:['source']}),e=>e.rpcError.code==='ReadFailed');game.system.id='other';await assert.rejects(readItem({item_uuid:f.item.uuid}),e=>e.rpcError.code==='UnsupportedSystem');game.system.id='pf2e';f.item.testUserPermission=()=>false;await assert.rejects(readItem({item_uuid:f.item.uuid}),e=>e.rpcError.code==='PermissionDenied');
});
test('entry discovery separates selected source from effective resources and actor casting joins',async()=>{
 fixture();const entry=(await getActorTypes()).item_types.find(r=>r.type==='spellcastingEntry');assert.equal(entry.mapped_supported,true);assert.equal(entry.effective_supported,false);assert.equal(entry.verification.live.status,'passed');assert.match(entry.limitations.join(' '),/CORE-casting/);
});
