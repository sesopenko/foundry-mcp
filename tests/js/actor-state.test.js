import test from 'node:test';
import assert from 'node:assert/strict';
import {actorStateSnapshot} from '../../foundry-module/scripts/actorState.js';

function fixture(type='npc',synthetic=false){
 const actor={documentName:'Actor',id:'a',uuid:synthetic?'Scene.s.Token.t.Actor.a':'Actor.a',type,name:'Actor',items:new Map(),folder:null,compendium:null,testUserPermission:()=>true};
 const docs=new Map([[actor.uuid,actor]]);let resolutions=0;
 const target={document:actor,identity:{uuid:actor.uuid},token:null};
 if(synthetic){const scene={documentName:'Scene',uuid:'Scene.s',name:'Scene',testUserPermission:()=>true};target.token={documentName:'Token',uuid:'Scene.s.Token.t',name:'Token',parent:scene,actor,baseActor:null,isLinked:false,testUserPermission:()=>true};docs.set(target.token.uuid,target.token);}
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map([['a',actor]]),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>{resolutions++;return docs.get(uuid);}}};
 const add=(id,type,system={},name='Duplicate')=>{const source={type,name,system},transformed={type,name,system:{}};const serializations=[];const item={documentName:'Item',id,uuid:`${actor.uuid}.Item.${id}`,type,name,system:{expired:false},parent:actor,folder:null,compendium:null,testUserPermission:()=>true,toObject(flag){serializations.push(flag);assert.equal(typeof flag,'boolean');return flag?source:transformed;}};actor.items.set(id,item);docs.set(item.uuid,item);return {item,source,transformed,serializations};};
 return {actor,target,docs,add,get resolutions(){return resolutions;}};
}
const identityRows=result=>result.records.filter(row=>row.key.startsWith('state:item:'));
test('effect expiry uses public system model when source and transformed serialization omit it',async()=>{
 for(const expired of [false,true]){
  const f=fixture(),effect=f.add('effect','effect');effect.item.system.expired=expired;
  Object.defineProperty(effect.item,'expired',{get(){throw Error('effect convenience getter prohibited');}});
  Object.defineProperty(effect.source.system,'expired',{get(){throw Error('source expiry must not be read');}});
  const result=await actorStateSnapshot(f.target),row=result.records.find(row=>row.key===`state:current:${effect.item.uuid}:/system/expired`);
  assert.ok(row);assert.equal(row.section,'state');assert.equal(row.kind,'field');
  assert.deepEqual(row.raw,[{document_uuid:effect.item.uuid,path:'/system/expired',present:true,value:expired,basis:'transformed'}]);
  assert.deepEqual(row.mapped,{concept:'current_effect_expired',value:expired,unit:null});
  assert.deepEqual(row.provenance,{contributors:[{document_uuid:effect.item.uuid,path:'/system/expired',basis:'transformed'}],mapping:'pf2e.effect.current.v1',limitations:['effect_expiry_not_application']});
  assert.ok(!effect.serializations.includes(false));assert.ok(result.reasons.includes('effective_application_not_evaluated'));
 }
});
test('missing transformed expiry remains unavailable and source cannot supply a fallback',async()=>{
 const f=fixture(),effect=f.add('effect','effect',{expired:true});effect.transformed.system.expired=true;delete effect.item.system.expired;
 const result=await actorStateSnapshot(f.target),row=result.records.find(row=>row.key===`state:current:${effect.item.uuid}:/system/expired`);
 assert.ok(row);assert.deepEqual(row.raw,[{document_uuid:effect.item.uuid,path:'/system/expired',present:false,basis:'transformed'}]);assert.equal(row.mapped.value,null);
 assert.ok(result.reasons.includes('current_effect_expiry_unavailable'));
 Object.setPrototypeOf(effect.item.system,{expired:false});const inherited=await actorStateSnapshot(f.target);assert.equal(inherited.records.find(row=>row.key===`state:current:${effect.item.uuid}:/system/expired`).raw[0].present,false);
});
test('transformed expiry rejects nonboolean and accessor leaves without invoking getters',async()=>{
 for(const value of [null,0,'false',{},undefined]){const f=fixture(),effect=f.add('effect','effect');effect.item.system.expired=value;await assert.rejects(actorStateSnapshot(f.target),TypeError);}
 for(const location of ['expired','system']){const f=fixture(),effect=f.add('effect','effect');let calls=0;Object.defineProperty(location==='expired'?effect.item.system:effect.item,location,{get(){calls++;return false;}});await assert.rejects(actorStateSnapshot(f.target),TypeError);assert.equal(calls,0);}
});
test('stored state covers actual distinct same-name Items, selected source, context and token provenance without application claims',async()=>{
 for(const type of ['character','npc','familiar']){
  const f=fixture(type,true),condition=f.add('condition','condition',{value:{isValued:true,value:0},persistent:null,references:{parent:{id:'effect'},children:[],overrides:[],overriddenBy:[]},overrides:[]}),effect=f.add('effect','effect',{duration:{value:-1,unit:'unlimited',expiry:null,sustained:false},badge:{type:'formula',value:'1d4',reevaluate:null},context:{origin:{actor:f.actor.uuid,token:f.target.token.uuid,item:condition.item.uuid},target:null,roll:null}});
  for(const field of ['active','suppressed','expired','rules','description'])for(const source of [condition.source,effect.source])Object.defineProperty(source.system,field,{get(){throw Error('unselected state accessed');}});
  Object.defineProperty(condition.item,'system',{get(){throw Error('condition model activity prohibited');}});
  const result=await actorStateSnapshot(f.target),items=identityRows(result);assert.equal(items.length,2);assert.equal(new Set(items.map(row=>row.mapped.value.target_uuid)).size,2);assert.ok(items.every(row=>row.mapped.value.name==='Duplicate'&&row.mapped.value.application==='unknown'&&row.mapped.value.token_uuid===f.target.token.uuid));
  assert.ok(!condition.serializations.includes(false),'conditions must not use transformed activity/expiry data');
  const source=result.records.find(row=>row.key===`state:source:${condition.item.uuid}:/system/value/value`);assert.equal(source.raw[0].value,0);assert.equal(source.raw[0].basis,'source');assert.equal(source.provenance.mapping,'pf2e.condition.source.v1');
  const parent=result.records.find(row=>row.key===`state:condition:${condition.item.uuid}:/system/references/parent/id`);assert.equal(parent.mapped.value.target_uuid,effect.item.uuid);
  const origin=result.records.find(row=>row.key===`state:effect:${effect.item.uuid}:origin_item`);assert.equal(origin.raw.length,5);assert.equal(origin.mapped.value.target_uuid,condition.item.uuid);
  assert.ok(!result.reasons.includes('unresolved_state_references'));assert.ok(result.reasons.includes('effective_application_not_evaluated'));assert.equal(new Set(result.records.map(row=>row.key)).size,result.records.length);
  for(const row of result.records)assert.deepEqual(row.provenance.contributors,row.raw.map(({document_uuid,path,basis})=>({document_uuid,path,basis})));
 }
});
test('empty inventory always states affliction capability and absence is not application evidence',async()=>{
 const f=fixture(),result=await actorStateSnapshot(f.target);assert.deepEqual(result.reasons,['affliction_reading_unsupported','effective_application_not_evaluated']);assert.deepEqual(result.records[0],{key:'state:capability:affliction',section:'state',kind:'field',raw:[],mapped:{concept:'state_affliction_support',value:{status:'unsupported',reason:'pf2e_8_6_1_affliction_disabled'},unit:null},provenance:{contributors:[],mapping:'pf2e.actor.state-capability.v1',limitations:['no_effective_state_inference']}});
});
test('denied scoped Items expose one marker; afflictions and unrelated types never serialize or name',async()=>{
 const f=fixture();for(const [id,type,denied]of [['one','effect',true],['two','condition',true],['affliction','affliction',false],['other','action',true]]){const {item}=f.add(id,type);item.testUserPermission=()=>!denied;item.toObject=()=>{throw Error('unreadable source');};Object.defineProperty(item,'system',{get(){throw Error('unreadable model');}});Object.defineProperty(item,'name',{get(){throw Error('unreadable name');}});}
 const result=await actorStateSnapshot(f.target);assert.equal(result.records.length,2);assert.deepEqual(result.records.find(row=>row.key==='state:denied').mapped.value,{status:'denied',target_uuid:null});assert.ok(result.reasons.includes('state_items_denied'));assert.ok(!JSON.stringify(result).includes('.Item.'));
});
test('source identity/owner/accessor failures reject safely and names use codepoint clipping',async()=>{
 for(const mutate of [row=>row.source.type='condition',row=>row.item.parent={},row=>Object.defineProperty(row.source,'type',{get(){throw Error('type getter invoked');}}),row=>Object.defineProperty(row.source.system,'badge',{get(){throw Error('badge getter invoked');}})]){const f=fixture(),row=f.add('effect','effect');mutate(row);await assert.rejects(actorStateSnapshot(f.target),TypeError);}
 const f=fixture(),row=f.add('effect','effect',{},'🙂'.repeat(257));row.item.name='Different display';const record=identityRows(await actorStateSnapshot(f.target))[0];assert.equal([...record.mapped.value.name].length,256);assert.equal(record.mapped.value.name_truncated,true);assert.equal(record.raw[0].value,'🙂'.repeat(257));
});
test('only nonempty unresolved claims add a relationship gap; absent optional roles and type-only children do not',async()=>{
 const f=fixture(),row=f.add('condition','condition',{references:{children:[{type:'condition'}]},overrides:[]});let result=await actorStateSnapshot(f.target);assert.ok(!result.reasons.includes('unresolved_state_references'));
 row.source.system.references.parent={id:'missing'};result=await actorStateSnapshot(f.target);assert.ok(result.reasons.includes('unresolved_state_references'));
 const g=fixture();g.add('effect','effect',{context:{origin:{actor:'Actor.missing'}}});result=await actorStateSnapshot(g.target);assert.ok(result.reasons.includes('unresolved_state_references'));assert.equal(result.records.find(row=>row.key.endsWith(':origin_actor')).mapped.value.status,'missing');
});
test('all aggregate bounds preflight before any external UUID resolution',async()=>{
 const count=fixture();for(let index=0;index<12001;index++)count.add(String(index),'action');await assert.rejects(actorStateSnapshot(count.target),/12000/);assert.equal(count.resolutions,0);
 const records=fixture();records.add('first','effect',{context:{origin:{actor:'Actor.missing'}}});records.add('many','condition',{overrides:Array(12000).fill('frightened')});await assert.rejects(actorStateSnapshot(records.target),/24000/);assert.equal(records.resolutions,0);
 const claims=fixture();for(let index=0;index<41;index++)claims.add(String(index),'effect',{context:{origin:{actor:'Actor.missing',token:'Scene.s.Token.missing',item:'Item.missing'},target:{actor:'Actor.missing',token:'Scene.s.Token.missing'}}});await assert.rejects(actorStateSnapshot(claims.target),/200/);assert.equal(claims.resolutions,0);
});
