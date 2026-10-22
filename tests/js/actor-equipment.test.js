import test from 'node:test';
import assert from 'node:assert/strict';
import {equipmentFields} from '../../foundry-module/scripts/actorEquipment.js';
import {physicalFields} from '../../foundry-module/scripts/actorPhysical.js';
const source=()=>({type:'equipment',system:{usage:{value:'worncloak'},equipped:{carryType:'worn',invested:false},subitems:[],traits:{value:['invested','magical','future-trait'],otherTags:['future-tag'],rarity:'uncommon'},slug:null,publication:{title:'Source',authors:'Author',license:'ORC',remaster:true}}});
const row=(rows,path)=>rows.find(r=>r.path==='/system/'+path);
test('equipment source preserves exact traits and metadata without asserting active benefits',()=>{
 const input=source(),before=JSON.stringify(input),rows=equipmentFields(input);
 for(const [path,value]of [['traits/value/0','invested'],['traits/value/2','future-trait'],['traits/otherTags/0','future-tag'],['traits/rarity','uncommon'],['slug',null],['publication/title','Source'],['publication/remaster',true]])assert.equal(row(rows,path).value,value);
 assert.equal(JSON.stringify(input),before);assert.ok(rows.every(r=>r.limitations.includes('source_only_no_equipment_benefit_application')));
 assert.equal(equipmentFields({type:'consumable'}),null);assert.equal(equipmentFields(null),null);
});
test('missing and empty trait arrays remain distinct without fabricated metadata defaults',()=>{
 const input=source();input.system.traits.value=[];input.system.traits.otherTags=[];
 assert.deepEqual(row(equipmentFields(input),'traits/value').value,[]);assert.deepEqual(row(equipmentFields(input),'traits/otherTags').value,[]);
 delete input.system.traits.value;delete input.system.slug;delete input.system.publication;
 for(const path of ['traits/value','slug','publication/title','publication/remaster']){const missing=row(equipmentFields(input),path);assert.equal(missing.present,false);assert.equal(Object.hasOwn(missing,'value'),false);}
});
test('malformed selected equipment fields reject without coercion',()=>{
 for(const change of [s=>s.system.traits.value=undefined,s=>s.system.traits.value=null,s=>s.system.traits.value={},s=>s.system.traits.value=[null],s=>s.system.traits.otherTags=[false],s=>s.system.traits.rarity=3,s=>s.system.slug=undefined,s=>s.system.slug=3,s=>s.system.publication.title=null,s=>s.system.publication.remaster='true']){const input=source();change(input);assert.throws(()=>equipmentFields(input),TypeError);}
});
test('shared physical usage, uninvested state and attachments stay unique while prose and rules remain untouched',()=>{
 const input=source();for(const key of ['flags','description','rules','activation','frequency','apex','abilities'])Object.defineProperty(input.system,key,{get(){throw new Error(key);}});
 const rows=[...physicalFields(input),...equipmentFields(input)],paths=rows.map(r=>r.path);assert.equal(new Set(paths).size,paths.length);
 assert.equal(row(rows,'usage/value').value,'worncloak');assert.equal(row(rows,'equipped/invested').value,false);assert.deepEqual(row(rows,'subitems').value,[]);
 assert.ok(!equipmentFields(input).some(r=>/usage|equipped|subitems|description|rules|activation|frequency|apex|abilities/.test(r.path)));
});
