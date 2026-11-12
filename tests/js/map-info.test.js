import test from 'node:test';
import assert from 'node:assert/strict';
import {webcrypto} from 'node:crypto';
import {getMapInfo,mapMedia} from '../../foundry-module/scripts/mapInfo.js';
globalThis.crypto??=webcrypto;
const key='a'.repeat(64),error=code=>e=>e.rpcError?.code===code;
const size=v=>new TextEncoder().encode(JSON.stringify(v)).length;
function fixture(){
  const collection=list=>({contents:list,invalidDocumentIds:new Set(),get:id=>list.find(d=>d.id===id)});
  const state={scenes:[],folders:[],reads:0};
  globalThis.game={ready:true,version:'14.369',world:{id:'test'},user:{id:'gm',isGM:true},system:{id:'other'},
    scenes:collection(state.scenes),folders:collection(state.folders)};
  globalThis.canvas=new Proxy({},{get(){throw Error('No canvas');}});
  const document=(kind,id,parent,source)=>{
    const doc={id,uuid:parent?parent.uuid+'.'+kind+'.'+id:kind+'.'+id,parent,source,allowed:true,
      testUserPermission(){return doc.allowed;},toObject(){assert.ok(doc.allowed);state.reads++;return structuredClone(doc.source);},
      activate(){throw Error('No activation');},view(){throw Error('No view');}};
    return doc;
  };
  state.scene=(id='one',overrides={})=>{
    const scene=document('Scene',id,null,{name:'Same map',folder:null,width:5940,height:7920,padding:.25,shiftX:0,shiftY:0,
      grid:{type:1,size:180,distance:5,units:'ft',style:'solid',thickness:1,color:'#000000',alpha:.35},initialLevel:'floor',...overrides});
    scene.levels=collection([]);scene.tiles=collection([]);scene.notes=collection([]);
    scene.getEmbeddedCollection=type=>({Level:scene.levels,Tile:scene.tiles,Note:scene.notes})[type];
    scene.getDimensions=()=>({sceneX:1620,sceneY:2160,sceneWidth:5940,sceneHeight:7920});
    state.scenes.push(scene);return scene;
  };
  state.level=(scene,id='floor',overrides={})=>{
    const doc=document('Level',id,scene,{name:'Floor',sort:0,background:{src:'maps/a.webp'},foreground:{src:null},...overrides});
    scene.levels.contents.push(doc);return doc;
  };
  state.tile=(scene,id='tile',overrides={})=>{
    const doc=document('Tile',id,scene,{name:'Artwork',sort:0,levels:[],x:10,y:20,width:300,height:400,rotation:15,
      texture:{src:'maps/t.png',scaleX:1,scaleY:-1},...overrides});
    scene.tiles.contents.push(doc);return doc;
  };
  state.call=(params={},guard)=>getMapInfo({caller_key:key,scene_uuid:'Scene.one',...params},guard);
  return state;
}

test('screenshot geometry/grid and explicit level roles preserve raw reference versus pixel dimensions',async()=>{
  const f=fixture(),scene=f.scene();f.level(scene,'floor',{foreground:{src:'maps/front.png'}});
  const result=await f.call();
  assert.equal(result.geometry.width,5940);assert.equal(result.geometry.height,7920);
  assert.deepEqual(result.geometry.scene_rect,{sceneX:1620,sceneY:2160,sceneWidth:5940,sceneHeight:7920});
  assert.deepEqual(result.grid,scene.source.grid);assert.equal(result.initial_level_id,'floor');
  const row=result.entries[0];assert.equal(row.level_uuid,'Scene.one.Level.floor');
  assert.equal(row.background.reference,'maps/a.webp');assert.equal(row.foreground.reference,'maps/front.png');
  assert.deepEqual(row.background.map,{scene_uuid:'Scene.one',level_id:'floor',role:'background'});
  assert.deepEqual(row.foreground.info_next_call,{tool:'get_foundry_image_info',arguments:{request:{map:row.foreground.map}}});
  assert.equal(result.level_id,null);assert.ok(result.complete);assert.equal(result.scope_status,'complete');
});

test('all levels sort by declared sort/UUID without implicit viewed level and include empty/video media',async()=>{
  const f=fixture(),scene=f.scene();f.level(scene,'z',{sort:10});f.level(scene,'a',{sort:10,background:{src:'maps/movie.webm'}});
  f.level(scene,'empty',{sort:-1,background:{},foreground:{src:''}});
  const all=await f.call();assert.deepEqual(all.entries.map(e=>e.level_id),['empty','a','z']);
  assert.equal(all.entries[0].background.reference_status,'missing');assert.equal(all.entries[0].foreground.reference_status,'empty');
  assert.equal(all.entries[1].background.support_status,'unsupported_video');assert.equal(all.entries[1].background.info_next_call,null);
  const single=await f.call({level_id:'z'});assert.deepEqual(single.entries.map(e=>e.level_id),['z']);
  assert.notEqual(single.revision,all.revision);await assert.rejects(f.call({level_id:'foreign'}),error('LevelNotFound'));
});

test('gridless/hex and absent/null/zero configuration remain distinct',async()=>{
  const f=fixture(),scene=f.scene('one',{grid:{type:0,size:null,alpha:0,units:null}});f.level(scene);
  const result=await f.call();assert.deepEqual(result.grid,{type:0,size:null,alpha:0,units:null});
  scene.source.grid.type=4;delete scene.source.padding;scene.source.shiftX=null;
  const changed=await f.call();assert.equal(changed.grid.type,4);assert.ok(!Object.hasOwn(changed.geometry,'padding'));
  assert.equal(changed.geometry.shiftX,null);
});

test('media classification redacts signed/credential references and never guesses unsupported inputs',()=>{
  for(const value of ['https://bucket.example/a.webp?X-Amz-Signature=secret','https://user:secret@host/a.png']){
    const result=mapMedia(value);assert.equal(result.reference_status,'sensitive');assert.equal(result.reference,null);
    assert.equal(result.info_next_call,null);assert.ok(!JSON.stringify(result).includes('secret'));
  }
  for(const value of ['file:///tmp/a.png','data:image/svg+xml,unsafe','../a.png','maps/%2fsecret.png','maps/a.png#fragment']){
    assert.equal(mapMedia(value).reference_status,'unsupported');assert.equal(mapMedia(value).reference,null);
  }
  assert.equal(mapMedia('maps/α space.webp').reference,'maps/α space.webp');
  assert.equal(mapMedia('maps/document.pdf').support_status,'unsupported_reference');
});

test('tiles retain placement and declared membership; unknown selected-level applicability makes scope partial',async()=>{
  const f=fixture(),scene=f.scene();f.level(scene);f.level(scene,'other');
  f.tile(scene,'yes',{levels:['floor']});f.tile(scene,'no',{levels:['other']});f.tile(scene,'unknown',{levels:null});
  const result=await f.call({section:'tiles',level_id:'floor'});
  assert.deepEqual(result.entries.map(e=>e.tile_uuid),['Scene.one.Tile.unknown','Scene.one.Tile.yes']);
  assert.equal(result.scope_status,'partial');assert.equal(result.entries[1].placement.scaleY,-1);
  assert.equal(result.entries[1].placement.rotation,15);assert.equal(result.artwork.tiles,3);
  const assets=await f.call({level_id:'floor'});assert.equal(assets.revision,result.revision);
});

test('denied embedded data never serializes and produces truthful partial scope',async()=>{
  const f=fixture(),scene=f.scene();f.level(scene,'floor');const denied=f.level(scene,'secret',{name:'Private name'});denied.allowed=false;
  scene.tiles.invalidDocumentIds.add('private-invalid');
  const result=await f.call();assert.equal(result.scope_status,'partial');assert.equal(result.entries.length,1);
  assert.ok(!JSON.stringify(result).includes('Private name'));assert.ok(!JSON.stringify(result).includes('private-invalid'));
  await assert.rejects(f.call({level_id:'secret'}),error('PermissionDenied'));
  scene.allowed=false;await assert.rejects(f.call(),error('PermissionDenied'));
});

test('pagination follows exact cursors with changed bounds and rejects caller/filter/revision changes',async()=>{
  const f=fixture(),scene=f.scene();for(let i=0;i<5;i++)f.level(scene,'f'+i);
  const first=await f.call({limit:1});assert.equal(first.entries.length,1);assert.ok(!first.complete);
  const rest=await f.call({cursor:first.next_cursor,max_bytes:48000,limit:100});assert.equal(rest.entries.length,4);assert.ok(rest.complete);
  await assert.rejects(f.call({cursor:first.next_cursor,caller_key:'b'.repeat(64)}),error('InvalidCursor'));
  await assert.rejects(f.call({cursor:first.next_cursor,section:'tiles'}),error('InvalidCursor'));
  scene.levels.contents.pop();await assert.rejects(f.call({cursor:first.next_cursor}),error('ContentChanged'));
  await assert.rejects(f.call({expected_revision:first.revision}),error('ContentChanged'));
});

test('byte budgets include common metadata/cursor and complete levels; clipped names are marked',async()=>{
  const f=fixture(),scene=f.scene();for(let i=0;i<5;i++)f.level(scene,'f'+i,{name:'α'.repeat(300)});
  const page=await f.call({max_bytes:4000});assert.ok(size(page)<=4000);assert.ok(page.entries.length>0&&page.entries.length<5);
  assert.equal(page.entries[0].name_truncated,true);assert.equal(Array.from(page.entries[0].name).length,256);
  await assert.rejects(f.call({max_bytes:1024}),error('ResponseTooLarge'));
});

test('malformed inputs and stale socket guards precede source access',async()=>{
  const f=fixture(),scene=f.scene();f.level(scene);
  for(const params of [{section:'notes'},{scene_uuid:'Same map'},{level_id:true},{limit:true},{note_keys:['N1']}]){
    await assert.rejects(f.call(params),error('InvalidRequest'));
  }
  await assert.rejects(f.call({},()=>false),error('ContextChanged'));assert.equal(f.reads,0);
  game.user.isGM=false;await assert.rejects(f.call(),error('PermissionDenied'));assert.equal(f.reads,0);
});

test('sensitive asset reference replacement invalidates the selected map metadata revision',async()=>{
  const f=fixture(),scene=f.scene(),level=f.level(scene,'floor',{background:{src:'https://bucket/a.png?signature=first'}});
  const initial=await f.call();level.source.background.src='https://bucket/a.png?signature=replacement';
  await assert.rejects(f.call({expected_revision:initial.revision}),error('ContentChanged'));
});

test('encoded dot traversal is rejected before URL normalization hides it',()=>{
  for(const value of ['maps/%2e%2e/a.png','maps/%2e/a.png']){
    assert.equal(mapMedia(value).reference_status,'unsupported');
    assert.equal(mapMedia(value).reference,null);
  }
});

test('similarly named Scene copies retain folder ancestry and their own grid configuration',async()=>{
  const f=fixture(),a=f.scene('one',{folder:'original'}),b=f.scene('two',{folder:'chapter',grid:{type:1,size:100}});
  for(const [id,name] of [['original','Original Maps'],['chapter','Chapter']])f.folders.push({id,uuid:'Folder.'+id,type:'Scene',
    testUserPermission:()=>true,toObject:()=>({name,folder:null})});
  f.level(a);f.level(b);
  const first=await f.call(),second=await f.call({scene_uuid:'Scene.two'});
  assert.equal(first.scene.name,second.scene.name);assert.notEqual(first.scene.scene_uuid,second.scene.scene_uuid);
  assert.equal(first.scene.ancestry[0].name,'Original Maps');assert.equal(second.scene.ancestry[0].name,'Chapter');
  assert.equal(first.grid.size,180);assert.equal(second.grid.size,100);
});

test('context/permission mutation during hashing never publishes an old snapshot',async()=>{
  const f=fixture(),scene=f.scene();f.level(scene);
  const original=Object.getOwnPropertyDescriptor(globalThis,'crypto');
  let first=true;
  Object.defineProperty(globalThis,'crypto',{configurable:true,value:{subtle:{async digest(...args){const value=await webcrypto.subtle.digest(...args);
    if(first){first=false;scene.allowed=false;}return value;}}}});
  try{await assert.rejects(f.call(),error('PermissionDenied'));}
  finally{Object.defineProperty(globalThis,'crypto',original);}
});

test('an own undefined optional Tile name remains absent rather than failing the whole map',async()=>{
  const f=fixture(),scene=f.scene();f.level(scene);f.tile(scene,'art',{name:undefined});
  const result=await f.call({section:'tiles'});
  assert.equal(result.entries.length,1);assert.equal(Object.hasOwn(result.entries[0],'name'),false);
  assert.equal(result.entries[0].name_truncated,false);
});

test('an undefined optional level source is missing rather than an unsupported configured reference',async()=>{
  const f=fixture(),scene=f.scene();f.level(scene,'floor',{background:{src:undefined},foreground:{}});
  const result=await f.call();assert.equal(result.entries[0].background.reference_status,'missing');
  assert.equal(result.artwork.background_references,0);
});

test('Tile placement rotation survives undeclared texture rotation without publishing unsupported fields',async()=>{
  const f=fixture(),scene=f.scene();f.level(scene);f.tile(scene,'art',{rotation:15,texture:{src:'maps/a.png',rotation:90}});
  const result=await f.call({section:'tiles'});
  assert.equal(result.entries[0].placement.rotation,15);
  assert.equal(Object.hasOwn(result.entries[0].placement,'texture_rotation'),false);
});
