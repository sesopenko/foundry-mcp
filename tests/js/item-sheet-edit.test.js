import test from 'node:test';
import assert from 'node:assert/strict';
import {editItem} from '../../foundry-module/scripts/itemSheet.js';
import {world} from './fixtures/item-sheet-world.js';

const args={item_uuid:'Item.blade',changes:{publication:{remaster:false},header:{name:'Blade'}}};
const apply=(args,preview)=>editItem({...args,mode:'apply',expected_revision:preview.revision});

test('preview is inert, invalid compound proposals are atomic, successful apply makes one update',async()=>{
  const {source,writes}=world();
  for(const bad of [{details:{range:55}},{rules:[]},{header:{name:'Fine',flags:{}}}]){
    await assert.rejects(()=>editItem({...args,changes:{...args.changes,...bad}}));
    assert.equal(writes.length,0);
  }
  const p=await editItem(args);assert.equal(writes.length,0);
  assert.equal(p.changes.length,2);
  const r=await apply(args,p);
  assert.equal(r.status,'applied');assert.equal(writes.length,1);assert.equal(source.name,'Blade');
  assert.deepEqual(writes[0],{name:'Blade','system.publication.remaster':false});
  assert.equal((await apply(args,await editItem(args))).status,'unchanged');assert.equal(writes.length,1);
  assert.ok(Buffer.byteLength(JSON.stringify(r))<=8000);assert.equal(r.next_call.tool,'read_item');
});
test('stale sources, changed choices, altered proposal and concurrent applies cannot overwrite',async()=>{
  const {source,writes}=world();
  const req={...args,changes:{header:{traits:['finesse']}}};
  const p=await editItem(req);source.name='external';
  await assert.rejects(()=>apply(req,p),/changed/);
  source.name='Dogslicer';CONFIG.PF2E.weaponTraits.world='World';
  await assert.rejects(()=>apply(req,p),/changed/);
  const fresh=await editItem(req);
  await assert.rejects(()=>apply({...req,changes:{header:{traits:[]}}},fresh),/changed/);
  assert.equal(writes.length,0);
  const results=await Promise.allSettled([apply(req,fresh),apply(req,fresh)]);
  assert.equal(results.filter(r=>r.status==='fulfilled').length,1);assert.equal(writes.length,1);
});
test('embedded write goes to the exact owner; unverified dispatch returns reconciliation error',async()=>{
  const {item,doc}=world();
  const actor=doc('Actor.a','Actor',{type:'npc',items:new Map()});game.actors.set('a',actor);
  const owned=doc('Actor.a.Item.i','Item',{...item,uuid:'Actor.a.Item.i',id:'i',parent:actor});
  actor.items.set('i',owned);let calls=0;
  actor.updateEmbeddedDocuments=async(type,updates)=>{
    assert.equal(type,'Item');assert.equal(updates.length,1);assert.equal(updates[0]._id,'i');calls++;
    return [owned]; // hook withheld the change
  };
  const req={...args,item_uuid:owned.uuid};const p=await editItem(req);
  await assert.rejects(()=>apply(req,p),e=>e.rpcError.code==='WriteOutcomeUnknown');
  assert.equal(calls,1);
});

test('apply rechecks option domains even when they change during its last asynchronous resolution',async()=>{
  const {writes}=world();const req={...args,changes:{header:{traits:['finesse']}}};
  const p=await editItem(req);
  const resolve=foundry.utils.fromUuid;let reads=0;
  foundry.utils.fromUuid=async uuid=>{
    if(++reads===3)delete CONFIG.PF2E.weaponTraits.finesse;
    return resolve(uuid);
  };
  await assert.rejects(()=>apply(req,p),/changed/);assert.equal(writes.length,0);
});

test('oversized previews and apply receipts fail before any dispatch',async()=>{
  const {writes}=world();
  const traits=Array.from({length:98},(_,i)=>'hb-'+String(i)+'a'.repeat(110));
  for(const t of traits)CONFIG.PF2E.weaponTraits[t]=t;
  const req={...args,changes:{header:{traits}}};
  for(const p of [req,{...req,mode:'apply',expected_revision:'stale'}]){
    await assert.rejects(()=>editItem(p),e=>e.rpcError.code==='ResponseTooLarge');
  }
  assert.equal(writes.length,0);
});
