import test from 'node:test';
import assert from 'node:assert/strict';
import {actorBuildRecords} from '../../foundry-module/scripts/actorBuild.js';
function fixture(synthetic=false){
 globalThis.game={user:{isGM:true}};
 const actor={documentName:'Actor',type:'character',id:'a',uuid:synthetic?'Scene.s.Token.t.Actor.a':'Actor.a',items:new Map()};
 const target={document:actor,...(synthetic?{token:{uuid:'Scene.s.Token.t',parent:{uuid:'Scene.s'},isLinked:false}}:{})};
 const add=(id,type='feat',system={},flags={})=>{const source={type,name:id,system,flags};let reads=0;const item={id,type,name:'Prepared '+id,uuid:actor.uuid+'.Item.'+id,documentName:'Item',parent:actor,testUserPermission:()=>true,toObject:()=>{reads++;return structuredClone(source);}};actor.items.set(id,item);return {item,source,get reads(){return reads;}};};
 return {actor,target,add};
}
const rows=(r,c)=>r.records.filter(row=>row.mapped.concept===c);
test('all seven actual contributor types occur once; offered definitions never hydrate',()=>{
 const f=fixture();for(const type of ['ancestry','heritage','background','class','deity','feat','lore'])f.add(type,type);
 const r=actorBuildRecords(f.target);assert.equal(rows(r,'build_item').length,7);assert.equal(new Set(r.records.map(row=>row.key)).size,r.records.length);assert.deepEqual(r.reasons,[]);
 for(const row of r.records){assert.equal(row.section,'build');assert.deepEqual(row.provenance.contributors,row.raw.map(({document_uuid,path,basis})=>({document_uuid,path,basis})));if(row.kind==='field')assert.equal(row.raw[0].path,'/type');}
});
test('matching outgoing claims retain inverse evidence and shared identity without duplication',()=>{
 const f=fixture(true),a=f.add('a','background',{}, {pf2e:{itemGrants:{'a/b~c':{id:'benefit'}}}}),b=f.add('b','class',{}, {pf2e:{itemGrants:{feature:{id:'benefit'}}}}),benefit=f.add('benefit','lore',{}, {pf2e:{grantedBy:{id:'a'}}});
 const r=actorBuildRecords(f.target),claims=rows(r,'build_grant_claim');assert.equal(claims.length,2);assert.deepEqual(claims.map(row=>row.mapped.value.reciprocity),['agree','disagree']);assert.equal(claims[0].raw[1].path,'/flags/pf2e/itemGrants/a~1b~0c/id');assert.equal(claims[0].raw[2].document_uuid,benefit.item.uuid);assert.equal(claims[0].raw[2].path,'/flags/pf2e/grantedBy/id');
 assert.equal(rows(r,'build_item').filter(row=>row.mapped.value.target_uuid===benefit.item.uuid).length,1);assert.equal(rows(r,'build_granted_by_claim')[0].mapped.value.reciprocity,'not_evaluated');for(const row of rows(r,'build_item'))assert.equal(row.mapped.value.token_uuid,f.target.token.uuid);assert.deepEqual([a.reads,b.reads,benefit.reads],[1,1,1]);
});
test('grant targets outside contributor types retain identity only and absence stays exact',()=>{
 const f=fixture(),donor=f.add('donor','feat',{}, {pf2e:{itemGrants:{x:{id:'weapon'}}}}),weapon=f.add('weapon','weapon');weapon.source.name='😀'.repeat(257);
 const r=actorBuildRecords(f.target),claim=rows(r,'build_grant_claim')[0];assert.equal(claim.mapped.value.reciprocity,'absent');assert.equal(claim.raw[2].present,false);assert.equal(claim.raw[2].path,'/flags/pf2e/grantedBy');assert.equal(claim.mapped.value.name,'😀'.repeat(256));assert.equal(claim.mapped.value.name_truncated,true);assert.equal(rows(r,'build_item').length,2);assert.ok(!r.records.some(row=>row.kind==='field'&&row.raw[0].document_uuid===weapon.item.uuid));assert.equal(donor.reads,1);assert.equal(weapon.reads,1);
});
test('missing denied unsupported targets and denied contributor scope preserve privacy',()=>{
 const f=fixture();f.add('donor','feat',{}, {pf2e:{itemGrants:{a:{id:'gone'},b:{id:'hidden'},c:{id:'poison'}}}});const hidden=f.add('hidden','feat');hidden.item.testUserPermission=()=>false;hidden.item.toObject=()=>{throw Error('secret');};f.add('poison','affliction');
 const r=actorBuildRecords(f.target);assert.deepEqual(rows(r,'build_grant_claim').map(row=>row.mapped.value.status),['missing','denied','unsupported']);assert.ok(rows(r,'build_grant_claim').every(row=>row.raw.length===2&&row.mapped.value.target_uuid===null&&row.mapped.value.reciprocity==='not_evaluated'));assert.ok(!r.records.some(row=>row.raw.some(field=>field.document_uuid===hidden.item.uuid)));assert.deepEqual(rows(r,'build_scope')[0].raw,[]);assert.deepEqual(r.reasons,['build_grant_target_denied','build_grant_target_missing','build_grant_target_unsupported','build_items_denied']);
});
test('stored selections are source only; unsupported values make view partial',()=>{
 const f=fixture();f.add('feat','feat',{}, {pf2e:{rulesSelections:{one:'choice',two:2,private:{uuid:'Actor.secret'}}}});const r=actorBuildRecords(f.target);assert.equal(rows(r,'feat_recorded_selection').length,2);assert.deepEqual(r.reasons,['unsupported_selection_values']);assert.ok(!JSON.stringify(r).includes('Actor.secret'));assert.equal(rows(r,'build_item').length,1);
});
test('empty scope, actor boundary, malformed source and owner bound fail explicitly',()=>{
 const f=fixture();assert.equal(rows(actorBuildRecords(f.target),'build_scope')[0].mapped.value.status,'empty');f.actor.type='npc';assert.throws(()=>actorBuildRecords(f.target),/character Actor/);f.actor.type='character';const feat=f.add('bad');feat.source.type='lore';assert.throws(()=>actorBuildRecords(f.target),/identity/);f.actor.items.clear();for(let i=0;i<12001;i++)f.actor.items.set(String(i),{id:String(i),type:'spell'});assert.throws(()=>actorBuildRecords(f.target),/12000/);
});
test('record bound fails incrementally and stable UUID ordering ignores membership order',()=>{
 const f=fixture();f.add('z','background');f.add('a','heritage');const first=actorBuildRecords(f.target);f.actor.items=new Map([...f.actor.items].reverse());assert.deepEqual(actorBuildRecords(f.target),first);
 const big=fixture();for(let i=0;i<1200;i++)big.add(String(i));assert.throws(()=>actorBuildRecords(big.target),/24000 selected records/);
});
