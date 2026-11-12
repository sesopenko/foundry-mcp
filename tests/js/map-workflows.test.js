import test from 'node:test';
import assert from 'node:assert/strict';
import {webcrypto} from 'node:crypto';
import {contextWorld} from './fixtures/map-context-world.js';
import {handleRpcMessage} from '../../foundry-module/scripts/foundryBridge.js';
globalThis.crypto??=webcrypto;
const key='a'.repeat(64);
const bytes=value=>new TextEncoder().encode(JSON.stringify(value)).length;

test('non-PF2e inactive folder navigation leads to exact level, private geometry and stable note legend',async()=>{
  const state=contextWorld({folders:[{id:'root',name:'Adventure',folder:null,sorting:'m',sort:0}],scene:{
    id:'scene',name:'Map',folder:'root',sort:0,width:1000,height:800,padding:.25,shiftX:50,shiftY:-20,
    rectangle:{sceneX:150,sceneY:220,sceneWidth:1000,sceneHeight:800},
    grid:{type:1,size:180,distance:5,units:'ft',style:'solid',thickness:1,color:'#000000',alpha:.35},
    initialLevel:'floor',levels:[{id:'floor',name:'Floor',sort:0,textures:{default_placement:true},background:{src:'assets/a.png'}}],
    notes:[{id:'n01',x:650,y:620,text:'Linked',levels:[],entryId:'journal',pageId:'page'}]},
    journals:[{id:'journal',name:'Journal',pages:[{id:'page',name:'Page'}]}]});
  const call=async(method,params={})=>{
    const result=await handleRpcMessage({id:crypto.randomUUID(),method,params:{caller_key:key,...params}});
    assert.ok(!result.error,JSON.stringify(result.error));assert.ok(bytes(result)<65536);return result.result;
  };
  const root=await call('browseMaps');assert.equal(root.entries[0].name,'Adventure');
  const folder=await call('browseMaps',root.entries[0].next_call.arguments);
  assert.equal(folder.entries[0].scene_uuid,'Scene.scene');
  const assets=await call('getMapInfo',folder.entries[0].next_call.arguments);
  assert.equal(assets.grid.size,180);assert.equal(assets.geometry.width,1000);
  const map=assets.entries[0].background.info_next_call.arguments.request.map;
  assert.deepEqual(map,{scene_uuid:'Scene.scene',level_id:'floor',role:'background'});
  const context=await call('getMapImageContext',{map});
  assert.equal(context.mapping.status,'supported');
  const legend=await call('getMapInfo',{scene_uuid:map.scene_uuid,level_id:map.level_id,section:'notes',note_keys:['N1'],expected_revision:context.revision});
  assert.equal(legend.entries[0].note_uuid,'Scene.scene.Note.n01');
  assert.equal(legend.entries[0].page.page_uuid,'JournalEntry.journal.JournalEntryPage.page');
  assert.equal(game.system.id,'other');assert.equal(state.scene.id,'scene');
  state.source.notes[0].text='Changed';
  const stale=await handleRpcMessage({id:'stale',method:'getMapInfo',params:{caller_key:key,scene_uuid:'Scene.scene',level_id:'floor',section:'notes',expected_revision:context.revision}});
  assert.equal(stale.error.code,'ContentChanged');
});
