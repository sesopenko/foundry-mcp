import test from 'node:test';
import assert from 'node:assert/strict';
import {readItem,getActorTypes} from '../../foundry-module/scripts/actors.js';
function fixture(){
 const source={name:'Healing supply',type:'consumable',system:{category:'potion',quantity:4,usage:{value:'held-in-one-hand'},uses:{value:0,max:2,autoDestroy:false},damage:{formula:'2d8+5',type:'vitality',kind:'healing'},spell:null,traits:{value:['magical'],otherTags:[],rarity:'common'},description:{value:'<p>Exact activation 🙂</p>'}}};
 const item={documentName:'Item',uuid:'Item.c',id:'c',name:source.name,type:'consumable',folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map(),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>uuid===item.uuid?item:null}};return {source,item};
}
async function sourceRows(f){let cursor,rows=[];do{const page=await readItem({item_uuid:f.item.uuid,sections:['source','effective'],limit:6,max_bytes:8000,...(cursor?{cursor}:{})});assert.equal(page.sections[0].status,page.pagination.complete?'complete':'partial');assert.equal(page.sections[1].status,'unsupported');rows.push(...page.records);cursor=page.pagination.next_cursor;}while(cursor);return rows;}
test('healing source keeps stock and uses separate without consuming or rolling',async()=>{
 const f=fixture(),before=JSON.stringify(f.source),rows=await sourceRows(f);
 assert.equal(new Set(rows.map(r=>r.raw[0].path)).size,rows.length);
 for(const [path,value]of [['quantity',4],['uses/value',0],['uses/max',2],['uses/autoDestroy',false],['damage/formula','2d8+5'],['damage/kind','healing'],['spell',null]])assert.equal(rows.find(r=>r.raw[0].path==='/system/'+path).raw[0].value,value);
 assert.equal(rows.find(r=>r.raw[0].path==='/system/damage/kind').provenance.mapping,'pf2e.consumable.source.v1');assert.equal(rows.find(r=>r.raw[0].path==='/system/quantity').provenance.mapping,'pf2e.physical.source.v1');assert.equal(JSON.stringify(f.source),before);
 assert.equal((await readItem({item_uuid:f.item.uuid,sections:['description']})).records[0].raw[0].value,f.source.system.description.value);
});
test('contained spell metadata keeps source identity and does not become an embedded Item selector',async()=>{
 const f=fixture();f.source.system.damage={formula:'1d6',type:'fire',kind:'damage'};f.source.system.spell={_id:'nested',name:'Contained spell',type:'spell',system:{level:{value:3},rules:[{secret:'not selected'}]}};
 const rows=await sourceRows(f);assert.equal(rows.find(r=>r.raw[0].path==='/system/damage/kind').raw[0].value,'damage');assert.equal(rows.find(r=>r.raw[0].path==='/system/spell/name').raw[0].value,'Contained spell');assert.equal(rows.find(r=>r.raw[0].path==='/system/spell/system/level/value').raw[0].value,3);
 assert.ok(rows.every(r=>r.raw[0].document_uuid===f.item.uuid));assert.ok(!JSON.stringify(rows).includes('not selected'));assert.ok(rows.every(r=>r.kind!=='relationship'));
});
test('consumable malformed source stale continuations permissions and system boundaries remain actionable',async()=>{
 const f=fixture();const first=await readItem({item_uuid:f.item.uuid,sections:['source'],limit:1});f.source.system.uses.value=1;
 await assert.rejects(readItem({item_uuid:f.item.uuid,sections:['source'],limit:1,cursor:first.pagination.next_cursor}),e=>e.rpcError.code==='ContentChanged');
 f.source.system.damage.formula={secret:true};await assert.rejects(readItem({item_uuid:f.item.uuid,sections:['source']}),e=>e.rpcError.code==='ReadFailed');
 game.system.id='other';await assert.rejects(readItem({item_uuid:f.item.uuid}),e=>e.rpcError.code==='UnsupportedSystem');game.system.id='pf2e';f.item.testUserPermission=()=>false;await assert.rejects(readItem({item_uuid:f.item.uuid}),e=>e.rpcError.code==='PermissionDenied');
});
test('consumable discovery advertises contained definitions and no castability',async()=>{
 fixture();const entry=(await getActorTypes()).item_types.find(row=>row.type==='consumable');assert.equal(entry.mapped_supported,true);assert.equal(entry.effective_supported,false);assert.match(entry.limitations.join(' '),/contained spell definitions/);
});

test('contained definitions and continued prose retain consumable provenance without applying variants',async()=>{
 const f=fixture();const prose='<p>'+ 'Contained 🙂 spell '.repeat(900)+'</p>';
 f.source.system.spell={_id:'nested',name:'Contained',type:'spell',system:{level:{value:4},time:{value:'1 minute'},location:{value:'claimed-entry',heightenedLevel:7},damage:{component:{formula:'1d6',type:'fire',kinds:['damage'],category:null,materials:[]}},description:{value:prose},overlays:{variant:{overlayType:'override',sort:1,system:{damage:{component:{formula:'2d6'}},description:{value:'Variant prose'}}}}}};
 const before=JSON.stringify(f.source),rows=await sourceRows(f);
 assert.equal(rows.find(r=>r.raw[0].path==='/system/spell/system/location/heightenedLevel').raw[0].value,7);
 const base=rows.find(r=>r.raw[0].path==='/system/spell/system/level/value');assert.equal(base.raw[0].value,4);assert.equal(base.provenance.mapping,'pf2e.consumable.source.v1');
 const time=rows.find(r=>r.raw[0].path==='/system/spell/system/time/value');assert.equal(time.raw[0].value,'1 minute');assert.equal(time.provenance.mapping,'pf2e.spell.source.v1');assert.ok(rows.every(r=>r.raw[0].document_uuid===f.item.uuid));
 let cursor,text='',variant='',pages=0;do{const page=await readItem({item_uuid:f.item.uuid,sections:['description'],limit:1,max_bytes:8000,...(cursor?{cursor}:{})});for(const row of page.records){assert.equal(row.raw[0].document_uuid,f.item.uuid);if(row.raw[0].path==='/system/spell/system/description/value'){assert.equal(row.text.start,text.length);text+=row.raw[0].value;}if(row.raw[0].path.endsWith('/overlays/variant/system/description/value'))variant+=row.raw[0].value;}pages++;cursor=page.pagination.next_cursor;}while(cursor);
 assert.ok(pages>3);assert.equal(text,prose);assert.equal(variant,'Variant prose');assert.equal(JSON.stringify(f.source),before);
 const relation=await readItem({item_uuid:f.item.uuid,sections:['relationships']});assert.equal(relation.sections[0].status,'unsupported');assert.equal(relation.records.length,0);
 const first=await readItem({item_uuid:f.item.uuid,sections:['source'],limit:1});f.source.system.spell.system.damage.component.formula='3d6';await assert.rejects(readItem({item_uuid:f.item.uuid,sections:['source'],limit:1,cursor:first.pagination.next_cursor}),e=>e.rpcError.code==='ContentChanged');
});
