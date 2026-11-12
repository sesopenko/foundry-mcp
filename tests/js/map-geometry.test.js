import test from 'node:test';
import assert from 'node:assert/strict';
import {mapNoteToSource,mapRegionNotes,validateMapCrop} from '../../foundry-module/scripts/mapGeometry.js';
import {getMapImageContext,getMapRegionCandidates} from '../../foundry-module/scripts/mapContext.js';
import {handleRpcMessage} from '../../foundry-module/scripts/foundryBridge.js';
import {contextWorld} from './fixtures/map-context-world.js';
import {webcrypto} from 'node:crypto';
globalThis.crypto??=webcrypto;
const rect={sceneX:1800,sceneY:2400,sceneWidth:6800,sceneHeight:9000};
const source={width:6800,height:9000};

test('measured rectangle and shifted origin map independently to original pixels without double shift',()=>{
  assert.deepEqual(mapNoteToSource(rect,source,1900,2500),{source_x:100,source_y:100});
  const shifted={...rect,sceneX:1680,sceneY:2480};
  assert.deepEqual(mapNoteToSource(shifted,source,1780,2580),{source_x:100,source_y:100});
  assert.deepEqual(mapNoteToSource(rect,{width:3400,height:4500},1900,2500),{source_x:50,source_y:50});
});

test('exclusive source crops retain numeric aliases rather than renumbering or lexical key order',()=>{
  const notes=[{key:'N10',note_uuid:'Scene.s.Note.z',x:1910,y:2510},{key:'N2',note_uuid:'Scene.s.Note.b',x:1900,y:2500},
    {key:'N1',note_uuid:'Scene.s.Note.a',x:1920,y:2510},{key:'N9',note_uuid:'Scene.s.Note.y',x:1910,y:2520}];
  const selected=mapRegionNotes(notes,rect,source,{x:100,y:100,width:20,height:20});
  assert.deepEqual(selected.map(n=>n.key),['N2','N10']);assert.equal(selected[0].source_x,100);
  assert.equal(mapRegionNotes(notes,rect,source,{x:100,y:100,width:1,height:1}).length,1);
});

test('orientation uses display axes and scaled Scene/source dimensions independently',()=>{
  assert.deepEqual(mapNoteToSource({sceneX:10,sceneY:20,sceneWidth:300,sceneHeight:500},{width:3,height:5},310,520),{source_x:3,source_y:5});
  assert.deepEqual(mapNoteToSource({sceneX:0,sceneY:0,sceneWidth:10,sceneHeight:20},{width:5,height:3},4,10),{source_x:2,source_y:1.5});
});

test('invalid geometry/crops and nonfinite or boolean positions fail explicitly',()=>{
  const bad=e=>e.rpcError?.code==='UnsupportedMapMapping';
  for(const point of [[true,1],[Infinity,1],[1,NaN]])assert.throws(()=>mapNoteToSource(rect,source,...point),bad);
  for(const crop of [{x:0,y:0,width:0,height:1},{x:6799,y:0,width:2,height:1},{x:true,y:0,width:1,height:1}])assert.throws(()=>validateMapCrop(rect,source,crop),bad);
  assert.throws(()=>mapNoteToSource({...rect,sceneWidth:0},source,1,2),bad);
});

const caller='a'.repeat(64),map={scene_uuid:'Scene.scene',level_id:'floor',role:'background'};
const rpcError=code=>e=>e.rpcError?.code===code;
test('private map context resolves canonical membership and pins bounded alias/placement witnesses',async()=>{
  const f=contextWorld();
  const reply=await handleRpcMessage({id:'context',method:'getMapImageContext',params:{map,caller_key:caller}});
  assert.ok(!reply.error);assert.equal(reply.result.mapping.status,'supported');
  assert.deepEqual(reply.result.image,{source:'data',directory:'assets',src:'assets/a.png'});
  assert.equal(reply.result.alias_total,1);assert.equal(reply.result.level_uuid,'Scene.scene.Level.floor');
  assert.ok(!Object.hasOwn(reply.result,'notes'));assert.ok(!Object.hasOwn(reply.result,'source_witness'));
  assert.equal(f.listings,2);
});

test('nondefault whole-schema placement, foreground and unverified builds remain explicit unsupported mappings',async()=>{
  const f=contextWorld();f.source.levels[0].textures={default_placement:false};
  assert.equal((await getMapImageContext({map,caller_key:caller})).mapping.reason,'nondefault_placement');
  assert.equal((await getMapImageContext({map:{...map,role:'foreground'},caller_key:caller})).mapping.reason,'foreground_role');
  contextWorld({version:'14.370'});
  assert.equal((await getMapImageContext({map,caller_key:caller})).mapping.reason,'unverified_build');
});

test('reference mutation across source resolution rejects context and native failures expose no private diagnostics',async()=>{
  const f=contextWorld();let first=true;
  f.browse_hook=()=>{if(first){first=false;f.source.levels[0].background.src='assets/replaced.png';}};
  await assert.rejects(getMapImageContext({map,caller_key:caller}),rpcError('MapContextChanged'));
  const g=contextWorld();g.scene.toObject=()=>{throw Error('https://private.example/secret');};
  const reply=await handleRpcMessage({id:'error',method:'getMapImageContext',params:{map,caller_key:caller}});
  assert.equal(reply.error.code,'MapContextReadFailed');assert.ok(!JSON.stringify(reply).includes('secret'));
});

test('bound reference changes are rejected before resolving a replacement missing file',async()=>{
  const f=contextWorld();const context=await getMapImageContext({map,caller_key:caller});
  const before=f.listings;f.source.levels[0].background.src='assets/missing.png';
  await assert.rejects(getMapImageContext({map,caller_key:caller,expected_reference_digest:context.reference_digest}),rpcError('MapContextChanged'));
  assert.equal(f.listings,before);
});

test('private region pages retain aliases and bind source/crop scope with exclusive edges',async()=>{
  const f=contextWorld();f.source.notes.push({id:'n02',x:1910,y:2510,text:'Other',levels:[],entryId:null,pageId:null});
  f.source.notes.push({id:'n03',x:1920,y:2510,text:'Edge',levels:[],entryId:null,pageId:null});
  // Rebuild the external collection after fixture changes, never patch production.
  contextWorld({scene:f.source});
  const context=await getMapImageContext({map,caller_key:caller});
  const args={map,caller_key:caller,expected_revision:context.revision,source_size:source,
    crop:{x:100,y:100,width:20,height:20},source_scope:'b'.repeat(64),limit:1};
  const first=await getMapRegionCandidates(args);assert.equal(first.total_in_region,2);
  assert.equal(first.entries[0].key,'N1');assert.equal(first.complete,false);
  const rest=await getMapRegionCandidates({...args,cursor:first.next_cursor,limit:100});
  assert.equal(rest.entries[0].key,'N2');assert.equal(rest.complete,true);
  await assert.rejects(getMapRegionCandidates({...args,cursor:first.next_cursor,source_scope:'c'.repeat(64)}),rpcError('InvalidCursor'));
  await assert.rejects(getMapRegionCandidates({...args,cursor:first.next_cursor,crop:{x:0,y:0,width:20,height:20}}),rpcError('InvalidCursor'));
});

test('candidate byte bounds include context, geometry, entries and cursor without whole-note export',async()=>{
  const f=contextWorld();f.source.notes=Array.from({length:20},(_,i)=>({id:'n'+String(i).padStart(2,'0'),x:1900+i,y:2500,text:'label',levels:[],entryId:null,pageId:null}));
  contextWorld({scene:f.source});const context=await getMapImageContext({map,caller_key:caller});
  const args={map,caller_key:caller,expected_revision:context.revision,source_size:source,
    crop:{x:0,y:0,width:6800,height:9000},source_scope:'b'.repeat(64),max_bytes:2000};
  const page=await getMapRegionCandidates(args);
  assert.ok(new TextEncoder().encode(JSON.stringify(page)).length<=2000);
  assert.ok(page.entries.length>0&&page.entries.length<20);assert.equal(page.complete,false);
  assert.ok(page.entries.every(n=>!Object.hasOwn(n,'label')&&!Object.hasOwn(n,'journal')));
  await assert.rejects(getMapRegionCandidates({...args,max_bytes:1024}),rpcError('ResponseTooLarge'));
});

test('mutation during final asynchronous candidate-scope hashing rejects the old region snapshot',async()=>{
  const f=contextWorld();const context=await getMapImageContext({map,caller_key:caller});
  const original=Object.getOwnPropertyDescriptor(globalThis,'crypto');let hashes=0;
  Object.defineProperty(globalThis,'crypto',{configurable:true,value:{subtle:{async digest(...args){
    const result=await webcrypto.subtle.digest(...args);if(++hashes===5)f.source.notes[0].x++;return result;
  }}}});
  try{await assert.rejects(getMapRegionCandidates({map,caller_key:caller,expected_revision:context.revision,
    source_size:source,crop:{x:0,y:0,width:6800,height:9000},source_scope:'b'.repeat(64)}),rpcError('MapContextChanged'));}
  finally{Object.defineProperty(globalThis,'crypto',original);}
});
