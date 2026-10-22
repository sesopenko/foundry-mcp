import test from 'node:test';
import assert from 'node:assert/strict';
import {armorFields} from '../../foundry-module/scripts/actorArmor.js';
import {physicalFields} from '../../foundry-module/scripts/actorPhysical.js';
const source=()=>({type:'armor',system:{category:'heavy',group:null,baseItem:'full-plate',acBonus:6,strength:4,dexCap:0,checkPenalty:-3,speedPenalty:-10,grade:null,runes:{potency:0,resilient:2,property:['fortification','future-rune']},specific:null,traits:{value:['bulwark','future-trait'],otherTags:[],rarity:'uncommon'},slug:null,publication:{title:'Source',authors:'Author',license:'ORC',remaster:true}}});
const row=(rows,path)=>rows.find(row=>row.path==='/system/'+path);
test('armor source retains zero, penalties and unknown codes without actor calculations',()=>{
 const input=source(),before=JSON.stringify(input),rows=armorFields(input);
 for(const [path,value]of [['category','heavy'],['group',null],['acBonus',6],['strength',4],['dexCap',0],['checkPenalty',-3],['speedPenalty',-10],['grade',null],['runes/potency',0],['runes/resilient',2],['runes/property/1','future-rune'],['traits/value/1','future-trait'],['slug',null],['publication/remaster',true]])assert.equal(row(rows,path).value,value);
 assert.ok(rows.every(r=>r.limitations.includes('source_only_no_actor_armor_calculation')));
 assert.equal(JSON.stringify(input),before);assert.equal(armorFields(null),null);assert.equal(armorFields({type:'shield'}),null);
});
test('specific baseline material and runes preserve distinct authored values',()=>{
 const input=source();input.system.specific={material:{type:'future-metal',grade:null},runes:{potency:3,resilient:0,property:[]}};
 const rows=armorFields(input);assert.equal(row(rows,'runes/potency').value,0);assert.equal(row(rows,'specific/runes/potency').value,3);
 assert.equal(row(rows,'specific/runes/resilient').value,0);assert.deepEqual(row(rows,'specific/runes/property').value,[]);
 assert.equal(row(rows,'specific/material/type').value,'future-metal');assert.equal(row(rows,'specific/material/grade').value,null);
});
test('missing, null, empty and zero source values remain distinct',()=>{
 const input=source();assert.equal(row(armorFields(input),'specific').value,null);
 input.system.specific={};assert.deepEqual(row(armorFields(input),'specific').value,{});
 delete input.system.specific;let missing=row(armorFields(input),'specific');assert.equal(missing.present,false);assert.equal(Object.hasOwn(missing,'value'),false);
 input.system.specific={material:{},runes:{}};let rows=armorFields(input);assert.deepEqual(row(rows,'specific/material').value,{});assert.deepEqual(row(rows,'specific/runes').value,{});
 input.system.runes={};assert.deepEqual(row(armorFields(input),'runes').value,{});
 delete input.system.runes;assert.equal(row(armorFields(input),'runes').present,false);
 input.system.strength=null;assert.equal(row(armorFields(input),'strength').value,null);input.system.strength=0;assert.equal(row(armorFields(input),'strength').value,0);
 delete input.system.strength;assert.equal(row(armorFields(input),'strength').present,false);
 input.system.traits.value=[];assert.deepEqual(row(armorFields(input),'traits/value').value,[]);
});
test('malformed selected leaves reject without defaults or coercion',()=>{
 for(const change of [s=>s.system.acBonus='6',s=>s.system.acBonus=undefined,s=>s.system.strength=Infinity,s=>s.system.group=false,s=>s.system.dexCap=NaN,s=>s.system.grade=0,s=>s.system.runes=null,s=>s.system.runes.potency=undefined,s=>s.system.runes.resilient='2',s=>s.system.runes.property=[null],s=>s.system.specific=undefined,s=>s.system.specific=[],s=>s.system.specific={material:null},s=>s.system.specific={runes:null},s=>s.system.specific={material:{type:9}},s=>s.system.traits.value=null,s=>s.system.traits.otherTags=[false],s=>s.system.publication.remaster='true']){const input=source();change(input);assert.throws(()=>armorFields(input),TypeError);}
});
test('shared physical paths stay unique and prepared or unrelated getters are untouched',()=>{
 const input=source();for(const key of ['usage','flags','description','rules','effects','ac','saves'])Object.defineProperty(input.system,key,{get(){throw new Error(key);}});
 Object.defineProperty(input.system.runes,'effects',{get(){throw new Error('prepared rune effects');}});Object.defineProperty(input.system.traits,'config',{get(){throw new Error('prepared trait config');}});
 const rows=[...physicalFields(input),...armorFields(input)],paths=rows.map(r=>r.path);assert.equal(new Set(paths).size,paths.length);
 assert.equal(row(rows,'baseItem').value,'full-plate');assert.ok(!armorFields(input).some(r=>/usage|baseItem|equipped|effects|config|description|rules|flags/.test(r.path)));
});
