import test from 'node:test';
import assert from 'node:assert/strict';
import {readActor} from '../../foundry-module/scripts/actors.js';

function fixture(){
 const source={type:'character',name:'Caster',system:{resources:{focus:{value:1}}}},current={...source,system:{resources:{focus:{value:1,max:3,cap:3}}}};
 const actor={documentName:'Actor',id:'a',uuid:'Actor.a',name:'Caster',type:'character',items:new Map(),folder:null,compendium:null,testUserPermission:()=>true,toObject:flag=>structuredClone(flag?source:current)};
 const entrySource={name:'Prepared',type:'spellcastingEntry',system:{prepared:{value:'prepared'},slots:{slot1:{value:0,max:2,prepared:[{id:'spell',expended:false},{id:'spell',expended:true}]}}}};
 const spellSource={name:'Spell',type:'spell',system:{level:{value:1},location:{value:'entry',heightenedLevel:4},traits:{value:[]},ritual:null}};
 for(const [id,data] of [['entry',entrySource],['spell',spellSource]])actor.items.set(id,{documentName:'Item',id,uuid:`Actor.a.Item.${id}`,name:data.name,type:data.type,parent:actor,folder:null,compendium:null,testUserPermission:()=>true,toObject:flag=>structuredClone(flag?data:{...data,system:{...data.system,cast:{focusPoints:0}}})});
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map([['a',actor]]),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>uuid===actor.uuid?actor:[...actor.items.values()].find(item=>item.uuid===uuid)}};
 return {actor,entrySource,spellSource};
}

test('actual paginated Actor casting preserves context options separately from source/current rows',async()=>{
 const f=fixture(),rows=[];let cursor,pages=0;
 do{const result=await readActor({actor_uuid:f.actor.uuid,sections:['spellcasting'],limit:3,max_bytes:8000,...(cursor?{cursor}:{})});rows.push(...result.records);cursor=result.pagination.next_cursor;assert.ok(++pages<100);assert.ok(Buffer.byteLength(JSON.stringify(result))<=8000);assert.ok(result.sections[0].reasons.includes('availability_not_evaluated'));}while(cursor);
 const options=rows.filter(row=>row.provenance.mapping==='pf2e.actor.casting-options.v1');assert.equal(options.length,2);assert.deepEqual(options.map(row=>row.mapped.value.expended),[false,true]);assert.ok(options.every(row=>row.mapped.value.base_rank===1&&row.mapped.value.configured_rank===4&&row.mapped.value.slot_rank===1&&row.mapped.value.cast_rank===null));assert.equal(new Set(rows.map(row=>row.key)).size,rows.length);assert.ok(rows.some(row=>row.provenance.mapping==='pf2e.actor.casting-current.v1'));assert.ok(rows.some(row=>row.key==='spellcasting:focus:value'));
});

test('context-source changes stale actual reader continuations and denied entry status survives',async()=>{
 const f=fixture(),params={actor_uuid:f.actor.uuid,sections:['spellcasting'],limit:1},first=await readActor(params);f.spellSource.system.location.heightenedLevel=5;await assert.rejects(readActor({...params,cursor:first.pagination.next_cursor}),error=>error.rpcError.code==='ContentChanged');
 f.actor.items.get('entry').testUserPermission=()=>false;const rows=[];let cursor;do{const result=await readActor({...params,limit:3,...(cursor?{cursor}:{})});rows.push(...result.records);cursor=result.pagination.next_cursor;}while(cursor);
 const options=rows.filter(row=>row.mapped.concept==='casting_contextual_option');assert.equal(options.length,1);assert.deepEqual(options[0].mapped.value.entry,{status:'denied',target_uuid:null});assert.equal(options[0].mapped.value.context,'listed_spell');assert.ok(!options[0].raw.some(raw=>raw.document_uuid==='Actor.a.Item.entry'));
});
