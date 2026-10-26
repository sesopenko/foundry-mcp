import test from 'node:test';
import assert from 'node:assert/strict';
import {actorCastingOptions} from '../../foundry-module/scripts/actorCastingOptions.js';
function fixture(mode='prepared',type='character'){
 const target={uuid:'Scene.s.Token.t.Actor.a',type,instance:{token_uuid:'Scene.s.Token.t'}},actorSource={type,system:{resources:{focus:{value:1,max:3}}}};
 const item=(id,type,system)=>({identity:{id,uuid:`${target.uuid}.Item.${id}`,type,name:id,name_truncated:false,actor:{uuid:target.uuid}},source:{name:id,type,system}});
 const entry=item('entry','spellcastingEntry',{prepared:{value:mode,flexible:false},autoHeightenLevel:{value:7},slots:{slot1:{value:0,max:3,prepared:[{id:'spell',expended:false},{id:'spell',expended:true}]}}});
 const spell=item('spell','spell',{level:{value:1},location:{value:'entry',heightenedLevel:4,signature:true,autoHeightenLevel:5,uses:{value:0,max:2}},traits:{value:['cantrip']},ritual:null});
 return {target,actorSource,entry,spell,items:[entry,spell],run(){return actorCastingOptions(target,this.items,actorSource,this.relationships??[]);}};
}
test('prepared repeats preserve slot positions and expenditure independently of zero generic counter',()=>{
 const f=fixture(),before=JSON.stringify(f.items),result=f.run();assert.equal(result.records.length,2);
 assert.deepEqual(result.records.map(row=>[row.mapped.value.preparation_index,row.mapped.value.expended]),[[0,false],[1,true]]);
 for(const row of result.records){const value=row.mapped.value;assert.equal(value.context,'prepared_use');assert.equal(value.slot_rank,1);assert.equal(value.base_rank,1);assert.equal(value.configured_rank,4);assert.equal(value.spell_auto_heighten_rank,5);assert.equal(value.entry_auto_heighten_rank,7);assert.equal(value.cast_rank,null);assert.equal(value.availability,'not_evaluated');assert.equal(value.cantrip,true);assert.equal(value.spell.token_uuid,f.target.instance.token_uuid);assert.equal(value.entry.target_uuid,f.entry.identity.uuid);assert.deepEqual(row.provenance.contributors,row.raw.map(({document_uuid,path,basis})=>({document_uuid,path,basis})));assert.ok(row.raw.every(raw=>raw.basis==='source'));assert.deepEqual(row.provenance.limitations,['availability_not_evaluated','configured_rank_not_final_cast_rank']);}
 assert.equal(new Set(result.records.map(row=>row.key)).size,2);assert.equal(JSON.stringify(f.items),before);
});
test('spontaneous signature preserves repertoire without inventing slot or cast rank alternatives',()=>{
 const f=fixture('spontaneous'),result=f.run(),value=result.records[0].mapped.value;assert.equal(result.records.length,1);assert.equal(value.context,'spontaneous_repertoire');assert.equal(value.resource_scope,'shared_entry_slots');assert.equal(value.signature,true);assert.equal(value.slot_rank,null);assert.equal(value.cast_rank,null);assert.equal(value.preparation_index,null);assert.ok(result.reasons.includes('signature_alternatives_not_evaluated'));
});
test('higher spontaneous slot capacity does not become a heightened spell or signature entitlement',()=>{
 const f=fixture('spontaneous');
 f.spell.source.system.traits.value=[];
 f.spell.source.system.location.heightenedLevel=3;
 f.entry.source.system.slots.slot6={value:2,max:2,prepared:[]};
 for(const signature of [false,true,undefined]){
  if(signature===undefined)delete f.spell.source.system.location.signature;
  else f.spell.source.system.location.signature=signature;
  const result=f.run();assert.equal(result.records.length,1);
  const value=result.records[0].mapped.value;
  assert.equal(value.base_rank,1);assert.equal(value.configured_rank,3);
  assert.equal(value.signature,signature??null);
  assert.equal(value.cast_rank,null);assert.equal(value.slot_rank,null);
  assert.equal(value.availability,'not_evaluated');
  assert.equal(result.reasons.includes('signature_alternatives_not_evaluated'),signature===true);
 }
});
test('innate cantrip uses remain individual zero/absent and never imply unlimited use',()=>{
 const f=fixture('innate');let value=f.run().records[0].mapped.value;assert.deepEqual(value.uses,{value:0,max:2});assert.equal(value.cantrip,true);assert.equal(value.resource_scope,'individual_spell_uses');delete f.spell.source.system.location.uses;value=f.run().records[0].mapped.value;assert.deepEqual(value.uses,{value:null,max:null});assert.equal(value.availability,'not_evaluated');
});
test('focus shares Actor source without fabricating cost or character source max; familiar excluded',()=>{
 for(const type of ['character','npc','familiar']){const f=fixture('focus',type);f.spell.source.system.traits.value=[];const row=f.run().records[0];assert.equal(row.mapped.value.resource_scope,'shared_actor_focus');assert.equal(row.mapped.value.cantrip,false);const actorRaw=row.raw.filter(raw=>raw.document_uuid===f.target.uuid);assert.equal(actorRaw.length,type==='character'?1:type==='npc'?2:0);assert.ok(!JSON.stringify(row).includes('focusPoints'));assert.equal(row.mapped.value.cast_rank,null);}
});
test('distinct focus entries reference one Actor pool without assigning a pool per spell',()=>{
 const f=fixture('focus','npc');
 const secondEntry=structuredClone(f.entry),secondSpell=structuredClone(f.spell);
 secondEntry.identity.id='other-entry';secondEntry.identity.uuid=f.target.uuid+'.Item.other-entry';
 secondSpell.identity.id='other-spell';secondSpell.identity.uuid=f.target.uuid+'.Item.other-spell';
 secondSpell.source.system.location.value='other-entry';
 f.items.push(secondEntry,secondSpell);
 const before=JSON.stringify(f.items),rows=f.run().records;
 assert.equal(rows.length,2);
 assert.notEqual(rows[0].mapped.value.entry.target_uuid,rows[1].mapped.value.entry.target_uuid);
 const pools=rows.map(row=>row.raw.filter(raw=>raw.document_uuid===f.target.uuid));
 assert.deepEqual(pools[0],pools[1]);
 assert.deepEqual(pools[0].map(raw=>[raw.path,raw.value]),[['/system/resources/focus/value',1],['/system/resources/focus/max',3]]);
 assert.ok(rows.every(row=>row.mapped.value.resource_scope==='shared_actor_focus'&&row.mapped.value.availability==='not_evaluated'&&row.mapped.value.uses===null));
 assert.ok(rows.every(row=>!row.raw.some(raw=>raw.path.includes('/location/uses/')||raw.path.includes('/cast/focusPoints'))));
 assert.equal(JSON.stringify(f.items),before);
});
test('unassigned canonical statuses stay distinct and no unresolved spell identities are fabricated',()=>{
 for(const status of ['missing','denied','unsupported']){const f=fixture();f.items=[f.spell];f.relationships=[{key:`spellcasting:assignment:${f.spell.identity.uuid}`,mapped:{value:{status,target_uuid:null}}}];const value=f.run().records[0].mapped.value;assert.deepEqual(value.entry,{status,target_uuid:null});assert.equal(value.context,'listed_spell');assert.equal(value.mode,null);}
 const f=fixture();f.items=[f.spell];assert.throws(()=>f.run(),/canonical unresolved/);
});
test('flexible, ritual, item and unknown modes remain unsupported contexts with safe scalar witnesses',()=>{
 for(const mode of ['ritual','items','unknown']){const f=fixture(mode),result=f.run();assert.equal(result.records[0].mapped.value.context,'unsupported_mode');assert.ok(result.reasons.includes('unsupported_casting_mode'));}
 const f=fixture();f.entry.source.system.prepared.flexible=true;assert.equal(f.run().records[0].mapped.value.context,'unsupported_mode');
 const ritual=fixture('spontaneous');ritual.spell.source.system.ritual={primary:{check:'Arcana'},secondary:{checks:'Occultism',casters:2}};const row=ritual.run().records[0];assert.equal(row.mapped.value.context,'unsupported_mode');assert.ok(row.raw.some(raw=>raw.path==='/system/ritual/primary/check'&&raw.value==='Arcana'));assert.ok(!row.raw.some(raw=>raw.path==='/system/ritual'));
 ritual.spell.source.system.ritual={};assert.throws(()=>ritual.run(),/ritual requires/);
});
test('legacy preparation shapes keep safe siblings, slot11 never becomes spell rank11',()=>{
 const f=fixture();f.entry.source.system.slots.slot1.prepared.push('legacy',{id:'spell',expended:'bad'},{id:'missing',expended:false});f.entry.source.system.slots.slot11={prepared:[{id:'spell',expended:false}]};const result=f.run();assert.equal(result.records.length,3);assert.equal(result.records[2].mapped.value.expended,null);assert.ok(result.reasons.includes('malformed_preparation'));assert.ok(result.reasons.includes('template_slot11_no_spell_rank_semantics'));assert.ok(!result.records.some(row=>row.mapped.value.slot_rank===11));
 f.entry.source.system.slots.slot2=null;assert.equal(f.run().records.length,3);assert.ok(f.run().reasons.includes('malformed_slot'));
});
test('selected getters rejected without execution, inherited leaves absent, unrelated getters unread',()=>{
 const f=fixture('spontaneous');let called=0;Object.defineProperty(f.spell.source.system,'damage',{get(){throw Error('unrelated');}});assert.equal(f.run().records.length,1);
 const prototype={heightenedLevel:9};f.spell.source.system.location=Object.assign(Object.create(prototype),{value:'entry'});assert.equal(f.run().records[0].mapped.value.configured_rank,null);
 Object.defineProperty(f.spell.source.system.location,'signature',{get(){called++;return true;}});assert.throws(()=>f.run(),TypeError);assert.equal(called,0);
});
test('selected malformed scalar/identity/owner data and standalone bounds reject',()=>{
 for(const value of [true,null,'1',NaN,Infinity]){const f=fixture();f.spell.source.system.level.value=value;assert.throws(()=>f.run(),TypeError);}
 const wrong=fixture();wrong.spell.identity.actor.uuid='Actor.other';assert.throws(()=>wrong.run(),/identity/);
 const traits=fixture();traits.spell.source.system.traits.value=Array(201).fill('cantrip');assert.throws(()=>traits.run(),/200/);
 const items=fixture();items.items=Array(12001).fill(items.spell);assert.throws(()=>items.run(),/12000/);
 const preparations=fixture();for(let rank=0;rank<5;rank++)preparations.entry.source.system.slots[`slot${rank}`]={prepared:Array.from({length:6000},()=>({id:null,expended:false}))};assert.throws(()=>preparations.run(),/24000 preparation/);
});
