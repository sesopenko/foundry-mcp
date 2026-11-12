import test from 'node:test';
import assert from 'node:assert/strict';
import {webcrypto} from 'node:crypto';
import {browseMaps} from '../../foundry-module/scripts/mapBrowse.js';
import {handleRpcMessage} from '../../foundry-module/scripts/foundryBridge.js';

globalThis.crypto??=webcrypto;
const key='a'.repeat(64),rpcError=code=>error=>error.rpcError?.code===code;
const size=value=>new TextEncoder().encode(JSON.stringify(value)).length;
function fixture(){
  const state={folders:[],scenes:[],reads:0,permissions:0};
  const collection=list=>({contents:list,invalidDocumentIds:new Set(),get:id=>list.find(d=>d.id===id)});
  globalThis.game={ready:true,version:'14.369',world:{id:'test'},user:{id:'gm',isGM:true},system:{id:'dnd5e'},
    folders:collection(state.folders),scenes:collection(state.scenes)};
  globalThis.canvas=new Proxy({},{get(){throw Error('Canvas must not be read');}});
  function document(kind,id,name,parent=null,extra={}){
    const source={name,folder:parent,sort:0,...(kind==='folder'?{type:'Scene',sorting:'a'}:{}),...extra};
    const d={id,uuid:`${kind==='folder'?'Folder':'Scene'}.${id}`,type:source.type,source,allowed:true,
      testUserPermission(user,level){state.permissions++;assert.equal(user,game.user);assert.equal(level,'OBSERVER');return d.allowed;},
      toObject(original){assert.equal(original,true);assert.ok(d.allowed,'denied data must not be serialized');state.reads++;return structuredClone(source);},
      activate(){throw Error('Scene activation forbidden');},view(){throw Error('Scene view forbidden');}};
    (kind==='folder'?state.folders:state.scenes).push(d);return d;
  }
  state.folder=(...args)=>document('folder',...args);state.scene=(...args)=>document('map',...args);
  state.call=params=>browseMaps({caller_key:key,...params});return state;
}

test('root/nested folders preserve duplicates, manual order, named ancestry and empty/no-image maps',async()=>{
  const f=fixture();f.folder('chapter','Chapter',null,{sorting:'m'});f.folder('empty','Empty');
  f.folder('bonus1','Bonus Flip Mats','chapter',{sort:20});f.folder('bonus2','Bonus Flip Mats','chapter',{sort:10});
  f.scene('z','Same map','chapter',{sort:0});f.scene('a','Same map','chapter',{sort:-10,levels:[]});
  const root=await f.call({});assert.deepEqual(root.entries.map(e=>e.folder_uuid),['Folder.chapter','Folder.empty']);
  const nested=await f.call(root.entries[0].next_call.arguments);
  assert.deepEqual(nested.entries.map(e=>e.folder_uuid??e.scene_uuid),['Folder.bonus2','Folder.bonus1','Scene.a','Scene.z']);
  assert.deepEqual(nested.location.ancestry,[]);
  assert.ok(nested.entries.every(e=>e.ancestry[0].folder_uuid==='Folder.chapter'));
  assert.equal(nested.entries[2].image_status,'not_checked');
  assert.deepEqual(nested.entries[2].next_call,{tool:'get_map_info',arguments:{scene_uuid:'Scene.a'}});
  const empty=await f.call(root.entries[1].next_call.arguments);
  assert.equal(empty.total,0);assert.equal(empty.complete,true);assert.equal(empty.scope_status,'complete');
});

test('alphabetical ordering uses full names and UUID ties; literal matching is local and Unicode-safe',async()=>{
  const f=fixture();f.folder('parent','Parent');f.folder('child','Nested','parent');
  f.scene('b','Duplicate','parent',{sort:-10});f.scene('a','Duplicate','parent',{sort:100});
  f.scene('unicode','α River','parent');f.scene('hidden','α Deep','child');
  const page=await f.call({folder_uuid:'Folder.parent'});
  assert.deepEqual(page.entries.filter(e=>e.kind==='map'&&e.name==='Duplicate').map(e=>e.scene_uuid),['Scene.a','Scene.b']);
  const found=await f.call({folder_uuid:'Folder.parent',name_contains:'Α RIV'});
  assert.deepEqual(found.entries.map(e=>e.scene_uuid),['Scene.unicode']);
  assert.equal((await f.call({name_contains:'α'})).total,0);
});

test('denied documents and ancestry produce partial scope without reading names or serialization',async()=>{
  const f=fixture();const hidden=f.folder('hidden','Never expose this');hidden.allowed=false;
  f.scene('secret','Never expose child','hidden');const denied=f.scene('denied','Never expose map');denied.allowed=false;
  const page=await f.call({});assert.equal(page.scope_status,'partial');assert.equal(page.complete,true);assert.equal(page.total,0);
  assert.ok(!JSON.stringify(page).includes('Never expose'));
  await assert.rejects(f.call({folder_uuid:'Folder.hidden'}),rpcError('PermissionDenied'));
});

test('uninitialized world documents make empty streams partial without exposing their identifiers',async()=>{
  const f=fixture();game.scenes.invalidDocumentIds=new Set(['private-invalid-id']);
  const page=await f.call({});
  assert.equal(page.scope_status,'partial');assert.equal(page.complete,true);
  assert.ok(!JSON.stringify(page).includes('private-invalid-id'));
});

test('missing/non-Scene folders, orphan references and cycles fail explicitly',async()=>{
  const f=fixture();f.folder('journal','Journal',null,{type:'JournalEntry'});
  await assert.rejects(f.call({folder_uuid:'Folder.missing'}),rpcError('FolderNotFound'));
  await assert.rejects(f.call({folder_uuid:'Folder.journal'}),rpcError('InvalidFolder'));
  assert.equal(f.reads,0);
  f.folder('orphan','Orphan','missing');await assert.rejects(f.call({}),rpcError('InvalidHierarchy'));
  const g=fixture();g.folder('a','A','b');g.folder('b','B','a');await assert.rejects(g.call({}),rpcError('InvalidHierarchy'));
  const h=fixture();h.scene('orphan','Orphan','missing');await assert.rejects(h.call({}),rpcError('InvalidHierarchy'));
});

test('continuations allow changed bounds, bind caller/world/filter, and reject metadata/permission revisions',async()=>{
  const f=fixture();f.scene('a','Alpha');f.scene('b','Beta');f.scene('c','Gamma');
  const first=await f.call({limit:1});assert.equal(first.complete,false);
  const rest=await f.call({limit:100,max_bytes:48000,cursor:first.next_cursor});assert.equal(rest.complete,true);assert.equal(rest.entries.length,2);
  for(const change of [{caller_key:'b'.repeat(64)},{name_contains:'Alpha'},{folder_uuid:'Folder.any'}]){
    if(change.folder_uuid)f.folder('any','Any');
    await assert.rejects(f.call({...change,cursor:first.next_cursor}),rpcError('InvalidCursor'));
  }
  f.scenes[0].source.name='Changed';await assert.rejects(f.call({cursor:first.next_cursor}),rpcError('ContentChanged'));
  const fresh=await f.call({limit:1});f.scenes[1].allowed=false;
  await assert.rejects(f.call({cursor:fresh.next_cursor}),rpcError('ContentChanged'));
});

test('a shrinking catalog still reports changed revision rather than blaming a formerly valid offset',async()=>{
  const f=fixture();f.scene('a','A');f.scene('b','B');
  const first=await f.call({limit:1});f.scenes.splice(0);
  await assert.rejects(f.call({cursor:first.next_cursor}),rpcError('ContentChanged'));
});

test('UTF8 budget includes all metadata/cursors; names clip with markers while filtering uses full text',async()=>{
  const f=fixture();f.scene('long','🌊'.repeat(300)+'UNIQUE_END');f.scene('short','Other');
  const filtered=await f.call({name_contains:'unique_end'});
  assert.equal(filtered.entries.length,1);assert.equal(Array.from(filtered.entries[0].name).length,256);
  assert.equal(filtered.entries[0].name_truncated,true);
  await assert.rejects(f.call({max_bytes:1024,name_contains:'unique_end'}),rpcError('ResponseTooLarge'));
  const first=await f.call({limit:1});const exact=size(first);
  assert.ok(exact>1024);
  assert.equal(size(await f.call({limit:1,max_bytes:exact})),exact);
  await assert.rejects(f.call({limit:1,max_bytes:exact-1}),rpcError('ResponseTooLarge'));
});

test('request and context guards precede reads; actual bridge dispatch forwards its socket guard',async()=>{
  const f=fixture();f.folder('one','One');
  for(const params of [{limit:true},{max_bytes:1000},{name_contains:1},{folder_uuid:'Scene.one'},{cursor:12},{extra:true}])
    await assert.rejects(f.call(params),rpcError('InvalidRequest'));
  assert.equal(f.reads,0);
  game.user.isGM=false;await assert.rejects(f.call({}),rpcError('PermissionDenied'));assert.equal(f.reads,0);
  game.user.isGM=true;
  const response=await handleRpcMessage({id:'rpc',method:'browseMaps',params:{caller_key:key}},()=>false);
  assert.equal(response.error.code,'ContextChanged');assert.equal(f.reads,0);
  const success=await handleRpcMessage({id:'rpc2',method:'browseMaps',params:{caller_key:key}},()=>true);
  assert.equal(success.result.entries[0].folder_uuid,'Folder.one');
});

test('permission and world/socket changes while hashing cannot publish a stale page',async()=>{
  const f=fixture();f.scene('a','Alpha');let checks=0;
  await assert.rejects(browseMaps({caller_key:key},()=>++checks===1),rpcError('ContextChanged'));
});

test('permission changes during asynchronous hashing invalidate the detached metadata snapshot',async()=>{
  const f=fixture(),scene=f.scene('a','Private after denial');
  const original=crypto.subtle.digest;
  crypto.subtle.digest=async function(...args){const value=await original.apply(this,args);scene.allowed=false;return value;};
  try{await assert.rejects(f.call({}),rpcError('ContentChanged'));}
  finally{crypto.subtle.digest=original;}
});
