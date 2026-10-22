import test from 'node:test';
import assert from 'node:assert/strict';
import {ammoFields} from '../../foundry-module/scripts/actorAmmo.js';
import {physicalFields} from '../../foundry-module/scripts/actorPhysical.js';
const source=()=>({type:'ammo',system:{uses:{value:0,max:10,autoDestroy:false},craftableAs:['arrows','future-ammo'],baseItem:null,quantity:20,traits:{value:['magical','future-trait'],otherTags:[],rarity:'uncommon'},slug:null,publication:{title:'Source',authors:'Author',license:'ORC',remaster:true}}});
const row=(rows,path)=>rows.find(row=>row.path==='/system/'+path);
test('ammo source preserves uses separately from quantity and category codes without executing effects',()=>{
 const input=source(),before=JSON.stringify(input),rows=ammoFields(input);
 for(const [path,value]of [['uses/value',0],['uses/max',10],['uses/autoDestroy',false],['craftableAs/1','future-ammo'],['traits/value/1','future-trait'],['traits/rarity','uncommon'],['slug',null],['publication/remaster',true]])assert.equal(row(rows,path).value,value);
 assert.equal(JSON.stringify(input),before);assert.ok(rows.every(r=>r.limitations.includes('source_only_no_ammunition_consumption_or_compatibility')));
 assert.equal(ammoFields({type:'consumable'}),null);assert.equal(ammoFields(null),null);
});
test('missing, null, empty and populated craftableAs retain different source meanings',()=>{
 const input=source();input.system.craftableAs=null;assert.equal(row(ammoFields(input),'craftableAs').value,null);
 input.system.craftableAs=[];assert.deepEqual(row(ammoFields(input),'craftableAs').value,[]);
 delete input.system.craftableAs;const missing=row(ammoFields(input),'craftableAs');assert.equal(missing.present,false);assert.equal(Object.hasOwn(missing,'value'),false);
 delete input.system.uses;const rows=ammoFields(input);assert.equal(row(rows,'uses/value').present,false);assert.equal(row(rows,'uses/max').present,false);
 input.system.traits.value=[];assert.deepEqual(row(ammoFields(input),'traits/value').value,[]);
});
test('required undefined, malformed arrays and nonfinite numeric values reject without coercion',()=>{
 for(const change of [s=>s.system.uses.value=undefined,s=>s.system.uses.value='0',s=>s.system.uses.max=Infinity,s=>s.system.uses.autoDestroy=0,s=>s.system.craftableAs=undefined,s=>s.system.craftableAs={},s=>s.system.craftableAs=[null],s=>s.system.traits.value=null,s=>s.system.traits.otherTags=[false],s=>s.system.slug=3,s=>s.system.publication.remaster='true']){const input=source();change(input);assert.throws(()=>ammoFields(input),TypeError);}
});
test('physical selector supplies unique baseItem and quantity paths; prepared and unrelated getters remain untouched',()=>{
 const input=source();for(const key of ['flags','description','rules','damage','category','effects'])Object.defineProperty(input.system,key,{get(){throw new Error(key);}});
 Object.defineProperty(input.system.uses,'remaining',{get(){throw new Error('prepared remaining uses');}});
 const rows=[...physicalFields(input),...ammoFields(input)],paths=rows.map(r=>r.path);assert.equal(new Set(paths).size,paths.length);
 assert.equal(row(rows,'quantity').value,20);assert.equal(row(rows,'baseItem').value,null);
 assert.ok(!ammoFields(input).some(r=>/quantity|baseItem|effects|damage|remaining|flags|description|rules/.test(r.path)));
});
