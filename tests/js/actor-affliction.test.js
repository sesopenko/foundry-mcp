import test from 'node:test';
import assert from 'node:assert/strict';
import {afflictionFields} from '../../foundry-module/scripts/actorAffliction.js';
const input=()=>({type:'affliction',system:{level:{value:3},save:{type:'fortitude',value:19},status:{onset:false,stage:1,progress:0},onset:null,stages:[{damage:[{formula:'2d6 + @actor.level',damageType:'poison',category:null}],conditions:[{slug:'sickened',value:0,linked:false}],effects:[{uuid:'Compendium.pf2e.effects.Item.abc'}],duration:{value:1,unit:'rounds'}}],duration:{value:-1,unit:'unlimited',expiry:null},start:{value:0,initiative:null},context:{origin:{actor:'Actor.origin',token:null,item:null,spellcasting:null,rollOptions:[]},target:null,roll:null},fromSpell:false,traits:{value:['poison'],otherTags:[]},slug:null,publication:{title:'GM Core',authors:'Paizo',license:'ORC',remaster:true}}});
const row=(rows,path)=>rows.find(row=>row.path===path);
test('affliction selector preserves exact primitive source without acting on formulas or references',()=>{
 const source=input(),before=JSON.stringify(source),rows=afflictionFields(source);
 assert.equal(row(rows,'/system/stages/0/damage/0/formula').value,'2d6 + @actor.level');
 assert.equal(row(rows,'/system/stages/0/conditions/0/value').value,0);assert.equal(row(rows,'/system/stages/0/conditions/0/linked').value,false);
 assert.equal(row(rows,'/system/stages/0/effects/0/uuid').value,'Compendium.pf2e.effects.Item.abc');
 assert.deepEqual(row(rows,'/system/status/stage').mapped_value,{source_stage:1,stage_index:0,status:'resolved',stage_count:1});
 assert.equal(row(rows,'/system/onset').value,null);assert.equal(row(rows,'/system/start/initiative').value,null);
 assert.deepEqual(row(rows,'/system/context/origin/rollOptions').value,[]);assert.equal(JSON.stringify(source),before);
 assert.equal(afflictionFields({type:'effect'}),null);assert.equal(afflictionFields(null),null);
});
test('one-based stored stages never clamp or fabricate stages and invalid ordinals remain exact',()=>{
 for(const value of [0,-1,2,1.5]){const source=input();source.system.status.stage=value;const mapped=row(afflictionFields(source),'/system/status/stage');assert.equal(mapped.value,value);assert.deepEqual(mapped.mapped_value,{source_stage:value,stage_index:null,status:'out_of_range',stage_count:1});}
 const source=input();source.system.stages=[];
 let rows=afflictionFields(source);assert.deepEqual(row(rows,'/system/stages').value,[]);assert.equal(row(rows,'/system/status/stage').mapped_value.status,'out_of_range');assert.ok(!rows.some(row=>row.path.startsWith('/system/stages/')));
 delete source.system.stages;rows=afflictionFields(source);assert.equal(row(rows,'/system/status/stage').mapped_value.status,'unverified');assert.equal(row(rows,'/system/status/stage').mapped_value.stage_count,null);
 delete source.system.status.stage;rows=afflictionFields(source);assert.equal(row(rows,'/system/status/stage').present,false);assert.ok(!Object.hasOwn(row(rows,'/system/status/stage'),'mapped_value'));
});
test('multiple stage order and explicit optional absence stay distinct from null and empty arrays',()=>{
 const source=input();source.system.stages.push({damage:[],conditions:[],effects:[],duration:{value:0,unit:'encounter'}});source.system.status.stage=2;
 source.system.onset=undefined;source.system.context=undefined;source.system.stages[0].damage[0].category=undefined;source.system.stages[0].conditions[0].value=undefined;source.system.stages[0].conditions[0].linked=undefined;
 const rows=afflictionFields(source);assert.equal(row(rows,'/system/status/stage').mapped_value.stage_index,1);
 for(const path of ['/system/onset','/system/context','/system/stages/0/damage/0/category','/system/stages/0/conditions/0/value','/system/stages/0/conditions/0/linked'])assert.equal(row(rows,path).present,false);
 assert.deepEqual(row(rows,'/system/stages/1/effects').value,[]);
});
test('selected malformed source rejects rather than flattening arbitrary objects',()=>{
 for(const change of [s=>s.system.save.type='armor',s=>s.system.save.value=NaN,s=>s.system.status.stage=Infinity,s=>s.system.status.stage=null,s=>s.system.status.progress={},s=>s.system.stages=null,s=>s.system.stages=[null],s=>s.system.stages[0].damage=[{formula:42}],s=>s.system.stages[0].conditions[0].linked=null,s=>s.system.stages[0].effects[0].uuid={},s=>s.system.context=[],s=>s.system.traits.value=[3],s=>s.system.level.value=1.2,s=>s.system.fromSpell=undefined]){
  const source=input();change(source);assert.throws(()=>afflictionFields(source),TypeError);
 }
});
test('prepared getters, arbitrary siblings, descriptions and rule elements are excluded',()=>{
 const source=input();for(const key of ['expired','remaining','badge','rules','description'])Object.defineProperty(source.system,key,{get(){throw new Error('forbidden '+key);}});
 source.system.stages[0].unknown={secret:true};const rows=afflictionFields(source);
 assert.ok(rows.length>0);assert.ok(!rows.some(row=>/expired|remaining|badge|rules|description|unknown/.test(row.path)));
 assert.ok(rows.every(row=>!row.present||row.value===null||typeof row.value!=='object'||Array.isArray(row.value)&&row.value.length===0));
});
