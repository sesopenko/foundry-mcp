import test from 'node:test';
import assert from 'node:assert/strict';
import {loreFields} from '../../foundry-module/scripts/actorLore.js';
const input=()=>({type:'lore',name:'Sailing Lore',system:{mod:{value:9},proficient:{value:2},slug:null,traits:{otherTags:['custom','custom']},variants:{'a/b~c':{label:'Recall 😀',options:'action:recall-knowledge'}},publication:{title:'Player Core',authors:'Paizo',license:'ORC',remaster:true},level:{value:20},ability:{value:'int'},rules:[{key:'SECRET'}],description:{value:'SECRET'}}});
const row=(rows,path)=>rows.find(value=>value.path===path);

test('Lore preserves authored modifier and rank without inventing an owner or total',()=>{
 const source=input(),before=JSON.stringify(source),rows=loreFields(source);
 for(const [path,concept,value]of [['/system/mod/value','stored_lore_modifier',9],['/system/proficient/value','stored_lore_proficiency_rank',2]]) {
  assert.equal(row(rows,path).concept,concept);assert.equal(row(rows,path).value,value);
  assert.deepEqual(row(rows,path).limitations,['owner_context_required_not_effective_total']);
 }
 assert.deepEqual(row(rows,'/system/proficient/value').mapped_value,{rank:2,label:'Expert'});
 assert.equal(JSON.stringify(source),before);
 assert.ok(!rows.some(value=>/level|ability|rules|description/.test(value.path)));
 assert.ok(!JSON.stringify(rows).includes('SECRET'));
 assert.equal(loreFields({type:'feat'}),null);assert.equal(loreFields(null),null);
});

test('actual owner type selects authored NPC versus character rank concepts without totals',()=>{
 const source=input();
 assert.equal(row(loreFields(source,'npc'),'/system/mod/value').concept,'npc_lore_authored_modifier');
 const character=row(loreFields(source,'character'),'/system/proficient/value');
 assert.equal(character.concept,'character_lore_proficiency_rank');
 assert.deepEqual(character.mapped_value,{rank:2,label:'Expert'});
 assert.ok(character.limitations.includes('proficiency_rank_not_bonus_or_effective_total'));
});

test('variant keys use exact escaped source pointers and primitive leaves only',()=>{
 const rows=loreFields(input());
 assert.equal(row(rows,'/system/variants/a~1b~0c/label').value,'Recall 😀');
 assert.equal(row(rows,'/system/variants/a~1b~0c/options').value,'action:recall-knowledge');
 assert.deepEqual(rows.filter(value=>value.path.startsWith('/system/traits/otherTags/')).map(value=>value.value),['custom','custom']);
 assert.ok(rows.every(value=>!value.present||value.value===null||typeof value.value!=='object'));
});

test('missing, null, empty and zero retain distinct meanings without defaults',()=>{
 const source=input();source.system.mod.value=0;source.system.proficient.value=0;source.system.variants={};source.system.traits.otherTags=[];
 let rows=loreFields(source);
 assert.equal(row(rows,'/system/mod/value').value,0);assert.equal(row(rows,'/system/proficient/value').value,0);
 assert.deepEqual(row(rows,'/system/variants').value,{});assert.deepEqual(row(rows,'/system/traits/otherTags').value,[]);
 assert.equal(row(rows,'/system/slug').value,null);
 delete source.system.mod;delete source.system.proficient;source.system.variants=undefined;delete source.system.traits.otherTags;delete source.system.slug;
 rows=loreFields(source);
 for(const path of ['/system/mod/value','/system/proficient/value','/system/variants','/system/traits/otherTags','/system/slug']) {
  assert.equal(row(rows,path).present,false);assert.ok(!Object.hasOwn(row(rows,path),'value'));
 }
});

test('malformed selected values cannot leak objects or produce guessed mechanics',()=>{
 for(const change of [
  source=>source.system.mod.value=NaN,source=>source.system.mod.value={},source=>source.system.proficient.value=1.5,
  source=>source.system.proficient.value=5,source=>source.system.proficient.value=-1,source=>source.system.proficient.value=null,
  source=>source.system.variants=null,source=>source.system.variants=[],source=>source.system.variants={x:null},
  source=>source.system.variants={x:{label:{secret:true},options:'x'}},source=>source.system.traits.otherTags=[{}],
  source=>source.system.publication.title={secret:true}
 ]) {const source=input();change(source);assert.throws(()=>loreFields(source),TypeError);}
});
