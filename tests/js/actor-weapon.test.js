import test from 'node:test';
import assert from 'node:assert/strict';
import {weaponFields} from '../../foundry-module/scripts/actorWeapon.js';
import {physicalFields} from '../../foundry-module/scripts/actorPhysical.js';
const source=()=>({type:'weapon',system:{category:'martial',group:'sword',baseItem:'longsword',damage:{dice:1,die:'d8',damageType:'slashing',modifier:0,persistent:{number:2,faces:null,type:'bleed'}},range:null,maxRange:120,reload:{value:'1'},expend:0,selectedAmmoId:'ammo-local',bonus:{value:2},splashDamage:{value:0},attribute:null,grade:null,graspingAppendage:false,usage:{value:'held-in-one-hand',canBeAmmo:false},ammo:{builtIn:false,baseType:'arrows',capacity:null},runes:{potency:1,striking:2,property:['unknownRune','flaming']},meleeUsage:{damage:{type:'piercing',die:'d6'},group:'spear',traits:[],traitToggles:{modular:null,versatile:'fire'}},traits:{toggles:{doubleBarrel:{selected:false},modular:{selected:1},versatile:{selected:null}}},specific:{material:{type:'silver',grade:'standard'},runes:{potency:2,striking:1,property:[]}}}});
const row=(rows,path)=>rows.find(row=>row.path===path);
test('weapon source retains primitive damage/ranges/runes/ammunition without calculating totals',()=>{
 const input=source(),before=JSON.stringify(input),rows=weaponFields(input);
 for(const [path,value]of [['damage/dice',1],['damage/modifier',0],['damage/persistent/faces',null],['maxRange',120],['expend',0],['reload/value','1'],['selectedAmmoId','ammo-local'],['runes/property/0','unknownRune'],['traits/toggles/doubleBarrel/selected',false],['specific/material/type','silver']])assert.equal(row(rows,'/system/'+path).value,value);
 assert.equal(JSON.stringify(input),before);assert.ok(rows.every(r=>r.limitations.includes('source_only_no_effective_strike_calculation')));
 assert.equal(weaponFields({type:'melee'}),null);assert.equal(weaponFields(null),null);
});
test('missing, schema-optional undefined, null, empty arrays and empty objects remain distinct',()=>{
 const input=source();input.system.maxRange=undefined;input.system.meleeUsage=undefined;input.system.traits.toggles={};input.system.ammo=null;input.system.damage.persistent=null;
 let rows=weaponFields(input);
 assert.equal(row(rows,'/system/maxRange').present,false);assert.equal(row(rows,'/system/meleeUsage').present,false);
 assert.deepEqual(row(rows,'/system/traits/toggles').value,{});assert.equal(row(rows,'/system/ammo').value,null);assert.equal(row(rows,'/system/damage/persistent').value,null);
 assert.deepEqual(row(rows,'/system/specific/runes/property').value,[]);
 delete input.system.specific;rows=weaponFields(input);assert.equal(row(rows,'/system/specific').present,false);
 input.system.specific={};assert.deepEqual(row(weaponFields(input),'/system/specific').value,{});
});
test('all optional undefined selectors are absent while required undefined and malformed selected types reject',()=>{
 for(const path of ['maxRange','expend','attribute','graspingAppendage','meleeUsage']){const input=source();input.system[path]=undefined;assert.equal(row(weaponFields(input),'/system/'+path).present,false);}
 const input=source();input.system.usage.canBeAmmo=undefined;input.system.traits.toggles.modular=undefined;input.system.meleeUsage.traits=undefined;input.system.meleeUsage.traitToggles=undefined;
 let rows=weaponFields(input);for(const path of ['usage/canBeAmmo','traits/toggles/modular','meleeUsage/traits','meleeUsage/traitToggles'])assert.equal(row(rows,'/system/'+path).present,false);
 for(const change of [s=>s.system.category=undefined,s=>s.system.range=NaN,s=>s.system.damage.dice='1',s=>s.system.damage.persistent=[],s=>s.system.ammo.capacity='2',s=>s.system.runes.property=[2],s=>s.system.traits.toggles.doubleBarrel=null,s=>s.system.meleeUsage=null,s=>s.system.specific.runes=null,s=>s.system.usage.canBeAmmo=null]){const input=source();change(input);assert.throws(()=>weaponFields(input),TypeError);}
});
test('shared physical fields never duplicate weapon paths and forbidden prepared siblings are untouched',()=>{
 const input=source();for(const key of ['flags','description','rules','actions'])Object.defineProperty(input.system,key,{get(){throw new Error(key);}});
 Object.defineProperty(input.system.runes,'effects',{get(){throw new Error('prepared rune effects');}});
 Object.defineProperty(input.system.reload,'label',{get(){throw new Error('prepared reload label');}});
 const rows=[...physicalFields(input),...weaponFields(input)];const paths=rows.map(r=>r.path);assert.equal(new Set(paths).size,paths.length);
 assert.equal(row(rows,'/system/baseItem').value,'longsword');assert.ok(!weaponFields(input).some(row=>/effects|label|flags|description|rules|actions/.test(row.path)));
});
test('unknown code strings remain source exact across weapon modes and rune baselines',()=>{
 const input=source();input.system.category='future-category';input.system.reload.value='future-reload';input.system.grade='future-grade';input.system.damage.damageType='future-damage';input.system.traits.toggles.modular=null;
 const rows=weaponFields(input);for(const [path,value]of [['category','future-category'],['reload/value','future-reload'],['grade','future-grade'],['damage/damageType','future-damage']])assert.equal(row(rows,'/system/'+path).value,value);
 assert.equal(row(rows,'/system/traits/toggles/modular').value,null);
});
