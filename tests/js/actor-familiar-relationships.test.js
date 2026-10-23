import test from 'node:test';
import assert from 'node:assert/strict';
import {familiarMasterRelationship,familiarAbilityRecords} from '../../foundry-module/scripts/actorFamiliarRelationships.js';

function setup(){
 const actors=new Map();globalThis.game={user:{isGM:true},actors};
 globalThis.foundry={utils:{fromUuid:async uuid=>[...actors.values()].find(actor=>actor.uuid===uuid)}};
 const familiar={documentName:'Actor',type:'familiar',id:'f',uuid:'Actor.f',items:new Map()};
 const target={document:familiar,identity:{uuid:familiar.uuid},token:null};
 return {target,actors};
}
function master(overrides={}){return {documentName:'Actor',type:'character',id:'m',uuid:'Actor.m',name:'Master',testUserPermission:()=>true,...overrides};}
function ability(target,id,traits=[],extra={}){
 const source={name:'Ability',type:'action',system:{traits:traits===undefined?{}:{value:traits}}};
 const item={id,uuid:`Actor.f.Item.${id}`,documentName:'Item',type:'action',name:'Ability',parent:target.document,testUserPermission:()=>true,toObject:flag=>{assert.equal(flag,true);return source;},...extra};
 target.document.items.set(id,item);return {source,item};
}
const field=value=>({path:'/system/master/id',present:true,value});

test('master resolves actual world character with exact source evidence and no token inheritance',async()=>{
 const {target,actors}=setup();target.token={uuid:'Scene.s.Token.t'};actors.set('m',master());
 const result=await familiarMasterRelationship(target,field('m'));
 assert.deepEqual(result.reasons,[]);
 assert.equal(result.record.key,'identity:familiar_master');
 assert.deepEqual(result.record.raw,[{document_uuid:'Actor.f',path:'/system/master/id',present:true,value:'m',basis:'source'}]);
 assert.deepEqual(result.record.mapped.value,{status:'resolved',target_uuid:'Actor.m',document_name:'Actor',type:'character',name:'Master',name_truncated:false,next_call:{tool:'read_actor',arguments:{actor_uuid:'Actor.m'}}});
});
test('master distinguishes absent, null, empty, dangling, denied, unsupported and mismatches',async()=>{
 const {target,actors}=setup();
 for(const [descriptor,status] of [[{path:'/system/master/id',present:false},'missing'],[field(null),'unassociated'],[field(''),'missing'],[field('gone'),'missing']])assert.equal((await familiarMasterRelationship(target,descriptor)).record.mapped.value.status,status);
 for(const [candidate,status] of [[master({testUserPermission:()=>false,name:{toString(){throw Error('leak');}}}),'denied'],[master({type:'npc'}),'unsupported'],[master({id:'wrong'}),'unverified'],[master({uuid:'Compendium.x.y.Actor.m'}),'unverified'],[master({parent:{}}),'unverified']]){
  actors.set('m',candidate);const result=await familiarMasterRelationship(target,field('m'));
  assert.deepEqual(result.record.mapped.value,{status,target_uuid:null});assert.deepEqual(result.reasons,['familiar_master_'+status]);
 }
});
test('lookup failures preserve stored source claim without claiming target identity',async()=>{
 const {target}=setup();game.actors.get=()=>{throw Error('offline');};
 const result=await familiarMasterRelationship(target,field('m'));
 assert.deepEqual(result.record.mapped.value,{status:'unverified',target_uuid:null});assert.equal(result.record.raw[0].value,'m');
});
test('abilities retain complete source traits, exact identities, duplicates once and token context',()=>{
 const {target}=setup();target.token={uuid:'Scene.s.Token.t',parent:{uuid:'Scene.s',name:'Scene'},baseActor:null,isLinked:false,name:'Token'};
 const {source,item}=ability(target,'a',['familiar','master','concentrate']);target.document.items.set('duplicate',item);
 const before=structuredClone(source),result=familiarAbilityRecords(target);
 assert.equal(result.records.length,1);assert.deepEqual(source,before);
 const row=result.records[0];assert.deepEqual(row.raw.map(value=>value.path),['/name','/type','/system/traits/value/0','/system/traits/value/1','/system/traits/value/2']);
 assert.equal(row.mapped.value.ability_kind,'unclassified');assert.equal(row.mapped.value.token_uuid,'Scene.s.Token.t');assert.deepEqual(result.reasons,['other_abilities_pending']);
});
test('empty or absent traits remain evidence and empty abilities are partial',()=>{
 const {target}=setup();assert.deepEqual(familiarAbilityRecords(target),{records:[],reasons:['other_abilities_pending']});
 const {source}=ability(target,'a',[]);let result=familiarAbilityRecords(target);assert.deepEqual(result.records[0].raw[2].value,[]);
 delete source.system.traits.value;result=familiarAbilityRecords(target);assert.equal(result.records[0].raw[2].present,false);
});
test('denied owned Items are never serialized or named and only aggregate scope is exposed',()=>{
 const {target}=setup();const {item}=ability(target,'secret',[],{testUserPermission:()=>false,toObject(){throw Error('must not read');}});Object.defineProperty(item,'name',{get(){throw Error('must not name');}});
 const result=familiarAbilityRecords(target);assert.equal(result.records.length,1);assert.equal(result.records[0].key,'abilities:familiar:denied');assert.deepEqual(result.records[0].raw,[]);assert.deepEqual(result.reasons,['other_abilities_pending','related_items_denied']);
});
test('denied non-action Items do not create an abilities denial marker',()=>{
 const {target}=setup();ability(target,'physical',[],{type:'equipment',testUserPermission:()=>false,toObject(){throw Error('must not read');}});
 assert.deepEqual(familiarAbilityRecords(target),{records:[],reasons:['other_abilities_pending']});
});
test('invalid and excessive traits fail actionably instead of truncating',()=>{
 const {target}=setup(),{source}=ability(target,'a',Array(201).fill('trait'));
 assert.throws(()=>familiarAbilityRecords(target),error=>error.rpcError.code==='ReadFailed'&&error.rpcError.recovery.includes('read_item'));
 source.system.traits.value=['valid',null];assert.throws(()=>familiarAbilityRecords(target),/traits/);
 source.system.traits.value=Array(2);assert.throws(()=>familiarAbilityRecords(target),/traits/);
});
test('non-familiar boundary rejects interpretation',()=>{
 const {target}=setup();target.document.type='npc';assert.throws(()=>familiarAbilityRecords(target),/familiar/);
});
