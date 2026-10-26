import test from 'node:test';
import assert from 'node:assert/strict';
import {readActor} from '../../foundry-module/scripts/actors.js';

function fixture(synthetic=false){
 const docs=new Map(),sources=new Map();let stateReads=0;
 const actorSource={name:'Creature',type:'npc',system:{attributes:{hp:{value:9}}}};
 const actor={documentName:'Actor',id:'a',uuid:synthetic?'Scene.s.Token.t.Actor.a':'Actor.a',name:'Creature',type:'npc',folder:null,compendium:null,items:new Map(),testUserPermission:()=>true,toObject:flag=>{assert.equal(flag,true);return structuredClone(actorSource);}};
 const external={documentName:'Actor',id:'external',uuid:'Actor.external',name:'Origin',type:'npc',folder:null,compendium:null,items:new Map(),testUserPermission:()=>true,toObject(){throw Error('target source must not expand');}};
 docs.set(actor.uuid,actor);docs.set(external.uuid,external);
 let selector={actor_uuid:actor.uuid};
 if(synthetic){const scene={documentName:'Scene',uuid:'Scene.s',name:'Scene',testUserPermission:()=>true};const token={documentName:'Token',id:'t',uuid:'Scene.s.Token.t',name:'Token',parent:scene,actor,baseActor:null,isLinked:false,testUserPermission:()=>true};docs.set(token.uuid,token);selector={token_uuid:token.uuid};}
 function add(id,type,system={}){const source={name:'Duplicate',type,system};const item={documentName:'Item',id,uuid:`${actor.uuid}.Item.${id}`,name:'Duplicate',type,parent:actor,folder:null,compendium:null,testUserPermission:()=>true,toObject(flag){stateReads++;assert.equal(flag,true);return source;}};actor.items.set(id,item);sources.set(id,source);docs.set(item.uuid,item);return item;}
 const condition=add('condition','condition',{value:{isValued:true,value:2},references:{parent:{id:'effect'},children:[],overrides:[],overriddenBy:[]},persistent:{formula:'1d6',damageType:'fire',dc:15,criticalHit:false},overrides:[]});
 const effect=add('effect','effect',{duration:{value:2,unit:'rounds',expiry:'turn-start',sustained:false},badge:{type:'counter',value:1,min:null,max:3},context:{origin:{actor:external.uuid},target:null,roll:null}});
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map([['a',actor],['external',external]]),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>docs.get(uuid)}};
 return {actor,actorSource,external,condition,effect,selector,sources,add,get stateReads(){return stateReads;}};
}
async function all(f){const rows=[],pages=[];let cursor;do{const page=await readActor({...f.selector,sections:['state'],limit:2,max_bytes:8000,...(cursor?{cursor}:{})});assert.ok(Buffer.byteLength(JSON.stringify(page))<=8000);pages.push(page);rows.push(...page.records);cursor=page.pagination.next_cursor;assert.ok(pages.length<150);}while(cursor);return {rows,pages};}
const code=expected=>error=>error.rpcError?.code===expected;

test('actual paginated state reads join owned source and immediate references with canonical world/token provenance',async()=>{
 for(const synthetic of [false,true]){const f=fixture(synthetic),before=JSON.stringify([...f.sources]),result=await all(f);assert.ok(result.pages.length>1);assert.equal(new Set(result.rows.map(row=>row.key)).size,result.rows.length);assert.ok(result.pages.every(page=>page.sections[0].status==='partial'&&page.sections[0].reasons.includes('effective_application_not_evaluated')));
  const items=result.rows.filter(row=>row.key.startsWith('state:item:'));assert.equal(items.length,2);assert.ok(items.every(row=>row.mapped.value.application==='unknown'));if(synthetic)assert.ok(items.every(row=>row.mapped.value.token_uuid===f.selector.token_uuid));
  const source=result.rows.find(row=>row.key===`state:source:${f.condition.uuid}:/system/persistent/formula`);assert.equal(source.raw[0].value,'1d6');assert.equal(source.raw[0].basis,'source');assert.equal(source.provenance.mapping,'pf2e.condition.source.v1');
  const parent=result.rows.find(row=>row.key===`state:condition:${f.condition.uuid}:/system/references/parent/id`);assert.equal(parent.mapped.value.target_uuid,f.effect.uuid);
  const origin=result.rows.find(row=>row.key===`state:effect:${f.effect.uuid}:origin_actor`);assert.equal(origin.raw.length,5);assert.equal(origin.mapped.value.name,'Origin');assert.equal(origin.mapped.value.target_uuid,f.external.uuid);assert.equal(result.rows.filter(row=>row.key==='state:capability:affliction').length,1);assert.equal(JSON.stringify([...f.sources]),before);
 }
});
test('state continuations detect owned source/membership/permission and external identity/status changes',async()=>{
 for(const mutate of [f=>f.sources.get('condition').system.value.value++,f=>f.actor.items.delete('condition'),f=>f.condition.testUserPermission=()=>false,f=>f.external.name='Renamed',f=>f.external.testUserPermission=()=>false]){const f=fixture(),params={...f.selector,sections:['state'],limit:1},first=await readActor(params);assert.ok(first.pagination.next_cursor);mutate(f);await assert.rejects(readActor({...params,cursor:first.pagination.next_cursor}),code('ContentChanged'));}
});
test('state capability is always explicit, denied source stays hidden and other systems fail before serialization',async()=>{
 const f=fixture();for(const item of f.actor.items.values()){item.testUserPermission=()=>false;item.toObject=()=>{throw Error('denied source');};}const denied=await all(f);assert.equal(denied.rows.length,2);assert.deepEqual(denied.rows.find(row=>row.key==='state:denied').mapped.value,{status:'denied',target_uuid:null});assert.ok(denied.pages.every(page=>page.sections[0].reasons.includes('state_items_denied')));
 f.actor.items.clear();const empty=await all(f);assert.equal(empty.rows.length,1);assert.equal(empty.rows[0].key,'state:capability:affliction');
 const other=fixture();game.system.id='other';await assert.rejects(readActor({...other.selector,sections:['state']}),code('UnsupportedSystem'));assert.equal(other.stateReads,0);
});
test('default/source reads never serialize state Items and selected source accessors fail without invocation',async()=>{
 const f=fixture();for(const sections of [undefined,['source']])await readActor({...f.selector,...(sections?{sections}:{})});assert.equal(f.stateReads,0);
 let calls=0;Object.defineProperty(f.sources.get('effect').system.context.origin,'actor',{get(){calls++;return 'Actor.secret';}});await assert.rejects(readActor({...f.selector,sections:['state']}),code('ReadFailed'));assert.equal(calls,0);
});
