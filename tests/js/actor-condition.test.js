import test from 'node:test';
import assert from 'node:assert/strict';
import {conditionFields} from '../../foundry-module/scripts/actorCondition.js';
const input=()=>({type:'condition',system:{value:{isValued:true,value:0},persistent:{formula:'@actor.level + 1d6',damageType:'fire',dc:15,criticalHit:false},references:{parent:{id:'parent'},children:[{id:'child',type:'condition'}],overrides:[],overriddenBy:[{id:'other',type:'condition'}]},overrides:['frightened','frightened'],fromSpell:false,group:null,traits:{value:['magical'],otherTags:[]},slug:'persistent-damage',publication:{title:'Player Core',authors:'Paizo',license:'ORC',remaster:true},active:true,suppressed:false,duration:{value:-1},rules:[{key:'SECRET'}],description:{value:'SECRET'}}});
const row=(rows,path)=>rows.find(row=>row.path===path);
test('condition selector retains authored zero/null/false and exact local references without mutation',()=>{
 const source=input(),before=JSON.stringify(source),rows=conditionFields(source);
 assert.equal(row(rows,'/system/value/value').value,0);assert.equal(row(rows,'/system/fromSpell').value,false);
 assert.equal(row(rows,'/system/group').value,null);assert.deepEqual(row(rows,'/system/references/overrides').value,[]);
 assert.equal(row(rows,'/system/references/parent/id').value,'parent');assert.equal(row(rows,'/system/references/children/0/type').value,'condition');
 assert.equal(row(rows,'/system/persistent/formula').value,'@actor.level + 1d6');assert.equal(row(rows,'/system/overrides/1').value,'frightened');
 assert.equal(JSON.stringify(source),before);assert.ok(!JSON.stringify(rows).includes('SECRET'));
 assert.ok(!rows.some(row=>/active|suppressed|duration|rules|description/.test(row.path)));
 assert.equal(conditionFields({type:'effect'}),null);assert.equal(conditionFields(null),null);
});
test('unvalued, missing, nullable and empty states stay distinct without fabricated defaults',()=>{
 const source=input();source.system.value={isValued:false,value:null};source.system.persistent=null;source.system.references.parent=null;
 let rows=conditionFields(source);for(const path of ['/system/value/value','/system/persistent','/system/references/parent'])assert.equal(row(rows,path).value,null);
 delete source.system.value.value;delete source.system.persistent;delete source.system.references.parent;delete source.system.overrides;
 rows=conditionFields(source);for(const path of ['/system/value/value','/system/persistent','/system/references/parent','/system/overrides']){assert.equal(row(rows,path).present,false);assert.ok(!Object.hasOwn(row(rows,path),'value'));}
 assert.ok(rows.every(row=>!row.present||row.value===null||typeof row.value!=='object'||(Array.isArray(row.value)&&row.value.length===0)));
});
test('condition malformed selected values fail without leaking object values',()=>{
 for(const change of [source=>source.system.value.isValued=1,source=>source.system.value.value=Infinity,source=>source.system.value.value={},source=>source.system.persistent=[],source=>source.system.persistent.dc=NaN,source=>source.system.persistent.formula=3,source=>source.system.persistent.criticalHit=null,source=>source.system.references.parent='parent',source=>source.system.references.children=[null],source=>source.system.references.children=[{id:'id',type:'effect'}],source=>source.system.references.children=[{id:{},type:'condition'}],source=>source.system.references.overriddenBy=null,source=>source.system.overrides=[{}],source=>source.system.traits.value=[false],source=>source.system.publication.remaster='yes']) {
  const source=input();change(source);assert.throws(()=>conditionFields(source),TypeError);
 }
});
test('only schema-optional own undefined is absent and prepared getters remain untouched',()=>{
 const source=input();source.system.persistent=undefined;
 let rows=conditionFields(source);assert.equal(row(rows,'/system/persistent').present,false);assert.ok(!Object.hasOwn(row(rows,'/system/persistent'),'value'));
 Object.defineProperty(source.system,'active',{get(){throw new Error('prepared active accessed');}});
 Object.defineProperty(source.system,'duration',{get(){throw new Error('prepared duration accessed');}});
 Object.defineProperty(source.system,'rules',{get(){throw new Error('rules accessed');}});
 rows=conditionFields(source);assert.ok(rows.length>0);
 source.system.value.value=undefined;assert.throws(()=>conditionFields(source),TypeError);
});
