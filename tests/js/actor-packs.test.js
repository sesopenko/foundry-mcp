import test from 'node:test';
import assert from 'node:assert/strict';
import {listActorCompendiums,searchCompendiumActors} from '../../foundry-module/scripts/actorPacks.js';

const code=expected=>error=>error.rpcError?.code===expected;
function fixture() {
  const pack=(id,documentName='Actor',entries=[])=>({collection:id,title:`Title ${id}`,documentName,visible:false,locked:true,entries,calls:0,
    testUserPermission(user,permission){assert.equal(permission,'OBSERVER');return !this.denied;},
    getUuid(id){return `Compendium.${this.collection}.${this.documentName}.${id}`;},
    async getIndex(options){this.calls++;assert.deepEqual(options,{fields:['name','type']});if(this.failed)throw Error('private secret');return new Map(this.entries.map((entry,i)=>[i,entry]));},
    getDocuments(){throw Error('Bulk retrieval forbidden');},getDocument(){throw Error('Hydration forbidden during search');},importAll(){throw Error('Import forbidden');},contents:[]});
  const a=pack('scope.with.segments.pack','Actor',[{_id:'a',name:'Guard',type:'npc'},{_id:'b',name:'GUARD',type:'npc'},{_id:'excluded',name:'Guard',type:'loot'}]);
  const b=pack('other.pack','Actor',[{_id:'c',name:'Guard',type:'character'}]);
  const item=pack('items.pack','Item',[{_id:'spell',name:'Fire',type:'spell'}]);
  globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map(),items:new Map(),packs:new Map([a,b,item].map(pack=>[pack.collection,pack]))};
  return {a,b,item,pack};
}

test('flat pack listing requires permission, preserves IDs, and never reads indexes',async()=>{
  const {a,b,item}=fixture();b.denied=true;
  const result=await listActorCompendiums();assert.equal(result.nodes.length,1);assert.equal(result.nodes[0].id,a.collection);
  assert.equal(result.nodes[0].visible,false);assert.equal(result.nodes[0].folder,null);assert.equal(result.nodes[0].next_call,null);
  assert.match(result.nodes[0].limitations[0],/search_compendium_actors/);assert.equal(result.scopes[0].status,'incomplete');assert.equal(a.calls,0);
  const items=await listActorCompendiums({document_type:'Item',query:'ITEMS.PACK'});assert.equal(items.nodes[0].id,item.collection);
});

test('explicit index search retains duplicates, canonical Foundry UUIDs and scopes',async()=>{
  const {a,b}=fixture();
  const result=await searchCompendiumActors({pack_ids:[a.collection,b.collection],query:'  guArd '});
  assert.equal(result.nodes.length,3);assert.equal(a.calls,2);assert.equal(b.calls,2);
  const duplicate=result.nodes.filter(node=>node.identity.pack.id===a.collection);assert.equal(duplicate.length,2);
  assert.equal(duplicate[0].identity.uuid,a.getUuid('a'));
  assert.deepEqual(duplicate[0].next_call,{tool:'read_actor',arguments:{actor_uuid:a.getUuid('a')}});
  assert.ok(result.scopes.every(scope=>scope.status==='searched'));
  assert.deepEqual((await searchCompendiumActors({pack_ids:[a.collection],query:'[Guard]'})).nodes,[]);
});

test('partial failures and unknown index type cannot masquerade as absence',async()=>{
  const {a,b}=fixture();a.entries.push({_id:'unknown',name:'Guard'});b.failed=true;
  const result=await searchCompendiumActors({pack_ids:[a.collection,b.collection,'missing.pack'],query:'guard'});
  assert.deepEqual(result.scopes.map(scope=>scope.status),['failed','failed','incomplete']);
  assert.equal(result.nodes.length,2);assert.ok(!JSON.stringify(result).includes('private secret'));
  b.failed=false;b.denied=true;
  const denied=await searchCompendiumActors({pack_ids:[b.collection],query:'guard'});assert.equal(denied.scopes[0].status,'denied');assert.deepEqual(denied.nodes,[]);
});

test('Item scope, filters and unknown requests are validated',async()=>{
  const {a,item}=fixture();
  const result=await searchCompendiumActors({pack_ids:[item.collection],document_type:'Item',query:'fire',types:['spell']});
  assert.equal(result.nodes[0].kind,'item');assert.deepEqual(result.nodes[0].next_call,{tool:'read_item',arguments:{item_uuid:item.getUuid('spell')}});
  for(const params of [{pack_ids:[],query:'x'},{pack_ids:[a.collection,a.collection],query:'x'},{pack_ids:[a.collection],query:''},{pack_ids:[a.collection],query:'x',types:['loot']},{pack_ids:[a.collection],query:'x',unknown:true},{pack_ids:[a.collection],query:'x',document_type:'JournalEntry'}])await assert.rejects(searchCompendiumActors(params),code('InvalidRequest'));
  const wrong=await searchCompendiumActors({pack_ids:[item.collection],query:'fire'});assert.equal(wrong.scopes[0].status,'failed');
});

test('count/byte pagination and selected index revisions are bound',async()=>{
  const {a}=fixture();a.entries=Array.from({length:30},(_,i)=>({_id:`id${i}`,name:'漢'.repeat(256),type:'npc'}));
  let cursor;const all=[];
  do {const result=await searchCompendiumActors({pack_ids:[a.collection],query:'漢',limit:100,max_bytes:8000,cursor});assert.ok(Buffer.byteLength(JSON.stringify(result))<=8000);all.push(...result.nodes);cursor=result.pagination.next_cursor;}while(cursor);
  assert.equal(all.length,30);assert.equal(new Set(all.map(node=>node.identity.uuid)).size,30);
  const first=await searchCompendiumActors({pack_ids:[a.collection],query:'漢',limit:1});
  await assert.rejects(searchCompendiumActors({pack_ids:[a.collection],query:'other',limit:1,cursor:first.pagination.next_cursor}),code('CursorMismatch'));
  a.entries[1].name='Changed';
  await assert.rejects(searchCompendiumActors({pack_ids:[a.collection],query:'漢',limit:1,cursor:first.pagination.next_cursor}),code('ContentChanged'));
});

test('permission and pack identity are rechecked after index await',async()=>{
  const {a}=fixture();const original=a.getIndex;
  a.getIndex=async function(options){const result=await original.call(this,options);this.denied=true;return result;};
  await assert.rejects(searchCompendiumActors({pack_ids:[a.collection],query:'guard'}),code('ContentChanged'));
  fixture();game.system.id='other';await assert.rejects(listActorCompendiums(),code('UnsupportedSystem'));
});

test('Python forwarded optional nulls use the documented defaults',async()=>{
  const {a,item}=fixture();
  for(const document_type of ['Actor','Item']) {
    const listing=await listActorCompendiums({document_type,query:null,limit:50,max_bytes:48000,cursor:null});
    assert.ok(listing.nodes.length>0);
    const result=await searchCompendiumActors({document_type,pack_ids:[document_type==='Actor'?a.collection:item.collection],query:document_type==='Actor'?'guard':'fire',types:null,limit:50,max_bytes:48000,cursor:null});
    assert.ok(result.nodes.length>0);
  }
  await assert.rejects(listActorCompendiums({document_type:null}),code('InvalidRequest'));
  await assert.rejects(searchCompendiumActors({pack_ids:[a.collection],query:null}),code('InvalidRequest'));
});
