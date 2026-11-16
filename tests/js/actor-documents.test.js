import test from 'node:test';
import assert from 'node:assert/strict';
import { ready, actorTarget, itemTarget } from '../../foundry-module/scripts/actorDocuments.js';

function fixture() {
  const docs = new Map();
  const document = (uuid, kind, type) => {
    const value = { uuid, id: uuid.split('.').at(-1), name: 'Duplicate', type, documentName: kind, parent: null, folder: null, compendium: null, testUserPermission: () => true, items: new Map() };
    docs.set(uuid, value); return value;
  };
  const a = document('Actor.a', 'Actor', 'npc');
  const b = document('Actor.b', 'Actor', 'npc');
  const item = document('Actor.a.Item.i', 'Item', 'action'); item.parent = a; a.items.set('i', item);
  const scene = document('Scene.s', 'Scene');
  const token = document('Scene.s.Token.t', 'Token'); token.parent = scene; token.actor = b; token.baseActor = a; token.isLinked = false;
  globalThis.game = { version: '14.369', ready: true, system: {id: 'pf2e', version: '8.6.1'}, user: {isGM:true}, actors: new Map([['a',a],['b',b]]), items:new Map() };
  globalThis.foundry = {utils:{fromUuid: async uuid => docs.get(uuid)}};
  return {document, a,b,item,scene,token};
}

test('supported core and PF2e updates retain actual runtime identity', () => {
  fixture();
  for (const core of ['14.369', '14.370', '14.999']) {
    for (const system of ['8.6.1', '8.7.0', '8.99.12']) {
      game.version = core; game.system.version = system;
      assert.deepEqual(ready(), {core_version: core, system_id: 'pf2e', system_version: system});
    }
  }
});

test('version floors, major boundaries and malformed versions fail before document reads', () => {
  fixture();
  for (const [core, system] of [
    ['14.368', '8.7.0'], ['13.999', '8.7.0'], ['15.0', '8.7.0'],
    ['14.370', '8.6.0'], ['14.370', '8.5.99'], ['14.370', '9.0.0'],
    ...['', '14', '14.370-beta', '014.370', '14.370.0.1', '14.99999999999999999999', null, 14.370].map(v => [v, '8.7.0']),
    ...['', '8', '8.7.0-dev', '8.07.0', '8.7.0\n', null, 8.7].map(v => ['14.370', v]),
  ]) {
    game.version = core; game.system.version = system;
    assert.throws(() => ready(), /require Foundry/, `${core}/${system}`);
  }
});

test('world, compendium and token identities preserve canonical context and membership', async () => {
  const {document,a,b,item,token} = fixture(); ready();
  assert.equal((await actorTarget({actor_uuid:a.uuid})).identity.uuid,a.uuid);
  assert.equal((await itemTarget({item_uuid:item.uuid})).identity.actor.uuid,a.uuid);
  const synthetic = document('Scene.s.Token.t.Actor.b.Item.i','Item','action'); synthetic.parent=b; b.items.set('i',synthetic);
  const result=await itemTarget({item_uuid:synthetic.uuid,token_uuid:token.uuid});
  assert.equal(result.identity.source_kind,'token'); assert.equal(result.identity.uuid,synthetic.uuid);
  assert.equal(result.identity.instance.base_actor.uuid,a.uuid);
  await assert.rejects(itemTarget({item_uuid:item.uuid,token_uuid:token.uuid}),/does not belong/);
  await assert.rejects(itemTarget({item_uuid:synthetic.uuid}),/require token_uuid/);
  token.actor=a; token.isLinked=true;
  assert.equal((await itemTarget({item_uuid:item.uuid,token_uuid:token.uuid})).identity.instance.actor_link,true);
  const pack=document('Compendium.pf2e.example.Actor.p','Actor','npc');
  pack.compendium={collection:'pf2e.example',title:'Examples',testUserPermission:()=>true};
  assert.equal((await actorTarget({actor_uuid:pack.uuid})).identity.pack.id,'pf2e.example');
  pack.compendium.testUserPermission=()=>false;
  await assert.rejects(actorTarget({actor_uuid:pack.uuid}),/not readable/);
});

test('readiness, system/version, type and permission failures stay explicit',async()=>{
  const {a,item,scene,token}=fixture();
  game.ready=false; assert.throws(()=>ready(),/not ready/);game.ready=true;
  game.user.isGM=false;assert.throws(()=>ready(),/connected GM/);game.user.isGM=true;
  game.system.id='other';assert.throws(()=>ready(),/require PF2e/);game.system.id='pf2e';
  game.version='13.0';assert.throws(()=>ready(),/require Foundry/);game.version='14.369';
  await assert.rejects(actorTarget({actor_uuid:a.uuid,token_uuid:token.uuid}),/exactly one/);
  await assert.rejects(actorTarget({actor_uuid:'Duplicate'}),/world\/pack/);
  a.testUserPermission=()=>false;await assert.rejects(itemTarget({item_uuid:item.uuid}),/not readable/);a.testUserPermission=()=>true;
  a.type='hazard';await assert.rejects(actorTarget({actor_uuid:a.uuid}),/no supported/);a.type='npc';
  scene.testUserPermission=()=>false;await assert.rejects(actorTarget({token_uuid:token.uuid}),/not readable/);scene.testUserPermission=()=>true;
  token.actor=null;await assert.rejects(actorTarget({token_uuid:token.uuid}),/unavailable/);
  await assert.rejects(actorTarget({actor_uuid:'Actor.missing'}),/no longer exists/);
});
