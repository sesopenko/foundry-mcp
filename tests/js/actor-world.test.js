import test from 'node:test';
import assert from 'node:assert/strict';
import { getActorTree,searchActors } from '../../foundry-module/scripts/actorWorld.js';

function fixture() {
  const folder=(id,name,parent=null)=>({id,uuid:`Folder.${id}`,name,type:'Actor',parentId:parent,testUserPermission(){return this.denied!==true;},toObject(source){assert.equal(source,true);return {folder:this.parentId};}});
  const a=folder('a','Alpha'); const b=folder('b','Nested','a');const empty=folder('empty','Empty');
  const actor=(id,name,type='npc',directory=null)=>({id,uuid:`Actor.${id}`,documentName:'Actor',name,type,folder:directory,compendium:null,testUserPermission(){return this.denied!==true;}});
  const first=actor('first','Guard','npc',a);const second=actor('second','GUARD','npc',b);const root=actor('root','Guard');const excluded=actor('loot','Guard','loot');
  globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},items:new Map(),folders:new Map([a,b,empty].map(f=>[f.id,f])),actors:new Map([first,second,root,excluded].map(a=>[a.id,a]))};
  return {a,b,empty,first,second,root,actor};
}
const errorCode=code=>error=>error.rpcError?.code===code;

test('tree preserves empty folders, preorder, depth and unfiled identities',async()=>{
  fixture();let result=await getActorTree({depth:1});
  assert.deepEqual(result.nodes.map(node=>node.kind==='folder'?node.id:node.identity.id),['a','empty','root']);
  assert.equal(result.nodes[0].children_complete,false);assert.deepEqual(result.nodes[0].expand,{folder_uuid:'Folder.a'});
  assert.equal(result.nodes[1].children_complete,true);assert.equal(result.tree_complete,false);
  result=await getActorTree({folder_uuid:'Folder.a',depth:2});
  assert.deepEqual(result.nodes.map(node=>node.kind==='folder'?node.id:node.identity.id),['b','second','first']);
  assert.equal(result.tree_complete,true);
  const nested=result.nodes[1];assert.equal(nested.parent_uuid,'Folder.b');assert.deepEqual(nested.folder_path.map(f=>f.id),['a','b']);
  assert.deepEqual(nested.next_call,{tool:'read_actor',arguments:{actor_uuid:'Actor.second'}});
  result=await getActorTree({folder_uuid:'Folder.empty'});assert.deepEqual(result.nodes,[]);assert.equal(result.pagination.complete,true);
});

test('literal search returns duplicate identities and explicit scoped meaning',async()=>{
  fixture();let result=await searchActors({query:'  gUaRd '});
  assert.deepEqual(result.nodes.map(node=>node.identity.id),['first','root','second']);
  assert.equal(result.scopes[0].id,'world');
  result=await searchActors({query:'guard',folder_uuid:'Folder.a',recursive:false});assert.deepEqual(result.nodes.map(node=>node.identity.id),['first']);
  result=await searchActors({query:'guard',folder_uuid:'Folder.a'});assert.equal(result.nodes.length,2);
  result=await searchActors({query:'.*'});assert.deepEqual(result.nodes,[]);assert.match(result.limitations[0],/literal/);
  result=await searchActors({query:'guard',types:['character']});assert.deepEqual(result.nodes,[]);
});

test('count, byte, continuation and revision limits remain independent',async()=>{
  const {actor}=fixture();game.actors=new Map(Array.from({length:40},(_,i)=>{const doc=actor(`id${i}`,'漢'.repeat(256));return [doc.id,doc];}));game.folders=new Map();
  const all=[];let cursor=null;
  do {const result=await getActorTree({limit:100,max_bytes:8000,cursor});assert.ok(Buffer.byteLength(JSON.stringify(result))<=8000);all.push(...result.nodes);cursor=result.pagination.next_cursor;}while(cursor);
  assert.equal(all.length,40);assert.equal(new Set(all.map(node=>node.identity.uuid)).size,40);
  let first=await searchActors({query:'漢',limit:1});
  await assert.rejects(searchActors({query:'漢',limit:2,cursor:first.pagination.next_cursor}),errorCode('CursorMismatch'));
  game.actors.get('id1').name='Changed';
  await assert.rejects(searchActors({query:'漢',limit:1,cursor:first.pagination.next_cursor}),errorCode('ContentChanged'));
});

test('permission and runtime boundaries do not expose denied identities',async()=>{
  const {a,first}=fixture();first.denied=true;
  let result=await searchActors({query:'guard'});assert.equal(result.nodes.length,2);assert.equal(result.scopes[0].status,'incomplete');assert.ok(!JSON.stringify(result).includes('Actor.first'));
  a.denied=true;await assert.rejects(getActorTree({folder_uuid:a.uuid}),errorCode('PermissionDenied'));
  result=await getActorTree();assert.ok(!JSON.stringify(result).includes('Folder.a'));assert.equal(result.scopes[0].status,'incomplete');
  game.system.id='other';await assert.rejects(searchActors({query:'guard'}),errorCode('UnsupportedSystem'));
  game.system.id='pf2e';game.version='13.0';await assert.rejects(getActorTree(),errorCode('UnsupportedVersion'));
  fixture();game.user.isGM=false;await assert.rejects(getActorTree(),errorCode('PermissionDenied'));
});

test('invalid requests, missing folders and containment cycles are explicit',async()=>{
  const {a,b}=fixture();
  for(const params of [{depth:0},{depth:true},{folder_uuid:'Alpha'},{unknown:1}])await assert.rejects(getActorTree(params),errorCode('InvalidRequest'));
  await assert.rejects(getActorTree({folder_uuid:'Folder.missing'}),errorCode('DocumentNotFound'));
  for(const params of [{query:''},{query:'x',types:[]},{query:'x',types:['npc','npc']},{query:'x',types:['loot']},{query:'x',recursive:'true'}])await assert.rejects(searchActors(params),errorCode('InvalidRequest'));
  a.parentId=b.id;await assert.rejects(getActorTree(),errorCode('ReadFailed'));
});

test('snapshot is rechecked after asynchronous digest',async()=>{
  const {root}=fixture();
  const pending=searchActors({query:'guard'});
  root.name='Changed';
  await assert.rejects(pending,errorCode('ContentChanged'));
});
