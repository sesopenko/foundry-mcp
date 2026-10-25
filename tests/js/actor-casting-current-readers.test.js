import test from 'node:test';
import assert from 'node:assert/strict';
import {readActor} from '../../foundry-module/scripts/actors.js';
import {actorCastingRecords} from '../../foundry-module/scripts/actorCasting.js';

function fixture(type='character'){
 const source={type,name:'Caster',system:{resources:{focus:{value:1,max:2}}}},current={type,system:{resources:{focus:{value:2,max:3,cap:3}}}},actorCalls=[],spellCalls=[];
 const actor={documentName:'Actor',uuid:'Actor.a',id:'a',name:'Caster',type,items:new Map(),folder:null,compendium:null,testUserPermission:()=>true,toObject(flag){actorCalls.push(flag);return structuredClone(flag?source:current);}};
 const spellSource={type:'spell',name:'Spell',system:{level:{value:1},traits:{value:[]},location:{value:null}}},spellCurrent={type:'spell',system:{cast:{focusPoints:2}}};
 const item={documentName:'Item',uuid:'Actor.a.Item.s',id:'s',name:'Spell',type:'spell',parent:actor,folder:null,compendium:null,testUserPermission:()=>true,toObject(flag){spellCalls.push(flag);return structuredClone(flag?spellSource:spellCurrent);}};actor.items.set(item.id,item);
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map([['a',actor]]),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>uuid===actor.uuid?actor:uuid===item.uuid?item:null}};
 return {actor,item,source,current,spellSource,spellCurrent,actorCalls,spellCalls};
}
const currentRows=result=>result.records.filter(row=>row.provenance.mapping==='pf2e.actor.casting-current.v1');

test('casting current records preserve separate transformed basis and actual contributor identities',()=>{
 const f=fixture(),result=actorCastingRecords({document:f.actor}),rows=currentRows(result);
 assert.equal(rows.length,4);assert.deepEqual(f.actorCalls,[true,false]);assert.deepEqual(f.spellCalls,[true,false]);
 for(const row of rows){assert.equal(row.section,'spellcasting');assert.equal(row.kind,'field');assert.equal(row.raw.length,1);const raw=row.raw[0];assert.equal(raw.basis,'transformed');assert.equal(row.key,`spellcasting:current:${raw.document_uuid}:${raw.path}`);assert.deepEqual(row.provenance.contributors,[{document_uuid:raw.document_uuid,path:raw.path,basis:'transformed'}]);assert.deepEqual(row.provenance.limitations,['casting_availability_not_evaluated']);assert.equal(row.mapped.value,raw.value);assert.equal(row.mapped.unit,null);}
 assert.equal(rows.find(row=>row.mapped.concept==='current_focus_points').raw[0].value,2);
 assert.equal(result.records.find(row=>row.key==='spellcasting:focus:value').raw[0].value,1);
 assert.equal(rows.find(row=>row.mapped.concept==='current_spell_focus_point_cost').raw[0].document_uuid,f.item.uuid);
});

test('source/default reads avoid current serialization and denied spells never serialize',async()=>{
 for(const sections of [undefined,['source']]){const f=fixture();await readActor({actor_uuid:f.actor.uuid,...(sections?{sections}:{})});assert.ok(f.actorCalls.every(flag=>flag===true));assert.ok(f.spellCalls.every(flag=>flag===true));}
 const f=fixture();f.item.testUserPermission=()=>false;f.item.toObject=()=>{throw Error('denied serializer');};const result=actorCastingRecords({document:f.actor});assert.equal(currentRows(result).length,3);assert.ok(!JSON.stringify(result).includes(f.item.uuid));
});

test('familiar has no Actor transformed read, but readable owned spell costs remain available',()=>{
 const f=fixture('familiar'),result=actorCastingRecords({document:f.actor});assert.deepEqual(f.actorCalls,[true]);assert.deepEqual(f.spellCalls,[true,false]);assert.equal(currentRows(result).length,1);
});

test('missing current values remain absent while source stays independently present',()=>{
 const f=fixture();delete f.current.system.resources.focus.max;delete f.spellCurrent.system.cast.focusPoints;
 const result=actorCastingRecords({document:f.actor});assert.ok(result.reasons.includes('current_fields_unavailable'));assert.ok(result.reasons.includes('availability_not_evaluated'));
 for(const row of currentRows(result).filter(row=>!row.raw[0].present)){assert.equal(Object.hasOwn(row.raw[0],'value'),false);assert.equal(row.mapped.value,null);}
 assert.equal(result.records.find(row=>row.key==='spellcasting:focus:value').raw[0].value,1);
});

test('current-only changes invalidate actual readActor continuation across pages',async()=>{
 for(const mutate of [f=>f.current.system.resources.focus.max++,f=>f.spellCurrent.system.cast.focusPoints++]){
  const f=fixture(),sourceBefore=JSON.stringify([f.source,f.spellSource]),params={actor_uuid:f.actor.uuid,sections:['spellcasting'],limit:1};
  const first=await readActor(params);assert.ok(first.pagination.next_cursor);mutate(f);assert.equal(JSON.stringify([f.source,f.spellSource]),sourceBefore);
  await assert.rejects(readActor({...params,cursor:first.pagination.next_cursor}),error=>error.rpcError.code==='ContentChanged');
 }
});

test('serializer subtype mismatches and wrong owners fail before current interpretation',async()=>{
 for(const mutate of [f=>f.current.type='npc',f=>f.spellCurrent.type='spellcastingEntry',f=>f.source.type='npc',f=>f.spellSource.type='spellcastingEntry',f=>f.item.parent={}]){
  const f=fixture();mutate(f);await assert.rejects(readActor({actor_uuid:f.actor.uuid,sections:['spellcasting']}),error=>error.rpcError.code==='ReadFailed');
 }
 const f=fixture();let invoked=0;f.actor.toObject=flag=>{if(flag)return structuredClone(f.source);const result={system:f.current.system};Object.defineProperty(result,'type',{get(){invoked++;return 'character';}});return result;};
 await assert.rejects(readActor({actor_uuid:f.actor.uuid,sections:['spellcasting']}),error=>error.rpcError.code==='ReadFailed');assert.equal(invoked,0);
});
