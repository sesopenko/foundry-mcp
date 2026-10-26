import test from 'node:test';
import assert from 'node:assert/strict';
import {characterAbilityRecords} from '../../foundry-module/scripts/actorCharacterAbilities.js';

function fixture() {
 globalThis.game={user:{isGM:true}};
 const actor={documentName:'Actor',type:'character',uuid:'Actor.a',id:'a',name:'Owner',items:new Map(),testUserPermission:()=>true};
 const add=(id,type,name='Ability')=>{
  const source={name,type,system:{category:'classfeature'}};
  const item={documentName:'Item',id,uuid:actor.uuid+'.Item.'+id,type,name:'Prepared label',parent:actor,folder:null,compendium:null,testUserPermission:()=>true,toObject:basis=>{assert.equal(basis,true);return source;}};
  actor.items.set(id,item);return {source,item};
 };
 return {actor,target:{document:actor,token:null},add};
}

test('actual actions and all feat categories retain source identity and complete raw names',()=>{
 const f=fixture(),first=f.add('z','action','😀'.repeat(257)),second=f.add('a','feat','Alpha');
 second.source.system.category='classfeature';f.add('b','feat','Alpha');f.add('excluded','equipment');
 const before=JSON.stringify([first.source,second.source]),result=characterAbilityRecords(f.target);
 assert.deepEqual(result.reasons,['other_abilities_not_enumerated']);assert.equal(result.records.length,3);
 assert.deepEqual(result.records.slice(0,2).map(r=>r.mapped.value.target_uuid),['Actor.a.Item.a','Actor.a.Item.b']);
 const row=result.records[2];assert.equal([...row.raw[0].value].length,257);assert.equal([...row.mapped.value.name].length,256);assert.equal(row.mapped.value.name_truncated,true);
 assert.equal(row.mapped.value.type,'action');assert.equal(row.mapped.concept,'character_ability_item');
 assert.deepEqual(row.provenance,{contributors:row.raw.map(({document_uuid,path,basis})=>({document_uuid,path,basis})),mapping:'pf2e.character.ability-reference.v1',limitations:['owned_item_reference_not_complete_or_active_ability']});
 assert.equal(row.raw[0].basis,'source');assert.equal(row.raw[1].path,'/type');
 assert.equal(JSON.stringify([first.source,second.source]),before);
});

test('denied actual Items never expose source or labels and collapse into one marker',()=>{
 const f=fixture();
 for(const id of ['a','b']){
  const {item}=f.add(id,'feat');item.testUserPermission=()=>false;
  item.toObject=()=>{throw Error('Denied source read');};
  Object.defineProperty(item,'name',{get(){throw Error('Denied label read');}});
 }
 const result=characterAbilityRecords(f.target);
 assert.equal(result.records.length,1);const row=result.records[0];
 assert.equal(row.key,'abilities:items:denied');assert.deepEqual(row.raw,[]);assert.deepEqual(row.provenance.contributors,[]);
 assert.deepEqual(row.mapped.value,{status:'denied',target_uuid:null});assert.ok(result.reasons.includes('ability_items_denied'));
 assert.ok(!JSON.stringify(result).includes('.Item.'));
});

test('actual parent and exact membership are required, not a matching local ID',()=>{
 for(const change of [f=>f.item.parent={},f=>f.actor.items.set('other',f.item),f=>f.actor.items={size:1,values:()=>[f.item].values(),get:()=>({...f.item})}]){
  const f=fixture(),{item}=f.add('a','action');change({...f,item});
  assert.throws(()=>characterAbilityRecords(f.target),TypeError);
 }
});

test('source name/type accessors reject without invocation; nonplain own containers work',()=>{
 for(const key of ['name','type']){
  const f=fixture(),{source}=f.add('a','feat');let calls=0;
  Object.defineProperty(source,key,{get(){calls++;return 'forbidden';}});
  assert.throws(()=>characterAbilityRecords(f.target),TypeError);assert.equal(calls,0);
 }
 const f=fixture(),{item}=f.add('a','action');
 class Source {constructor(){this.name='Own source';this.type='action';}}
 item.toObject=()=>new Source();assert.equal(characterAbilityRecords(f.target).records[0].mapped.value.name,'Own source');
});

test('token context is retained; noncharacter and malformed source types reject',()=>{
 const f=fixture();f.target.token={uuid:'Scene.s.Token.t',parent:{uuid:'Scene.s',name:'Scene'},name:'Token',isLinked:false,baseActor:null};
 f.add('a','action');assert.equal(characterAbilityRecords(f.target).records[0].mapped.value.token_uuid,'Scene.s.Token.t');
 f.actor.type='npc';assert.throws(()=>characterAbilityRecords(f.target),TypeError);
 const g=fixture(),{source}=g.add('a','feat');source.type='action';assert.throws(()=>characterAbilityRecords(g.target),TypeError);
});

test('empty collection remains partial and own text/item bounds reject',()=>{
 const f=fixture();assert.deepEqual(characterAbilityRecords(f.target),{records:[],reasons:['other_abilities_not_enumerated']});
 const {source}=f.add('a','action');source.name='x'.repeat(6001);assert.throws(()=>characterAbilityRecords(f.target),/6000/);
 source.name='x'.repeat(6000);assert.equal(characterAbilityRecords(f.target).records[0].raw[0].value.length,6000);
 f.actor.items={size:12001};assert.throws(()=>characterAbilityRecords(f.target),/12000/);
});

test('source activation/category/rules and unrelated Item types are never evaluated',()=>{
 const f=fixture(),{source}=f.add('a','feat');
 for(const leaf of ['category','rules','actionType','frequency'])Object.defineProperty(source.system,leaf,{get(){throw Error('Effective or classification field unselected');}});
 const unrelated=f.add('b','weapon');unrelated.item.toObject=()=>{throw Error('Unrelated Item source');};
 assert.equal(characterAbilityRecords(f.target).records.length,1);
});
