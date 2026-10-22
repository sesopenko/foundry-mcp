import test from 'node:test';
import assert from 'node:assert/strict';
import {readItem,getActorTypes} from '../../foundry-module/scripts/actors.js';
function fixture(){
 const source={name:'Useful gear',type:'equipment',system:{usage:{value:'worncloak'},equipped:{carryType:'worn',invested:false},traits:{value:['invested','magical'],otherTags:[],rarity:'common'},subitems:[{_id:'attachment',name:'Stored attachment',type:'equipment',system:{secret:'not selected'}}],description:{value:'<p>Mundane shelter. Activate [reaction]; Frequency once per day. '+ '🙂 detail '.repeat(1400)+'</p>'},rules:[{secret:'not automatically applied'}]}};
 const item={documentName:'Item',uuid:'Item.e',id:'e',name:source.name,type:'equipment',folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map(),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>uuid===item.uuid?item:null}};return {source,item};
}
test('uninvested equipment preserves mundane source and exact continued prose abilities without applying benefits',async()=>{
 const f=fixture(),before=JSON.stringify(f.source);let cursor,rows=[];
 do{const page=await readItem({item_uuid:f.item.uuid,sections:['source','effective','rules'],limit:7,max_bytes:8000,...(cursor?{cursor}:{})});assert.ok(page.sections.slice(1).every(s=>s.status==='unsupported'));rows.push(...page.records);cursor=page.pagination.next_cursor;if(!cursor)assert.equal(page.sections[0].status,'complete');}while(cursor);
 assert.equal(new Set(rows.map(r=>r.raw[0].path)).size,rows.length);
 for(const [path,value]of [['/system/usage/value','worncloak'],['/system/equipped/invested',false],['/system/traits/value/0','invested'],['/system/subitems/0/name','Stored attachment']])assert.equal(rows.find(r=>r.raw[0].path===path).raw[0].value,value);
 assert.equal(rows.find(r=>r.raw[0].path==='/system/traits/value/0').provenance.mapping,'pf2e.equipment.source.v1');assert.equal(rows.find(r=>r.raw[0].path==='/system/equipped/invested').provenance.mapping,'pf2e.physical.source.v1');assert.ok(!JSON.stringify(rows).includes('not selected'));assert.ok(!rows.some(r=>/activation|frequency|benefit/.test(r.raw[0].path)));
 let text='',pages=0;cursor=null;
 do{const page=await readItem({item_uuid:f.item.uuid,sections:['description'],limit:1,max_bytes:8000,...(cursor?{cursor}:{})});for(const row of page.records.filter(row=>row.raw[0].path==='/system/description/value')){assert.equal(row.text.start,text.length);text+=row.raw[0].value;}pages++;cursor=page.pagination.next_cursor;}while(cursor);
 assert.ok(pages>1);assert.equal(text,f.source.system.description.value);assert.equal(JSON.stringify(f.source),before);
});
test('equipment malformed source stale continuations and runtime permissions stay actionable',async()=>{
 const f=fixture();const first=await readItem({item_uuid:f.item.uuid,sections:['source'],limit:1});f.source.system.equipped.invested=true;
 await assert.rejects(readItem({item_uuid:f.item.uuid,sections:['source'],limit:1,cursor:first.pagination.next_cursor}),e=>e.rpcError.code==='ContentChanged');
 f.source.system.traits.value={secret:true};await assert.rejects(readItem({item_uuid:f.item.uuid,sections:['source']}),e=>e.rpcError.code==='ReadFailed');
 game.system.id='other';await assert.rejects(readItem({item_uuid:f.item.uuid}),e=>e.rpcError.code==='UnsupportedSystem');game.system.id='pf2e';f.item.testUserPermission=()=>false;await assert.rejects(readItem({item_uuid:f.item.uuid}),e=>e.rpcError.code==='PermissionDenied');
});
test('equipment discovery distinguishes source support from unsupported effective benefits',async()=>{
 fixture();const entry=(await getActorTypes()).item_types.find(row=>row.type==='equipment');assert.equal(entry.mapped_supported,true);assert.equal(entry.effective_supported,false);assert.equal(entry.verification.live.status,'passed');assert.match(entry.limitations.join(' '),/description.*prose/);
});
