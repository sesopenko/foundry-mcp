import test from 'node:test';
import assert from 'node:assert/strict';
import {spellcastingEntryFields as fields,spellcastingEntryIssues as issues} from '../../foundry-module/scripts/actorSpellcastingEntry.js';
const source=()=>({type:'spellcastingEntry',system:{tradition:{value:'arcane'},prepared:{value:'prepared',flexible:false,validItems:null},ability:{value:'int'},proficiency:{value:2},spelldc:{value:12,dc:22},autoHeightenLevel:{value:null},slots:{slot1:{value:0,max:3,prepared:[{id:'spell-a',expended:false},{id:'spell-a',expended:true},{id:null,expended:false}]}},traits:{otherTags:[]},slug:null,publication:{title:'Source',authors:'Author',license:'ORC',remaster:true}}});
const row=(rows,path)=>rows.find(r=>r.path==='/system/'+path);
test('stored zero slots and repeated preparations retain separate indexes without exhaustion inference',()=>{
 const input=source(),before=JSON.stringify(input),rows=fields(input);
 assert.equal(row(rows,'slots/slot1/value').value,0);
 assert.equal(row(rows,'slots/slot1/prepared/0/id').value,'spell-a');assert.equal(row(rows,'slots/slot1/prepared/1/id').value,'spell-a');assert.equal(row(rows,'slots/slot1/prepared/1/expended').value,true);assert.equal(row(rows,'slots/slot1/prepared/2/id').value,null);
 assert.deepEqual(issues(input),[]);assert.equal(JSON.stringify(input),before);assert.ok(rows.every(r=>r.limitations.includes('source_only_no_castability_or_resource_expenditure')));
 assert.equal(fields({type:'spell'}),null);assert.deepEqual(issues(null),[]);
});
test('focus innate spontaneous and unknown modes retain exact source codes and resource scalars',()=>{
 for(const mode of ['focus','innate','spontaneous','future-mode']){const input=source();input.system.prepared.value=mode;input.system.prepared.flexible=true;input.system.prepared.validItems='scroll';input.system.autoHeightenLevel.value=7;
 const rows=fields(input);assert.equal(row(rows,'prepared/value').value,mode);assert.equal(row(rows,'prepared/flexible').value,true);assert.equal(row(rows,'prepared/validItems').value,'scroll');assert.equal(row(rows,'autoHeightenLevel/value').value,7);assert.equal(row(rows,'spelldc/value').value,12);assert.equal(row(rows,'spelldc/dc').value,22);}
});
test('missing optional fields and preparations differ from explicit null and empty arrays',()=>{
 const input=source();delete input.system.prepared.flexible;input.system.prepared.validItems=undefined;input.system.slots.slot0={value:0,max:0,prepared:[]};delete input.system.slots.slot1.prepared[0].expended;
 const rows=fields(input);assert.equal(row(rows,'prepared/flexible').present,false);assert.equal(row(rows,'prepared/validItems').present,false);assert.deepEqual(row(rows,'slots/slot0/prepared').value,[]);assert.equal(row(rows,'slots/slot2/prepared').present,false);assert.equal(row(rows,'slots/slot1/prepared/0/expended').present,false);
});
test('malformed legacy preparation containers and members report exact gaps and preserve safe siblings',()=>{
 const input=source();input.system.slots.slot1.prepared={0:{id:'secret'}};input.system.slots.slot2={value:1,max:2,prepared:[null,{id:3,expended:'no'},{id:'ok',expended:false}]};input.system.slots.slot3=[];
 const rows=fields(input),gaps=issues(input);assert.equal(row(rows,'slots/slot1/prepared'),undefined);assert.equal(row(rows,'slots/slot2/prepared/1/id'),undefined);assert.equal(row(rows,'slots/slot2/prepared/2/id').value,'ok');
 assert.ok(gaps.some(i=>i.path==='/system/slots/slot1/prepared'&&i.reason==='malformed_preparations'));assert.ok(gaps.some(i=>i.path==='/system/slots/slot2/prepared/1/id'));assert.ok(gaps.some(i=>i.path==='/system/slots/slot3'&&i.reason==='malformed_slot'));assert.ok(!JSON.stringify(gaps).includes('secret'));
});
test('source selection rejects invalid scalar types and bounded complexity without evaluating unrelated fields',()=>{
 for(const change of [s=>s.system.spelldc.value='12',s=>s.system.proficiency.value=Infinity,s=>s.system.prepared.flexible=0,s=>s.system.autoHeightenLevel.value=undefined,s=>s.system.traits.otherTags={}]){const input=source();change(input);assert.throws(()=>fields(input),TypeError);}
 const input=source();for(const key of ['description','rules','showSlotlessLevels','statistic','flags'])Object.defineProperty(input.system,key,{get(){throw Error(key);}});fields(input);
 input.system.slots.slot1.prepared=Array.from({length:65},()=>null);assert.throws(()=>issues(input),/64/);
 input.system.slots.slot1.prepared=Array(6001);assert.throws(()=>fields(input),/6000/);
});
test('official template slot11 is retained without inventing rank semantics; unknown slot keys remain explicit gaps',()=>{
 const input=source();input.system.slots.slot11={value:0,max:0,prepared:[]};input.system.slots['slot12/legacy']={private:'not disclosed'};
 const rows=fields(input);assert.equal(row(rows,'slots/slot11/value').value,0);assert.deepEqual(row(rows,'slots/slot11/prepared').value,[]);assert.ok(rows.every(r=>r.limitations.includes('template_slot11_no_spell_rank_semantics')));assert.deepEqual(issues(input),[{path:'/system/slots/slot12~1legacy',reason:'unsupported_slot_key'}]);
 delete input.system.slots['slot12/legacy'];delete input.system.slots.slot1.prepared[0].expended;assert.deepEqual(issues(input),[]);assert.equal(row(fields(input),'slots/slot1/prepared/0/expended').present,false);
});
