import test from 'node:test';
import assert from 'node:assert/strict';
import { readJournalPage, resolveJournalReference } from '../../foundry-module/scripts/journals.js';

const readable = { testUserPermission: () => true };
const collection = values => ({ contents: values, size: values.length, get: id => values.find(value => value.id === id) });
function fixture() {
  const entry = { ...readable, id:'j', uuid:'JournalEntry.j', name:'Notes', folder:null };
  const page = { ...readable, id:'p', uuid:'JournalEntry.j.JournalEntryPage.p', parent:entry, type:'text', name:'Clue', text:{content:'',markdown:'',format:1} };
  entry.pages = collection([page]);
  const actor = { ...readable, id:'a', uuid:'Actor.a', documentName:'Actor', type:'npc', name:'Same name', items:new Map() };
  const item = { ...readable, id:'i', uuid:'Actor.a.Item.i', documentName:'Item', type:'action', name:'Ability', parent:actor };
  actor.items.set(item.id,item);
  const pack = { ...readable, collection:'test.actors', title:'Creatures' };
  const packed = { ...actor, id:'b', uuid:'Compendium.test.actors.Actor.b', compendium:pack };
  const scene = { ...readable, documentName:'Scene', uuid:'Scene.s', name:'Encounter' };
  const token = { ...readable, documentName:'Token', uuid:'Scene.s.Token.t', name:'Instance', parent:scene, isLinked:false, baseActor:actor };
  const synthetic = { ...actor, uuid:'Scene.s.Token.t.Actor.a', token, items:new Map() };
  const owned = { ...item, uuid:'Scene.s.Token.t.Actor.a.Item.i', parent:synthetic };
  synthetic.items.set(owned.id,owned); token.actor=synthetic;
  const docs = new Map([actor,item,packed,token,synthetic,owned].map(doc=>[doc.uuid,doc]));
  docs.set('.relative',actor);
  const calls=[];
  globalThis.game = { ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},journal:collection([entry]),folders:collection([]),actors:new Map(),items:new Map() };
  globalThis.foundry = {utils:{fromUuidSync:()=>null,fromUuid:async(uuid,options)=>{calls.push({uuid,options});return docs.get(uuid)??null;}}};
  const resolve = (target,source='html') => {
    page.text[source==='html'?'content':'markdown']=`@UUID[${target}]{Same name}`;
    return resolveJournalReference({page_uuid:page.uuid,target,source});
  };
  return {entry,page,actor,item,pack,packed,scene,token,synthetic,owned,docs,calls,resolve};
}

test('journal reference metadata is lazy, fragment bounded and preserves original targets',async()=>{
  const f=fixture();
  f.page.text.content='@UUID[Actor.a#heading]{Same name} @UUID[Actor.a#heading]{Duplicate} @UUID[Item.'+'x'.repeat(513)+']';
  const read=await readJournalPage({page_uuid:f.page.uuid});
  assert.equal(read.content,f.page.text.content);assert.equal(f.calls.length,0);
  assert.equal(read.references.length,3);
  assert.deepEqual(read.references[0].resolve_next_call,{tool:'resolve_journal_reference',arguments:{page_uuid:f.page.uuid,target:'Actor.a#heading',source:'html'}});
  assert.deepEqual(read.references[0].resolve_next_call,read.references[1].resolve_next_call);
  assert.equal(read.references[2].resolve_next_call,null);
  f.page.text.content='@UUID[Actor.a] '.repeat(25);
  const bounded=await readJournalPage({page_uuid:f.page.uuid});
  assert.equal(bounded.references.length,20);assert.equal(bounded.references_complete,false);assert.equal(f.calls.length,0);
  const split=await readJournalPage({page_uuid:f.page.uuid,max_chars:5});assert.deepEqual(split.references,[]);
});

test('relative, absolute, packed and embedded targets yield canonical typed next calls',async()=>{
  const f=fixture();
  for(const [target,uuid,tool] of [['.relative#one#two',f.actor.uuid,'read_actor'],[f.actor.uuid,f.actor.uuid,'read_actor'],[f.packed.uuid,f.packed.uuid,'read_actor'],[f.item.uuid,f.item.uuid,'read_item']]) {
    f.calls.length=0;
    const result=await f.resolve(target);
    assert.equal(result.status,'resolved');assert.equal(result.identity.uuid,uuid);assert.equal(result.next_call.tool,tool);
    assert.equal(f.calls[0].uuid,target.split('#')[0]);assert.equal(f.calls[0].options.relative,f.page);
    assert.equal(result.anchor,target.includes('#')?'one#two':null);
    assert.deepEqual(Object.keys(result).sort(),['foundry_version','page_uuid','source','target','anchor','status','identity','next_call'].sort());
  }
  const result=await f.resolve(f.actor.uuid,'markdown');assert.equal(result.source,'markdown');
  const read=await readJournalPage({page_uuid:f.page.uuid,source:'markdown'});assert.equal(read.references[0].resolve_next_call.arguments.source,'markdown');
});

test('token and synthetic owned targets preserve exact current instance selectors',async()=>{
  const f=fixture();
  for(const target of [f.token.uuid,f.synthetic.uuid,f.owned.uuid]) {
    const result=await f.resolve(target);assert.equal(result.status,'resolved');
    assert.equal(result.identity.instance.token_uuid,f.token.uuid);
    assert.equal(result.next_call.arguments.token_uuid,f.token.uuid);
    if(target===f.owned.uuid)assert.equal(result.next_call.arguments.item_uuid,f.owned.uuid);
    else assert.equal(result.next_call.tool,'read_actor');
  }
  f.token.actor=f.actor;
  assert.equal((await f.resolve(f.owned.uuid)).status,'unverified');
});

test('missing, denied, unsupported and failed targets withhold identities and remain local',async()=>{
  const f=fixture();
  assert.equal((await f.resolve('Actor.missing')).status,'missing');
  for(const doc of [f.actor,f.pack]) {
    doc.testUserPermission=()=>false;
    const result=await f.resolve(doc===f.pack?f.packed.uuid:f.item.uuid);
    assert.equal(result.status,'denied');assert.equal(result.identity,null);assert.equal(result.next_call,null);
    doc.testUserPermission=()=>true;
  }
  f.actor.type='hazard';assert.equal((await f.resolve(f.actor.uuid)).status,'unsupported');f.actor.type='npc';
  game.system.id='other';assert.equal((await f.resolve(f.actor.uuid)).status,'unsupported');game.system.id='pf2e';
  game.version='13.1';assert.equal((await f.resolve(f.actor.uuid)).status,'unsupported');game.version='14.369';
  f.docs.set('.journal',{...readable,documentName:'JournalEntry'});assert.equal((await f.resolve('.journal')).status,'outside_scope');
  foundry.utils.fromUuid=async()=>{throw Error('pack unavailable');};
  assert.equal((await f.resolve(f.packed.uuid)).status,'unverified');
});

test('origin admission rejects arbitrary targets and rechecks source and permissions after awaits',async()=>{
  const f=fixture();
  await assert.rejects(resolveJournalReference({page_uuid:f.page.uuid,target:'Actor.a'}),error=>error.rpcError.type==='ReferenceChanged');
  f.page.text.markdown='@UUID[Actor.a]';
  await assert.rejects(resolveJournalReference({page_uuid:f.page.uuid,target:'Actor.a',source:'html'}),error=>error.rpcError.type==='ReferenceChanged');
  assert.equal(f.calls.length,0);
  f.entry.testUserPermission=()=>false;
  await assert.rejects(f.resolve('Actor.a'),error=>error.rpcError.type==='PermissionDenied');f.entry.testUserPermission=()=>true;
  foundry.utils.fromUuid=async()=>{f.page.text.content='changed';return f.actor;};
  await assert.rejects(f.resolve('Actor.a'),error=>error.rpcError.type==='ReferenceChanged');
  foundry.utils.fromUuid=async()=>{f.page.testUserPermission=()=>false;return f.actor;};
  await assert.rejects(f.resolve('Actor.a'),error=>error.rpcError.type==='PermissionDenied');
  f.page.testUserPermission=()=>true;game.user.isGM=false;
  await assert.rejects(f.resolve('Actor.a'),error=>error.rpcError.type==='GMRequired');
});

test('permissions and origin source remain checked after the selected reader resolves again',async()=>{
  const f=fixture();let calls=0;
  foundry.utils.fromUuid=async()=>{if(++calls===2)f.page.text.content='removed';return f.actor;};
  await assert.rejects(f.resolve('Actor.a'),error=>error.rpcError.type==='ReferenceChanged');
  calls=0;
  foundry.utils.fromUuid=async()=>{if(++calls===2)f.actor.testUserPermission=()=>false;return f.actor;};
  const denied=await f.resolve('Actor.a');assert.equal(denied.status,'denied');assert.equal(denied.identity,null);
  f.actor.testUserPermission=()=>true;
  foundry.utils.fromUuid=async uuid=>f.docs.get(uuid);
  f.scene.testUserPermission=()=>false;
  assert.equal((await f.resolve(f.token.uuid)).status,'denied');
});
