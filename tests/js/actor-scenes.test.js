import test from 'node:test';
import assert from 'node:assert/strict';
import {listSceneActors} from '../../foundry-module/scripts/actorScenes.js';

function fixture() {
  const doc=(uuid,name,documentName)=>({uuid,id:uuid.split('.').at(-1),name,documentName,testUserPermission:()=>true});
  const scene=doc('Scene.inactive','Inactive','Scene');scene.tokens=new Map();
  const base={...doc('Actor.base','Base','Actor'),type:'npc',folder:null,compendium:null};
  for (const id of ['a','b']) {
    const token=doc(`Scene.inactive.Token.${id}`,'Duplicate','Token');
    Object.assign(token,{parent:scene,isLinked:false,baseActor:base,
      actor:{...base,uuid:`Scene.inactive.Token.${id}.Actor.base`,name:`Current ${id}`}});
    scene.tokens.set(id,token);
  }
  globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map(),items:new Map(),scenes:new Map([['inactive',scene]])};
  return {scene,base};
}

test('inactive scene navigation preserves separate synthetic identities and linked selectors',async()=>{
  const {scene,base}=fixture();
  const scenes=await listSceneActors();assert.equal(scenes.nodes[0].next_call.arguments.scene_uuid,scene.uuid);
  let page=await listSceneActors({scene_uuid:scene.uuid,limit:1});
  const first=page.nodes[0];assert.equal(first.identity.instance.base_actor.uuid,base.uuid);
  page=await listSceneActors({scene_uuid:scene.uuid,limit:1,cursor:page.pagination.next_cursor});
  assert.notEqual(first.identity.uuid,page.nodes[0].identity.uuid);
  assert.equal(first.next_call.arguments.token_uuid,first.uuid);
  const token=scene.tokens.get('a');token.actor=base;token.isLinked=true;
  const linked=await listSceneActors({scene_uuid:scene.uuid,query:'current b'});
  assert.equal(linked.nodes.length,1);assert.equal(linked.nodes[0].id,'b');
  const all=await listSceneActors({scene_uuid:scene.uuid});
  assert.equal(all.nodes[0].identity.uuid,base.uuid);assert.equal(all.nodes[0].actor_link,true);
});

test('missing actor stays explicit; filters, permissions and stale revisions are checked',async()=>{
  const {scene}=fixture();const token=scene.tokens.get('a');token.actor=null;
  let result=await listSceneActors({scene_uuid:scene.uuid});
  assert.equal(result.nodes[0].identity,null);assert.equal(result.nodes[0].next_call,null);
  assert.match(result.nodes[0].limitations[0],/ActorUnavailable/);
  await assert.rejects(listSceneActors({query:'x'}),/require scene_uuid/);
  await assert.rejects(listSceneActors({scene_uuid:'Scene.missing'}),/no longer exists/);
  await assert.rejects(listSceneActors({scene_uuid:scene.uuid,types:['loot']}),/known|supported section/);
  result=await listSceneActors({scene_uuid:scene.uuid,limit:1});
  scene.tokens.get('b').name='Renamed';
  await assert.rejects(listSceneActors({scene_uuid:scene.uuid,limit:1,cursor:result.pagination.next_cursor}),/changed/);
  token.testUserPermission=()=>false;
  result=await listSceneActors({scene_uuid:scene.uuid});
  assert.equal(result.scopes.find(s=>s.id===scene.uuid).status,'incomplete');
  scene.testUserPermission=()=>false;
  await assert.rejects(listSceneActors({scene_uuid:scene.uuid}),/not readable/);
  result=await listSceneActors();assert.equal(result.scopes[0].status,'denied');
});

test('unsupported actor types are counted separately from caller filters',async()=>{
 const {scene}=fixture();
 scene.tokens.get('a').actor.type='loot';
 let result=await listSceneActors();assert.equal(result.unsupported_count,0);
 result=await listSceneActors({scene_uuid:scene.uuid,types:['character']});
 assert.equal(result.unsupported_count,1);assert.equal(result.nodes.length,0);
 result=await listSceneActors({scene_uuid:scene.uuid});
 assert.equal(result.unsupported_count,1);assert.equal(result.nodes.length,1);
});

test('missing or inaccessible base stays separate from available current actor',async()=>{
 const {scene}=fixture();
 scene.tokens.get('a').baseActor=null;
 scene.tokens.get('b').baseActor={...scene.tokens.get('b').baseActor,testUserPermission:()=>false};
 const result=await listSceneActors({scene_uuid:scene.uuid});
 assert.equal(result.nodes.length,2);
 for(const node of result.nodes){
  assert.ok(node.identity);assert.equal(node.base_actor,null);
  assert.equal(node.identity.instance.base_actor,null);
  assert.match(node.limitations[0],/BaseActorUnavailable/);
  assert.ok(node.next_call.arguments.token_uuid);
 }
});

test('actor permission denial and cursor binding remain explicit',async()=>{
 const {scene}=fixture();
 let result=await listSceneActors({scene_uuid:scene.uuid,limit:1});
 await assert.rejects(listSceneActors({scene_uuid:scene.uuid,limit:2,cursor:result.pagination.next_cursor}),/inputs differ/);
 scene.tokens.get('a').actor.testUserPermission=()=>false;
 result=await listSceneActors({scene_uuid:scene.uuid});
 assert.equal(result.nodes.length,1);
 assert.equal(result.scopes.find(s=>s.id===scene.uuid).status,'incomplete');
 assert.equal(result.scopes.find(s=>s.id===scene.tokens.get('a').uuid).status,'denied');
 await assert.rejects(listSceneActors({scene_uuid:scene.uuid,types:['npc','npc']}),/unique/);
 await assert.rejects(listSceneActors({scene_uuid:scene.uuid,query:''}),/characters/);
 await assert.rejects(listSceneActors({scene_uuid:'Scene.inactive.Token.a'}),/world Scene/);
 game.system.id='other';
 await assert.rejects(listSceneActors(),/require PF2e/);
});
