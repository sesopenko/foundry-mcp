import test from 'node:test';
import assert from 'node:assert/strict';
import {meleeFields} from '../../foundry-module/scripts/actorMelee.js';
const source=()=>({type:'melee',system:{action:'strike',bonus:{value:17},area:null,range:{increment:60,max:null},subjectToMAP:true,slug:'attack',traits:{value:['ranged','custom'],otherTags:[]},damageRolls:{'first/key~':{damage:'2d8+7',damageType:'piercing',category:null},second:{damage:'1d6',damageType:'fire',category:'persistent'}},attackEffects:{value:['Knockdown','custom label']},publication:{title:'Book',authors:'A',license:'ORC',remaster:true},rules:[{secret:'excluded'}],material:{secret:'prepared'},runes:{property:['prepared']}}});
const row=(rows,path)=>rows.find(entry=>entry.path===path);
test('ranged attacks retain source ranges and only strike is labelled Strike',()=>{
  const input=source();let rows=meleeFields(input);
  assert.equal(row(rows,'/system/action').mapped_value,'Strike');assert.equal(row(rows,'/system/range/increment').concept,'ranged_increment_feet');
  assert.equal(row(rows,'/system/range/increment').value,60);assert.equal(row(rows,'/system/range/max').value,null);
  for(const action of ['area-fire','auto-fire','custom']){input.system.action=action;rows=meleeFields(input);assert.notEqual(row(rows,'/system/action').mapped_value,'Strike');assert.equal(row(rows,'/system/action').value,action);}
  input.system.range=null;rows=meleeFields(input);assert.equal(row(rows,'/system/range').mapped_value,'no_explicit_range');
  delete input.system.range;rows=meleeFields(input);assert.equal(row(rows,'/system/range').present,false);assert.ok(!Object.hasOwn(row(rows,'/system/range'),'mapped_value'));
});
test('mixed authored damage components retain escaped keys categories and effects',()=>{
  const input=source();const before=JSON.stringify(input);const rows=meleeFields(input);
  assert.equal(row(rows,'/system/bonus/value').value,17);assert.equal(row(rows,'/system/bonus/value').concept,'authored_attack_bonus');
  assert.equal(row(rows,'/system/damageRolls/first~1key~0/damage').value,'2d8+7');
  assert.equal(row(rows,'/system/damageRolls/second/category').value,'persistent');
  assert.equal(row(rows,'/system/damageRolls/first~1key~0/category').value,null);
  assert.equal(row(rows,'/system/attackEffects/value/0').value,'Knockdown');
  assert.ok(row(rows,'/system/attackEffects/value/0').limitations.includes('label_not_document_uuid'));
  assert.equal(JSON.stringify(input),before);assert.ok(!JSON.stringify(rows).includes('prepared'));assert.ok(!JSON.stringify(rows).includes('excluded'));
});
test('area-fire and auto-fire preserve area without defaults or damage rewriting',()=>{
  const input=source();input.system.action='area-fire';input.system.area={type:'cone',value:30};input.system.damageRolls={bleed:{damage:'1d6',damageType:'bleed',category:null}};
  let rows=meleeFields(input);assert.equal(row(rows,'/system/area/type').value,'cone');assert.equal(row(rows,'/system/area/value').value,30);assert.equal(row(rows,'/system/damageRolls/bleed/category').value,null);
  input.system.action='auto-fire';input.system.area=null;rows=meleeFields(input);assert.equal(row(rows,'/system/area').value,null);
});
test('empty absent null and zero remain distinct with no calculated attacks',()=>{
  const input=source();input.system.bonus.value=0;input.system.damageRolls={};input.system.attackEffects.value=[];
  let rows=meleeFields(input);assert.equal(row(rows,'/system/bonus/value').value,0);assert.deepEqual(row(rows,'/system/damageRolls').value,{});assert.deepEqual(row(rows,'/system/attackEffects/value').value,[]);
  delete input.system.damageRolls;rows=meleeFields(input);assert.equal(row(rows,'/system/damageRolls').present,false);
  assert.equal(meleeFields({type:'weapon'}),null);assert.equal(meleeFields(null),null);
});
test('malformed source values cannot leak arbitrary object payloads',()=>{
  for(const change of [s=>s.system.damageRolls=[],s=>s.system.damageRolls={bad:null},s=>s.system.damageRolls={bad:{damage:{secret:1},damageType:'fire',category:null}},s=>s.system.range={increment:{secret:1},max:null},s=>s.system.attackEffects.value=[{secret:1}],s=>s.system.bonus.value=Infinity,s=>s.system.area=[]]){const input=source();change(input);assert.throws(()=>meleeFields(input),TypeError);}
});

test('null range with a thrown trait preserves uncertainty instead of exclusive melee capability',()=>{
  const input=source();input.system.range=null;input.system.traits.value=['thrown-20'];
  const rows=meleeFields(input);const range=row(rows,'/system/range');
  assert.equal(range.value,null);assert.equal(range.mapped_value,'no_explicit_range');
  assert.equal(row(rows,'/system/traits/value/0').value,'thrown-20');
  assert.ok(range.limitations.includes('source_null_range_does_not_exclude_trait_derived_ranged_attacks'));
  assert.ok(!rows.some(entry=>entry.path==='/system/range/increment'));
});
test('JSON Pointer escaping keeps hostile damage keys as provenance without fabricated identity',()=>{
  const input=source();input.system.damageRolls=JSON.parse('{"__proto__":{"damage":"1d4","damageType":"cold","category":null},"a~/b":{"damage":"2d6","damageType":"fire","category":"splash"}}');
  const rows=meleeFields(input);
  assert.equal(row(rows,'/system/damageRolls/__proto__/damage').value,'1d4');
  assert.equal(row(rows,'/system/damageRolls/a~0~1b/damage').value,'2d6');
  assert.ok(rows.every(entry=>!Object.hasOwn(entry,'uuid')));
  assert.equal({}.damage,undefined);
});
