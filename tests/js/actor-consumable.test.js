import test from 'node:test';
import assert from 'node:assert/strict';
import {consumableFields} from '../../foundry-module/scripts/actorConsumable.js';
import {physicalFields} from '../../foundry-module/scripts/actorPhysical.js';
const source=()=>({type:'consumable',system:{category:'potion',quantity:3,usage:{value:'held-in-one-hand'},uses:{value:0,max:2,autoDestroy:false},damage:{formula:'2d8+5',type:'vitality',kind:'healing'},spell:null,traits:{value:['magical','future-trait'],otherTags:[],rarity:'common'},slug:null,publication:{title:'Source',authors:'Author',license:'ORC',remaster:true}}});
const row=(rows,path)=>rows.find(r=>r.path==='/system/'+path);
test('consumable retains uses separately from quantity and preserves healing kind without rolling',()=>{
 const input=source(),before=JSON.stringify(input),rows=consumableFields(input);
 for(const [path,value]of [['category','potion'],['uses/value',0],['uses/max',2],['uses/autoDestroy',false],['damage/formula','2d8+5'],['damage/type','vitality'],['damage/kind','healing'],['spell',null],['traits/value/1','future-trait'],['slug',null]])assert.equal(row(rows,path).value,value);
 assert.equal(JSON.stringify(input),before);assert.ok(rows.every(r=>r.limitations.includes('source_only_no_consumable_use_or_spell_application')));
 const combined=[...physicalFields(input),...rows];assert.equal(new Set(combined.map(r=>r.path)).size,combined.length);assert.equal(row(combined,'quantity').value,3);
 assert.equal(consumableFields({type:'spell'}),null);assert.equal(consumableFields(null),null);
});
test('contained spell selects local identity and authored rank without traversing mechanics or fabricating UUIDs',()=>{
 const input=source();input.system.spell={_id:'local-spell',name:'Contained Spell',type:'spell',system:{level:{value:4},location:{heightenedLevel:7}} };
 for(const key of ['damage','heightening','rules','description'])Object.defineProperty(input.system.spell.system,key,{get(){throw new Error(key);}});
 Object.defineProperty(input.system.spell,'uuid',{get(){throw new Error('uuid');}});
 const rows=consumableFields(input);
 for(const [path,value]of [['spell/_id','local-spell'],['spell/name','Contained Spell'],['spell/type','spell'],['spell/system/level/value',4]])assert.equal(row(rows,path).value,value);
 assert.equal(rows.some(r=>r.path==='/system/spell'),false);assert.equal(rows.some(r=>/uuid|location|heightening/.test(r.path)),false);
});
test('null, absent and empty consumable fields remain distinct',()=>{
 const input=source();input.system.damage=null;assert.equal(row(consumableFields(input),'damage').value,null);
 delete input.system.damage;delete input.system.spell;delete input.system.uses;delete input.system.publication;
 const rows=consumableFields(input);
 for(const path of ['damage','spell','uses/value','publication/title']){assert.equal(row(rows,path).present,false);assert.equal(Object.hasOwn(row(rows,path),'value'),false);}
 assert.deepEqual(row(rows,'traits/otherTags').value,[]);
 input.system.spell={};const empty=consumableFields(input);assert.equal(row(empty,'spell/_id').present,false);assert.equal(row(empty,'spell/system/level/value').present,false);
});
test('malformed selected consumable source rejects without coercion or nonfinite numbers',()=>{
 for(const change of [s=>s.system.category=null,s=>s.system.uses.value=Infinity,s=>s.system.uses.max='2',s=>s.system.uses.autoDestroy=1,s=>s.system.damage=undefined,s=>s.system.damage=[],s=>s.system.damage.kind=null,s=>s.system.spell=undefined,s=>s.system.spell=false,s=>s.system.spell={type:'weapon'},s=>s.system.spell={system:{level:{value:NaN}}},s=>s.system.traits.value=[null],s=>s.system.slug=undefined,s=>s.system.publication.remaster='true']){const input=source();change(input);assert.throws(()=>consumableFields(input),TypeError);}
});
test('consumable source selection never reads rules, descriptive activation text or derived state',()=>{
 const input=source();for(const key of ['rules','description','activation','frequency','prepared','subitems'])Object.defineProperty(input.system,key,{get(){throw new Error(key);}});
 assert.ok(consumableFields(input).length>0);
});
