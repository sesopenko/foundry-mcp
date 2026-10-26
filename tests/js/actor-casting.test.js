import test from 'node:test';
import assert from 'node:assert/strict';
import {actorCastingRecords} from '../../foundry-module/scripts/actorCasting.js';
function fixture(type='npc',synthetic=false){
 globalThis.game={user:{isGM:true}};
 const actor={documentName:'Actor',id:'a',uuid:synthetic?'Scene.s.Token.t.Actor.a':'Actor.a',name:'Actor',type,items:new Map(),testUserPermission:()=>true,toObject:()=>({type,system:{resources:{focus:{value:0,max:3}}}})};
 const target={document:actor};
 if(synthetic){const scene={uuid:'Scene.s',name:'Scene'};target.token={uuid:'Scene.s.Token.t',name:'Token',parent:scene,isLinked:false,baseActor:null};}
 const add=(id,type,system)=>{const source={name:id,type,system};const item={id,uuid:actor.uuid+'.Item.'+id,documentName:'Item',type,name:id,parent:actor,testUserPermission:()=>true,toObject:()=>structuredClone(source)};actor.items.set(id,item);return {item,source};};
 const entry=add('entry','spellcastingEntry',{prepared:{value:'prepared'},slots:{slot1:{value:0,max:3,prepared:[{id:'spell',expended:false},{id:'spell',expended:true}]}}});
 const spell=add('spell','spell',{level:{value:1},traits:{value:['cantrip']},location:{value:'entry',signature:true,heightenedLevel:4,autoHeightenLevel:5,uses:{value:0,max:2}}});
 return {actor,target,add,entry,spell};
}
const join=(rows,concept)=>rows.filter(r=>r.mapped.concept===concept);
test('source identity names preserve codepoint bounds independently of display relationship names',()=>{
 const f=fixture();f.spell.source.name='Spell'+'😀'.repeat(257);f.spell.item.name='Spell (Heightened)';f.entry.source.name='SourceEntry';f.entry.item.name='Public entry label';
 const rows=actorCastingRecords(f.target).records;
 const spell=join(rows,'casting_spell')[0],entry=join(rows,'casting_entry')[0];
 assert.equal(spell.mapped.value.name,'Spell'+'😀'.repeat(251));assert.equal(spell.mapped.value.name_truncated,true);assert.equal(entry.mapped.value.name,'SourceEntry');
 assert.equal(join(rows,'casting_spell_assignment')[0].mapped.value.name,'Public entry label');
 assert.equal(join(rows,'casting_preparation')[0].mapped.value.name,'Spell (Heightened)');
 for(const option of join(rows,'casting_contextual_option')){assert.equal(option.mapped.value.spell.name,spell.mapped.value.name);assert.equal(option.mapped.value.entry.name,'SourceEntry');}
});
test('same-owner joins preserve repeated preparation indexes and separate source resource contexts',()=>{
 const f=fixture(),before=JSON.stringify([f.entry.source,f.spell.source]),result=actorCastingRecords(f.target),rows=result.records;
 assert.deepEqual(join(rows,'casting_preparation').map(r=>r.raw[0].path),['/system/slots/slot1/prepared/0/id','/system/slots/slot1/prepared/1/id']);
 assert.ok(join(rows,'casting_preparation').every(r=>r.mapped.value.target_uuid===f.spell.item.uuid));
 assert.equal(join(rows,'casting_spell_assignment')[0].mapped.value.target_uuid,f.entry.item.uuid);
 for(const [uuid,path,value]of [[f.entry.item.uuid,'/system/slots/slot1/value',0],[f.entry.item.uuid,'/system/slots/slot1/prepared/1/expended',true],[f.spell.item.uuid,'/system/location/uses/value',0],[f.spell.item.uuid,'/system/location/heightenedLevel',4],[f.actor.uuid,'/system/resources/focus/value',0]])assert.equal(rows.find(r=>r.raw[0]?.document_uuid===uuid&&r.raw[0]?.path===path).raw[0].value,value);
 assert.deepEqual(result.reasons,['availability_not_evaluated','current_fields_unavailable','signature_alternatives_not_evaluated']);assert.equal(new Set(rows.map(r=>r.key)).size,rows.length);assert.equal(JSON.stringify([f.entry.source,f.spell.source]),before);
 const options=join(rows,'casting_contextual_option');assert.equal(options.length,2);assert.ok(options.every(row=>row.key.startsWith('spellcasting:option:')&&row.provenance.mapping==='pf2e.actor.casting-options.v1'));assert.deepEqual(options.map(row=>row.mapped.value.preparation_index),[0,1]);
});
test('missing denied wrong-type and mismatched assignment remain distinct without leaking identities',()=>{
 for(const [change,status]of [[f=>f.actor.items.delete('spell'),'missing'],[f=>f.spell.item.testUserPermission=()=>false,'denied'],[f=>f.spell.item.type='equipment','unsupported'],[f=>f.spell.source.system.location.value='another','mismatched_assignment']]){
  const f=fixture();change(f);const rows=actorCastingRecords(f.target).records;assert.deepEqual(join(rows,'casting_preparation')[0].mapped.value,{status,target_uuid:null});if(status==='denied'){assert.equal(join(rows,'casting_spell').length,0);assert.deepEqual(join(rows,'casting_item')[0].raw,[]);}
 }
 const f=fixture();f.spell.source.system.location.value=null;assert.deepEqual(join(actorCastingRecords(f.target).records,'casting_spell_assignment')[0].mapped.value,{status:'missing',target_uuid:null});
});
test('focus character source excludes derived max; creature optional max and absence are preserved',()=>{
 for(const type of ['character','npc','familiar']){const f=fixture(type);const rows=actorCastingRecords(f.target).records;assert.equal(join(rows,'casting_focus_max').length,type==='character'?0:1);}
 const f=fixture();f.actor.toObject=()=>({type:'npc',system:{}});for(const row of join(actorCastingRecords(f.target).records,'casting_focus_value')){assert.equal(row.raw[0].present,false);assert.equal(row.mapped.value,null);}
 f.actor.toObject=()=>({type:'npc',system:{resources:{focus:{value:'0'}}}});assert.throws(()=>actorCastingRecords(f.target),/unexpected type|finite number/);
 f.actor.toObject=()=>({type:'npc',system:{resources:{focus:{value:undefined}}}});assert.throws(()=>actorCastingRecords(f.target),/finite number/);
 f.actor.toObject=()=>({type:'npc',system:{resources:{focus:{value:0,max:undefined}}}});assert.equal(actorCastingRecords(f.target).records.find(r=>r.key==='spellcasting:focus:max').raw[0].present,false);
});
test('legacy preparations and unsupported modes stay partial while valid siblings remain readable',()=>{
 for(const mode of ['ritual','items','unknown']){const f=fixture();f.entry.source.system.prepared.value=mode;f.entry.source.system.slots.slot2={prepared:{0:{id:'spell'}}};const result=actorCastingRecords(f.target);assert.ok(result.reasons.includes('unsupported_casting_mode'));assert.ok(result.reasons.includes('malformed_preparations'));assert.equal(join(result.records,'casting_preparation').length,2);}
 const f=fixture();f.entry.source.system.prepared.flexible=true;assert.ok(actorCastingRecords(f.target).reasons.includes('unsupported_casting_mode'));
});
test('synthetic identity remains selected actor and token; arbitrary descriptions/getters are not evaluated',()=>{
 const f=fixture('npc',true);const original=f.spell.item.toObject;f.spell.item.toObject=()=>{const s=original();for(const key of ['description','rules','overlays','damage'])Object.defineProperty(s.system,key,{get(){throw Error('must not access '+key);}});return s;};
 const rows=actorCastingRecords(f.target).records;assert.ok(join(rows,'casting_spell_assignment').every(r=>r.mapped.value.token_uuid===f.target.token.uuid));assert.ok(join(rows,'casting_spell').every(r=>r.mapped.value.target_uuid.startsWith(f.actor.uuid+'.Item.')));
});
test('omitted spell level traits and location remain absent instead of becoming own undefined',()=>{
 const f=fixture();f.spell.source.system={};const rows=actorCastingRecords(f.target).records;
 for(const path of ['/system/level','/system/traits','/system/location']){const row=rows.find(r=>r.kind==='field'&&r.raw[0]?.document_uuid===f.spell.item.uuid&&r.raw[0]?.path===path);assert.equal(row.raw[0].present,false);assert.equal(row.mapped.value,null);}
 assert.equal(join(rows,'casting_spell_assignment')[0].mapped.value.status,'missing');
 f.spell.source.system={traits:null};assert.throws(()=>actorCastingRecords(f.target),/traits source/);
});
