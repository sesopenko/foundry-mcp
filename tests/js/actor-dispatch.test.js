import test from 'node:test';
import assert from 'node:assert/strict';
import {handleRpcMessage} from '../../foundry-module/scripts/foundryBridge.js';

test('discovery RPC dispatch returns real handler results and structured failures',async()=>{
  const actor={id:'guard',uuid:'Actor.guard',name:'Guard',type:'npc',documentName:'Actor',folder:null,compendium:null,testUserPermission:()=>true};
  const pack={collection:'world.creatures',title:'Creatures',documentName:'Actor',visible:true,testUserPermission:()=>true,
    getIndex:async()=>new Map([['guard',{_id:'guard',name:'Guard',type:'npc'}]]),getUuid:id=>`Compendium.world.creatures.Actor.${id}`};
  globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map([['guard',actor]]),items:new Map(),folders:new Map(),packs:new Map([[pack.collection,pack]])};
  for(const [method,params,kind] of [
    ['getActorTree',{},'actor'],
    ['searchActors',{query:'guard'},'actor'],
    ['listActorCompendiums',{document_type:'Actor',query:null,cursor:null},'pack'],
    ['searchCompendiumActors',{document_type:'Actor',pack_ids:[pack.collection],query:'guard',types:null,cursor:null},'actor']
  ]) {
    const response=await handleRpcMessage({id:method,method,params});
    assert.equal(response.id,method);assert.equal(response.error,undefined);
    assert.equal(response.result.nodes[0].kind,kind);
    assert.equal(response.result.pagination.complete,true);
  }
  const invalid=await handleRpcMessage({id:'invalid',method:'searchCompendiumActors',params:{pack_ids:[],query:'guard'}});
  assert.equal(invalid.error.code,'InvalidRequest');assert.equal(typeof invalid.error.recovery,'string');
  game.user.isGM=false;
  const denied=await handleRpcMessage({id:'denied',method:'getActorTree'});
  assert.equal(denied.error.code,'PermissionDenied');
});
