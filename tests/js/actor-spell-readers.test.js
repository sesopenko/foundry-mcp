import test from 'node:test';
import assert from 'node:assert/strict';
import {readItem,getActorTypes} from '../../foundry-module/scripts/actors.js';
function fixture(){
 const source={name:'Spell definition',type:'spell',system:{level:{value:3},time:{value:'1 minute or 3 actions'},traits:{value:['cantrip'],traditions:['arcane'],rarity:'common'},damage:{first:{formula:'3d8',type:'vitality',kinds:['healing','damage'],category:null,materials:[]}},location:{value:null,heightenedLevel:7},heightening:{type:'interval',interval:1,area:0,damage:{first:'1d8'}},description:{value:'<p>Exact spell '+ '🙂 detail '.repeat(1400)+'</p>'}}};
 const item={documentName:'Item',uuid:'Item.s',id:'s',name:source.name,type:'spell',folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map(),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>uuid===item.uuid?item:null}};return {source,item};
}
test('spell source preserves base rank variable casting text damage kinds and heightening config without casting',async()=>{
 const f=fixture(),before=JSON.stringify(f.source);let cursor,rows=[];
 do{const page=await readItem({item_uuid:f.item.uuid,sections:['source','effective'],limit:7,max_bytes:8000,...(cursor?{cursor}:{})});assert.equal(page.sections[1].status,'unsupported');rows.push(...page.records);cursor=page.pagination.next_cursor;if(!cursor)assert.equal(page.sections[0].status,'complete');}while(cursor);
 for(const [path,value]of [['level/value',3],['time/value','1 minute or 3 actions'],['location/heightenedLevel',7],['damage/first/kinds/0','healing'],['damage/first/kinds/1','damage'],['heightening/damage/first','1d8']])assert.equal(rows.find(r=>r.raw[0].path==='/system/'+path).raw[0].value,value);
 assert.equal(new Set(rows.map(r=>r.raw[0].path)).size,rows.length);assert.equal(JSON.stringify(f.source),before);
 let text='',pages=0;cursor=null;do{const page=await readItem({item_uuid:f.item.uuid,sections:['description'],limit:1,max_bytes:8000,...(cursor?{cursor}:{})});for(const row of page.records.filter(row=>row.raw[0].path==='/system/description/value')){assert.equal(row.text.start,text.length);text+=row.raw[0].value;}pages++;cursor=page.pagination.next_cursor;}while(cursor);assert.ok(pages>1);assert.equal(text,f.source.system.description.value);
});
test('spell description retains fixed and overlay prose separately without merging variants',async()=>{
 const f=fixture();f.source.system.description.value='Base';f.source.system.heightening={type:'fixed',levels:{5:{description:{value:'Higher source'}}}};f.source.system.overlays={variant:{overlayType:'override',sort:1,name:'Alternative',system:{description:{value:'Variant source'}}}};
 const page=await readItem({item_uuid:f.item.uuid,sections:['description'],limit:100});const values=page.records.map(row=>row.raw[0].value);assert.deepEqual(values,['Base','Higher source','Variant source']);
});
test('spell source malformed stale denied and non-PF2e boundaries stay explicit',async()=>{
 const f=fixture();const first=await readItem({item_uuid:f.item.uuid,sections:['source'],limit:1});f.source.system.location.heightenedLevel=8;await assert.rejects(readItem({item_uuid:f.item.uuid,sections:['source'],limit:1,cursor:first.pagination.next_cursor}),e=>e.rpcError.code==='ContentChanged');
 f.source.system.time.value={secret:true};await assert.rejects(readItem({item_uuid:f.item.uuid,sections:['source']}),e=>e.rpcError.code==='ReadFailed');game.system.id='other';await assert.rejects(readItem({item_uuid:f.item.uuid}),e=>e.rpcError.code==='UnsupportedSystem');game.system.id='pf2e';f.item.testUserPermission=()=>false;await assert.rejects(readItem({item_uuid:f.item.uuid}),e=>e.rpcError.code==='PermissionDenied');
});
test('spell discovery separates definition source from computed casting',async()=>{
 fixture();const entry=(await getActorTypes()).item_types.find(row=>row.type==='spell');assert.equal(entry.mapped_supported,true);assert.equal(entry.effective_supported,false);assert.match(entry.limitations.join(' '),/No evaluated variants/);
});
