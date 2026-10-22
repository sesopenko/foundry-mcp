import test from 'node:test';
import assert from 'node:assert/strict';
import {shieldFields} from '../../foundry-module/scripts/actorShield.js';
import {physicalFields} from '../../foundry-module/scripts/actorPhysical.js';
const source=()=>({type:'shield',system:{baseItem:'steel-shield',acBonus:2,speedPenalty:-5,grade:null,runes:{reinforcing:0},specific:null,traits:{integrated:null,value:['future-trait'],otherTags:[],rarity:'common'},slug:null,publication:{title:'Source',authors:'Author',license:'ORC',remaster:true}}});
const row=(rows,path)=>rows.find(r=>r.path==='/system/'+path);
test('shield exact source values retain penalties zero null and unknown codes',()=>{
 const input=source(),before=JSON.stringify(input),rows=shieldFields(input);
 for(const [path,value] of [['acBonus',2],['speedPenalty',-5],['grade',null],['runes/reinforcing',0],['traits/integrated',null],['traits/value/0','future-trait'],['slug',null],['publication/remaster',true]])assert.equal(row(rows,path).value,value);
 assert.ok(rows.every(r=>r.limitations.includes('source_only_no_actor_shield_calculation')));
 assert.equal(JSON.stringify(input),before);assert.equal(shieldFields(null),null);assert.equal(shieldFields({type:'armor'}),null);
});
test('current integrated weapon and specific baseline runes remain separate',()=>{
 const input=source();input.system.traits.integrated={runes:{potency:1,striking:0,property:['future-rune']},versatile:{selected:'future-damage'}};
 input.system.specific={material:{type:'future-metal',grade:null},runes:{reinforcing:3},integrated:{runes:{potency:2,striking:1,property:[]}}};
 const rows=shieldFields(input);
 for(const [path,value]of [['runes/reinforcing',0],['specific/runes/reinforcing',3],['specific/material/type','future-metal'],['specific/material/grade',null],['traits/integrated/runes/potency',1],['traits/integrated/runes/striking',0],['traits/integrated/runes/property/0','future-rune'],['traits/integrated/versatile/selected','future-damage'],['specific/integrated/runes/potency',2],['specific/integrated/runes/striking',1]])assert.equal(row(rows,path).value,value);
 assert.deepEqual(row(rows,'specific/integrated/runes/property').value,[]);
});
test('missing nullable empty object and array markers preserve source distinctions',()=>{
 const input=source();delete input.system.specific;assert.deepEqual(row(shieldFields(input),'specific'),{path:'/system/specific',present:false,concept:'shield_specific_baseline',limitations:['source_only_no_actor_shield_calculation']});
 for(const path of ['specific','runes']){input.system[path]={};assert.deepEqual(row(shieldFields(input),path).value,{});}
 input.system.specific={material:{},runes:{},integrated:null};let rows=shieldFields(input);assert.deepEqual(row(rows,'specific/material').value,{});assert.equal(row(rows,'specific/integrated').value,null);
 input.system.specific.integrated={};assert.deepEqual(row(shieldFields(input),'specific/integrated').value,{});
 input.system.traits.integrated={runes:{},versatile:null};rows=shieldFields(input);assert.deepEqual(row(rows,'traits/integrated/runes').value,{});assert.equal(row(rows,'traits/integrated/versatile').value,null);
 input.system.traits.integrated.versatile={};assert.deepEqual(row(shieldFields(input),'traits/integrated/versatile').value,{});
 input.system.traits.value=[];assert.deepEqual(row(shieldFields(input),'traits/value').value,[]);
});
test('selected malformed values reject without coercion or fallback',()=>{
 for(const change of [s=>s.system.acBonus='2',s=>s.system.acBonus=undefined,s=>s.system.speedPenalty=Infinity,s=>s.system.grade=false,s=>s.system.runes=null,s=>s.system.runes.reinforcing=NaN,s=>s.system.specific=undefined,s=>s.system.specific=[],s=>s.system.specific={material:null},s=>s.system.specific={runes:null},s=>s.system.specific={integrated:[]},s=>s.system.traits.integrated={runes:null},s=>s.system.traits.integrated={runes:{property:[3]}},s=>s.system.traits.integrated={versatile:{selected:null}},s=>s.system.traits.integrated={versatile:false},s=>s.system.traits.otherTags=[null],s=>s.system.publication.remaster='true']){const input=source();change(input);assert.throws(()=>shieldFields(input),TypeError);}
});
test('no duplicate physical paths or source object leaks and prepared getters untouched',()=>{
 const input=source();input.system.traits.integrated={runes:{potency:0,striking:0,property:[]},versatile:{selected:'slashing'}};
 for(const key of ['usage','flags','description','rules','raised','broken','shieldBlock'])Object.defineProperty(input.system,key,{get(){throw new Error(key);}});
 Object.defineProperty(input.system.traits.integrated,'damageType',{get(){throw new Error('prepared damage');}});
 Object.defineProperty(input.system.traits.integrated.versatile,'options',{get(){throw new Error('prepared options');}});
 Object.defineProperty(input.system.traits.integrated.runes,'effects',{get(){throw new Error('prepared effects');}});
 const rows=[...physicalFields(input),...shieldFields(input)],paths=rows.map(r=>r.path);assert.equal(new Set(paths).size,paths.length);
 for(const r of shieldFields(input))if(r.value&&typeof r.value==='object')assert.equal(Object.keys(r.value).length,0);
 assert.ok(!shieldFields(input).some(r=>/usage|baseItem|equipped|effects|options|damageType|description|rules|flags/.test(r.path)));
});
