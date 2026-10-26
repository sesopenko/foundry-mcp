import test from 'node:test';
import assert from 'node:assert/strict';
import {listSceneActors} from '../../foundry-module/scripts/actorScenes.js';
import {readActor,readItem,listActorItems} from '../../foundry-module/scripts/actors.js';

function fixture(type='npc'){
 const docs=new Map(),sources=new Map(),currents=new Map();
 const scene={documentName:'Scene',id:'inactive',uuid:'Scene.inactive',name:'Inactive',active:false,tokens:new Map(),testUserPermission:()=>true};docs.set(scene.uuid,scene);
 function makeActor(uuid,hp,currentHp,masterId=null){
  const source={name:'Same creature',type,system:{attributes:{hp:{value:hp,temp:0}},...(type==='familiar'?{master:{id:masterId,ability:'int'}}:{})}};
  const current={name:source.name,type,system:{attributes:{hp:{value:currentHp,max:30,temp:0}}}};
  const actor={documentName:'Actor',id:'base',uuid,name:source.name,type,folder:null,compendium:null,items:new Map(),testUserPermission:()=>true,toObject(flag){if(type==='familiar')assert.equal(flag,true);return structuredClone(flag?source:current);},update(){throw Error('writes prohibited');},prepareData(){throw Error('preparation prohibited');}};
  Object.defineProperty(actor,'master',{get(){throw Error('master getter prohibited');}});
  docs.set(uuid,actor);sources.set(uuid,source);currents.set(uuid,current);return actor;
 }
 function action(actor,id,label){
  const source={name:label,type:'action',system:{actionType:{value:'passive'},actions:{value:null},traits:{value:[]},description:{value:`<p>${label}</p>`}}};
  const item={documentName:'Item',id,uuid:`${actor.uuid}.Item.${id}`,name:label,type:'action',parent:actor,folder:null,compendium:null,testUserPermission:()=>true,toObject(flag){assert.equal(flag,true);return structuredClone(source);},update(){throw Error('writes prohibited');}};
  actor.items.set(id,item);docs.set(item.uuid,item);sources.set(item.uuid,source);return item;
 }
 const base=makeActor('Actor.base',29,28),a=makeActor('Scene.inactive.Token.a.Actor.base',7,5,'m1'),b=makeActor('Scene.inactive.Token.b.Actor.base',19,17,'m2');
 for(const [actor,label]of [[base,'Base'],[a,'First'],[b,'Second']]){action(actor,'shared',label+' ability');action(actor,'other',label+' extra');}
 const token=(id,actor,linked=false)=>{const value={documentName:'Token',id,uuid:`${scene.uuid}.Token.${id}`,name:'Same token',parent:scene,actor,baseActor:base,isLinked:linked,testUserPermission:()=>true};scene.tokens.set(id,value);docs.set(value.uuid,value);return value;};
 const tokens=[token('a',a),token('b',b),token('linked',base,true)],masters=[];
 for(const id of ['m1','m2']){const master={documentName:'Actor',id,uuid:`Actor.${id}`,name:'Master '+id,type:'character',folder:null,compendium:null,items:new Map(),testUserPermission:()=>true,toObject(){throw Error('master source prohibited');}};masters.push(master);docs.set(master.uuid,master);sources.set(master.uuid,{name:master.name,type:'character',system:{attributes:{hp:{value:100}}}});}
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map([['base',base],...masters.map(master=>[master.id,master])]),items:new Map(),scenes:new Map([[scene.id,scene]])};
 globalThis.foundry={utils:{fromUuid:async uuid=>docs.get(uuid)}};
 return {docs,sources,currents,scene,base,a,b,tokens,masters,action};
}
async function pages(call,params,key='records'){
 const rows=[],results=[];let cursor;
 do{const result=await call({...params,limit:1,max_bytes:8000,...(cursor?{cursor}:{})});assert.ok(Buffer.byteLength(JSON.stringify(result))<=8000);rows.push(...result[key]);results.push(result);cursor=result.pagination.next_cursor;assert.ok(results.length<250);}while(cursor);
 return {rows,results};
}
const code=expected=>error=>error.rpcError?.code===expected;
const hp=(rows,section)=>rows.find(row=>row.section===section&&row.raw[0]?.path==='/system/attributes/hp/value');

test('inactive discovery through actual readers keeps two shared-base synthetic HP and Items separate without canvas',async t=>{
 const f=fixture(),before=JSON.stringify([...f.sources]),previous=Object.getOwnPropertyDescriptor(globalThis,'canvas');
 Object.defineProperty(globalThis,'canvas',{configurable:true,get(){throw Error('canvas prohibited');}});t.after(()=>previous?Object.defineProperty(globalThis,'canvas',previous):Reflect.deleteProperty(globalThis,'canvas'));
 const navigation=await pages(listSceneActors,{scene_uuid:f.scene.uuid},'nodes');assert.equal(navigation.rows.length,3);
 for(const [index,actor,stored,current,label]of [[0,f.a,7,5,'First'],[1,f.b,19,17,'Second'],[2,f.base,29,28,'Base']]){
  const token=f.tokens[index],node=navigation.rows.find(node=>node.uuid===token.uuid);assert.equal(node.identity.uuid,actor.uuid);assert.equal(node.base_actor.uuid,f.base.uuid);assert.equal(node.actor_link,index===2);
  const result=await pages(readActor,{...node.next_call.arguments,sections:['source','statistics','abilities']});
  assert.equal(hp(result.rows,'source').raw[0].value,stored);assert.equal(hp(result.rows,'statistics').raw[0].value,current);
  for(const row of [hp(result.rows,'source'),hp(result.rows,'statistics')]){assert.equal(row.raw[0].document_uuid,actor.uuid);assert.equal(row.provenance.contributors[0].document_uuid,actor.uuid);}
  assert.equal(hp(result.rows,'source').raw[0].basis,'source');assert.equal(hp(result.rows,'statistics').raw[0].basis,'transformed');
  assert.ok(result.results.every(page=>page.identity.uuid===actor.uuid&&page.identity.instance.token_uuid===token.uuid&&page.identity.instance.base_actor.uuid===f.base.uuid));
  const abilities=result.rows.filter(row=>row.mapped.concept==='npc_ability_item');assert.equal(abilities.length,2);assert.ok(abilities.every(row=>row.mapped.value.token_uuid===token.uuid&&row.mapped.value.target_uuid.startsWith(actor.uuid+'.Item.')));
  const inventory=await pages(listActorItems,{token_uuid:token.uuid},'nodes');assert.equal(inventory.rows.length,2);
  for(const item of inventory.rows){assert.equal(item.identity.actor.uuid,actor.uuid);assert.equal(item.identity.instance.token_uuid,token.uuid);const read=await pages(readItem,{...item.next_call.arguments,sections:['description']});assert.equal(read.rows.map(row=>row.raw[0].value).join(''),`<p>${label}${item.identity.id==='shared'?' ability':' extra'}</p>`);assert.ok(read.rows.every(row=>row.raw[0].document_uuid===item.identity.uuid));}
 }
 await assert.rejects(readItem({item_uuid:f.a.items.get('shared').uuid,token_uuid:f.tokens[1].uuid}),code('DocumentNotFound'));
 await assert.rejects(readItem({item_uuid:f.base.items.get('shared').uuid,token_uuid:f.tokens[0].uuid}),code('DocumentNotFound'));
 assert.equal(JSON.stringify([...f.sources]),before);
});

test('token-selected continuations detect selected identity/current changes and owned Item membership',async()=>{
 for(const change of [f=>f.tokens[0].name='Renamed',f=>f.tokens[0].isLinked=true,f=>f.base.name='Base renamed',f=>f.tokens[0].actor=f.b,f=>f.currents.get(f.a.uuid).system.attributes.hp.value++]){
  const f=fixture(),params={token_uuid:f.tokens[0].uuid,sections:['source','statistics'],limit:1},first=await readActor(params);assert.ok(first.pagination.next_cursor);change(f);await assert.rejects(readActor({...params,cursor:first.pagination.next_cursor}),code('ContentChanged'));
 }
 const f=fixture(),params={token_uuid:f.tokens[0].uuid,limit:1},first=await listActorItems(params);f.a.items.delete('other');await assert.rejects(listActorItems({...params,cursor:first.pagination.next_cursor}),code('ContentChanged'));
});

test('deleted/missing token Actors, missing base, readiness and permission failures are explicit',async()=>{
 let f=fixture();f.docs.delete(f.tokens[0].uuid);await assert.rejects(readActor({token_uuid:f.tokens[0].uuid}),code('DocumentNotFound'));
 f=fixture();f.tokens[0].actor=null;await assert.rejects(readActor({token_uuid:f.tokens[0].uuid}),code('ActorUnavailable'));
 f=fixture();f.tokens[0].baseActor=null;const page=await readActor({token_uuid:f.tokens[0].uuid,sections:['source']});assert.equal(page.identity.uuid,f.a.uuid);assert.equal(page.identity.instance.base_actor,null);
 for(const mutate of [()=>game.ready=false,f=>f.scene.testUserPermission=()=>false,f=>f.tokens[0].testUserPermission=()=>false,f=>f.a.testUserPermission=()=>false]){f=fixture();mutate(f);await assert.rejects(readActor({token_uuid:f.tokens[0].uuid}),code(game.ready?'PermissionDenied':'NotReady'));}
});

test('two synthetic familiar master claims resolve independently and missing master never fabricates statistics',async()=>{
 const f=fixture('familiar');
 for(const [index,master]of f.masters.entries()){
  const result=await pages(readActor,{token_uuid:f.tokens[index].uuid,sections:['identity','source','abilities']});const row=result.rows.find(row=>row.provenance.mapping==='pf2e.familiar.master.v1');assert.equal(row.raw[0].document_uuid,[f.a,f.b][index].uuid);assert.equal(row.mapped.value.target_uuid,master.uuid);assert.ok(result.rows.filter(row=>row.provenance.mapping==='pf2e.familiar.ability.v1').every(row=>row.mapped.value.token_uuid===f.tokens[index].uuid));
 }
 for(const [set,status]of [[f=>game.actors.delete('m1'),'missing'],[f=>f.sources.get(f.a.uuid).system.master.id=null,'unassociated'],[f=>delete f.sources.get(f.a.uuid).system.master.id,'missing'],[f=>f.masters[0].testUserPermission=()=>false,'denied']]){const f=fixture('familiar');set(f);const result=await pages(readActor,{token_uuid:f.tokens[0].uuid,sections:['identity','source','statistics']});const row=result.rows.find(row=>row.provenance.mapping==='pf2e.familiar.master.v1');assert.deepEqual(row.mapped.value,{status,target_uuid:null});assert.ok(result.results.every(page=>page.sections.find(section=>section.name==='identity').reasons.includes('familiar_master_'+status)));assert.ok(result.results.every(page=>page.sections.find(section=>section.name==='statistics').status==='partial'));assert.ok(!result.rows.some(row=>row.provenance.mapping==='pf2e.familiar.current.v1'));}
});

test('familiar token identity continuations track selected master claims/identity but not unrelated master state',async()=>{
 for(const change of [f=>f.sources.get(f.a.uuid).system.master.id='m2',f=>f.masters[0].name='Renamed',f=>f.masters[0].testUserPermission=()=>false,()=>game.actors.delete('m1')]){const f=fixture('familiar'),params={token_uuid:f.tokens[0].uuid,sections:['identity','source'],limit:1},first=await readActor(params);assert.ok(first.pagination.next_cursor);change(f);await assert.rejects(readActor({...params,cursor:first.pagination.next_cursor}),code('ContentChanged'));}
 const f=fixture('familiar'),params={token_uuid:f.tokens[0].uuid,sections:['identity','source'],limit:1},first=await readActor(params);f.masters[1].name='Unrelated renamed';f.sources.get(f.masters[0].uuid).system.attributes.hp.value--;const next=await readActor({...params,cursor:first.pagination.next_cursor});assert.equal(next.revision,first.revision);
});
