import test from 'node:test';
import assert from 'node:assert/strict';
import { getActorTypes, readActor, readItem, listActorItems } from '../../foundry-module/scripts/actors.js';
import { handleRpcMessage } from '../../foundry-module/scripts/foundryBridge.js';

function fixture() {
  const docs=new Map();
  const make=(uuid,documentName,type,system={})=>{
    const source={name:'Duplicate',type,system,flags:{private_secret:'never'},_migration:{secret:'never'}};
    const d={uuid,id:uuid.split('.').at(-1),name:source.name,type,documentName,parent:null,folder:null,compendium:null,items:new Map(),
      testUserPermission:()=>true,toObject(sourceFlag){assert.equal(sourceFlag,true);return structuredClone(source);}};
    docs.set(uuid,d);return {d,source};
  };
  const {d:actor,source:actorSource}=make('Actor.a','Actor','npc',{attributes:{hp:{value:17}},_migration:{secret:'never'}});
  const {d:item,source:itemSource}=make('Actor.a.Item.i','Item','action',{description:{value:'<p>Source 😀 &amp; @UUID[Actor.a]</p>',gm:'never'},rules:[{secret:'never'}]});
  item.parent=actor;actor.items.set(item.id,item);
  globalThis.game={version:'14.369',system:{id:'pf2e',version:'8.6.1'},ready:true,user:{isGM:true},actors:new Map([['a',actor]]),items:new Map()};
  globalThis.foundry={utils:{fromUuid:async uuid=>docs.get(uuid)},documents:{Actor:{TYPES:['character','npc','familiar','loot']},Item:{TYPES:['action','campaignFeature']}}};
  return {make,actor,actorSource,item,itemSource};
}

test('source reads preserve identities and exclude migration, flags and unselected system data',async()=>{
  const {actor,item}=fixture();
  const a=await readActor({actor_uuid:actor.uuid});
  assert.equal(a.identity.uuid,actor.uuid);assert.equal(a.sections.find(s=>s.name==='source').status,'partial');
  assert.deepEqual(a.records.slice(0,2).map(r=>r.raw[0].path),['/name','/type']);
  assert.equal(a.records.find(r=>r.raw[0].path==='/system/attributes/hp/value').raw[0].value,17);
  assert.ok(!JSON.stringify(a).includes('private_secret'));assert.equal(a.pagination.complete,true);
  const i=await readItem({item_uuid:item.uuid,sections:['identity','source','effective']});
  assert.equal(i.identity.actor.uuid,actor.uuid);assert.equal(i.sections.at(-1).status,'unsupported');
  assert.ok(!JSON.stringify(i).includes('never'));assert.ok(!JSON.stringify(a).includes('never'));
  await assert.rejects(readActor({actor_uuid:actor.uuid,extra:true}),/Unknown input/);
  await assert.rejects(readActor({actor_uuid:actor.uuid,limit:true}),/integer/);
  await assert.rejects(readItem({item_uuid:item.uuid,sections:['source','source']}),/unique/);
});

test('exact description text, byte limits and cursor continuation survive escaped Unicode',async()=>{
  const {item,itemSource}=fixture();
  itemSource.system.description.value='<p>\n😀 &amp; " \\ \u0000</p>'.repeat(900);
  let cursor;let text='';let count=0;
  do {
    const r=await readItem({item_uuid:item.uuid,sections:['description'],limit:2,max_bytes:8000,...(cursor?{cursor}:{})});
    assert.ok(Buffer.byteLength(JSON.stringify(r))<=8000);count++;
    for(const record of r.records){assert.equal(record.text.start,text.length);text+=record.raw[0].value;assert.equal(record.text.end,text.length);}
    cursor=r.pagination.next_cursor;
    assert.ok(count<200);
  } while(cursor);
  assert.equal(text,itemSource.system.description.value);
  const first=await readItem({item_uuid:item.uuid,sections:['description'],limit:1});
  await assert.rejects(readItem({item_uuid:item.uuid,sections:['description'],limit:2,cursor:first.pagination.next_cursor}),/inputs differ/);
  itemSource.system.description.value+='changed';
  await assert.rejects(readItem({item_uuid:item.uuid,sections:['description'],limit:1,cursor:first.pagination.next_cursor}),/changed/);
  delete itemSource.system.description.value;
  const missing=await readItem({item_uuid:item.uuid,sections:['description']});
  assert.equal(missing.records[0].raw[0].present,false);assert.ok(!Object.hasOwn(missing.records[0].raw[0],'value'));
});

test('discovery registry distinguishes planned mappings and unsupported runtime without coercion',async()=>{
  fixture();const result=await getActorTypes();
  assert.equal(result.actor_types.find(t=>t.type==='loot').in_scope,false);
  assert.equal(result.item_types.find(t=>t.type==='campaignFeature').source_supported,false);
  assert.equal(result.actor_types.find(t=>t.type==='npc').mapped_supported,true);
  assert.match(result.actor_types.find(t=>t.type==='npc').limitations[0],/Lore references/);
  assert.equal(result.item_types.find(t=>t.type==='action').mapped_supported,true);
  assert.equal(result.item_types.find(t=>t.type==='melee').mapped_supported,true);
  assert.equal(result.item_sections.find(t=>t.name==='relationships').source_supported,true);
  game.system.id='other';assert.equal((await getActorTypes()).availability.supported,false);
  await assert.rejects(readActor({actor_uuid:'Actor.a'}),/require PF2e/);
  game.system.id='pf2e';
  foundry.documents.Actor.TYPES=Array.from({length:200},(_,i)=>`custom${i}`);
  await assert.rejects(getActorTypes(),/registry response budget/);
});

test('owned Item navigation preserves duplicates, scope and continuation membership',async()=>{
  const {make,actor}=fixture();
  const {d:second}=make('Actor.a.Item.j','Item','action');second.parent=actor;actor.items.set(second.id,second);
  const {d:unknown}=make('Actor.a.Item.u','Item','campaignFeature');unknown.parent=actor;actor.items.set(unknown.id,unknown);
  const first=await listActorItems({actor_uuid:actor.uuid,limit:1});
  assert.equal(first.unsupported_count,1);assert.equal(first.pagination.complete,false);
  assert.equal(first.nodes[0].next_call.tool,'read_item');
  const secondPage=await listActorItems({actor_uuid:actor.uuid,limit:1,cursor:first.pagination.next_cursor});
  assert.equal(secondPage.pagination.complete,true);assert.notEqual(secondPage.nodes[0].identity.uuid,first.nodes[0].identity.uuid);
  actor.items.delete('j');await assert.rejects(listActorItems({actor_uuid:actor.uuid,limit:1,cursor:first.pagination.next_cursor}),/changed/);
  await assert.rejects(listActorItems({actor_uuid:actor.uuid,types:['unknown']}),/in-scope/);
});

test('mid-read source changes and permission revocation cannot produce stale or unauthorized data',async()=>{
  const {actor,actorSource,item}=fixture();let reads=0;
  const original=actor.toObject;
  actor.toObject=function(flag){reads++;if(reads===2)actorSource.name='Changed';return original.call(this,flag);};
  await assert.rejects(readActor({actor_uuid:actor.uuid}),/changed during/);
  actor.toObject=original;
  item.testUserPermission=()=>false;await assert.rejects(readItem({item_uuid:item.uuid}),/not readable/);
  await assert.rejects(readActor({actor_uuid:'Actor.missing'}),/no longer exists/);
});

test('new foundation handlers are registered in the same RPC dispatch boundary',async()=>{
  fixture();
  const result=await handleRpcMessage({id:'reader',method:'readActor',params:{actor_uuid:'Actor.a'}});
  assert.equal(result.result?.identity.uuid,'Actor.a');
  const invalid=await handleRpcMessage({id:'reader',method:'readActor',params:{actor_uuid:'Actor.a',extra:true}});
  assert.equal(invalid.error.code,'InvalidRequest');
});
