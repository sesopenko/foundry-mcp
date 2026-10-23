import test from 'node:test';
import assert from 'node:assert/strict';
import { readActor, getActorTypes } from '../../foundry-module/scripts/actors.js';

function fixture(context = 'world', type = 'npc') {
  const source = { name: 'Creature', type, system: { attributes: { ac: { value: 15 }, hp: { value: 9, max: 20, temp: 0 } } } };
  const current = { name: 'Creature', type, system: {
    abilities: Object.fromEntries(['str', 'dex', 'con', 'int', 'wis', 'cha'].map(key => [key, { mod: 3, base: 2 }])),
    attributes: { ac: { value: 23, breakdown: 'current AC', details: '' }, hp: { value: 5, max: 35, temp: 4 } },
    saves: Object.fromEntries(['fortitude', 'reflex', 'will'].map(key => [key, { value: 10, totalModifier: 11, breakdown: 'current save', rank: 2 }])),
    perception: { value: 12, totalModifier: 13, breakdown: 'current Perception', vision: true, rank: 1 },
    movement: { speeds: Object.fromEntries(['land', 'burrow', 'climb', 'fly', 'swim', 'travel'].map(mode => [mode, ['land', 'travel'].includes(mode) ? { value: 30, base: 25, type: mode, source: null } : null])) },
  } };
  let permitted = true;
  const calls = [];
  const actor = { documentName: 'Actor', uuid: 'Actor.a', id: 'a', name: 'Creature', type, items: new Map(), folder: null, compendium: null,
    testUserPermission: () => permitted, toObject(flag) { calls.push(flag); return structuredClone(flag ? source : current); },
    getRollData() { throw Error('roll data prohibited'); }, prepareData() { throw Error('preparation prohibited'); }, update() { throw Error('writes prohibited'); } };
  Object.defineProperty(actor, 'system', { get() { throw Error('runtime data prohibited'); } });
  const docs = new Map(); let selector;
  if (context === 'pack') { actor.uuid = 'Compendium.pf2e.example.Actor.a'; actor.compendium = { collection: 'pf2e.example', title: 'Examples', testUserPermission: () => permitted }; }
  selector = { actor_uuid: actor.uuid };
  let token;
  if (context === 'token') {
    const base = { documentName: 'Actor', id: 'base', uuid: 'Actor.base', name: 'Base', type, testUserPermission: () => true };
    const scene = { documentName: 'Scene', id: 's', uuid: 'Scene.s', name: 'Scene', testUserPermission: () => true };
    token = { documentName: 'Token', id: 't', uuid: 'Scene.s.Token.t', name: 'Token', parent: scene, actor, baseActor: base, isLinked: false, testUserPermission: () => true };
    actor.uuid = 'Scene.s.Token.t.Actor.a'; docs.set(scene.uuid, scene); docs.set(token.uuid, token); selector = { token_uuid: token.uuid };
  }
  docs.set(actor.uuid, actor);
  globalThis.game = { ready: true, version: '14.369', system: { id: 'pf2e', version: '8.6.1' }, user: { isGM: true }, actors: new Map([['a', actor]]), items: new Map() };
  globalThis.foundry = { utils: { fromUuid: async uuid => docs.get(uuid) } };
  return { source, current, actor, calls, selector, token, setPermission(value) { permitted = value; } };
}
async function all(selector, sections) {
  const pages = []; let cursor;
  do { const page = await readActor({ ...selector, sections, limit: 5, max_bytes: 8000, ...(cursor ? { cursor } : {}) }); pages.push(page); assert.ok(Buffer.byteLength(JSON.stringify(page)) <= 8000); cursor = page.pagination.next_cursor; assert.ok(pages.length < 100); } while (cursor);
  return { pages, rows: pages.flatMap(page => page.records) };
}
const field = (rows, section, path) => rows.find(row => row.section === section && row.raw[0]?.path === path);

test('world, pack and synthetic reads separate source and transformed values with canonical provenance', async () => {
  for (const context of ['world', 'pack', 'token']) {
    const f = fixture(context), { pages, rows } = await all(f.selector, ['source', 'statistics']);
    for (const [path, stored, transformed, concept] of [['/system/attributes/ac/value', 15, 23, 'current_armor_class'], ['/system/attributes/hp/value', 9, 5, 'current_hit_points']]) {
      const source = field(rows, 'source', path), current = field(rows, 'statistics', path);
      assert.equal(source.raw[0].value, stored); assert.equal(source.raw[0].basis, 'source');
      assert.equal(current.raw[0].value, transformed); assert.equal(current.raw[0].basis, 'transformed');
      assert.equal(current.raw[0].document_uuid, f.actor.uuid); assert.equal(current.mapped.concept, concept); assert.equal(current.mapped.value, transformed);
      assert.equal(current.provenance.mapping, 'pf2e.actor.current.v1');
      assert.deepEqual(current.provenance.contributors, [{ document_uuid: f.actor.uuid, path, basis: 'transformed' }]);
      assert.deepEqual(current.provenance.limitations, ['serialized_current_value_not_target_context']);
      assert.notEqual(current.key, source.key);
    }
    assert.equal(pages[0].identity.source_kind, context === 'pack' ? 'compendium' : context);
    if (context === 'token') { assert.equal(pages[0].identity.instance.token_uuid, f.token.uuid); assert.equal(pages[0].identity.instance.base_actor.uuid, 'Actor.base'); }
    assert.ok(f.calls.includes(true) && f.calls.includes(false));
  }
});

test('source-only reads do not request transformed serialization; current missing data never falls back', async () => {
  const f = fixture(); await all(f.selector, ['source']); assert.ok(f.calls.every(flag => flag === true));
  delete f.current.system.attributes.ac.value;
  const { pages, rows } = await all(f.selector, ['statistics']);
  const ac = field(rows, 'statistics', '/system/attributes/ac/value'); assert.equal(ac.raw[0].present, false); assert.equal(Object.hasOwn(ac.raw[0], 'value'), false);
  assert.ok(pages.at(-1).sections.find(section => section.name === 'statistics').reasons.includes('current_fields_unavailable'));
  assert.equal(f.source.system.attributes.ac.value, 15);
});

test('current changes invalidate continuations even when persisted source is unchanged', async () => {
  for (const mutate of [f => f.current.system.attributes.ac.value++, f => f.current.system.attributes.hp.value++, f => f.current.system.perception.totalModifier++, f => f.actor.name = 'Changed']) {
    const f = fixture(), before = JSON.stringify(f.source), params = { ...f.selector, sections: ['statistics'], limit: 1 };
    const first = await readActor(params); assert.ok(first.pagination.next_cursor); mutate(f);
    assert.equal(JSON.stringify(f.source), before);
    await assert.rejects(readActor({ ...params, cursor: first.pagination.next_cursor }), error => error.rpcError.code === 'ContentChanged');
  }
  const f = fixture(), params = { ...f.selector, sections: ['statistics'], limit: 1 }, first = await readActor(params);
  f.setPermission(false);
  await assert.rejects(readActor({ ...params, cursor: first.pagination.next_cursor }), error => error.rpcError.code === 'PermissionDenied');
});

test('familiar statistics stay explicitly unsupported without transformed reads', async () => {
  const f = fixture('world', 'familiar'), result = await readActor({ ...f.selector, sections: ['statistics'] });
  assert.deepEqual(result.records, []);
  assert.deepEqual(result.sections.find(section => section.name === 'statistics'), { name: 'statistics', status: 'unsupported', reasons: ['master_current_contract_pending'] });
  assert.ok(f.calls.every(flag => flag === true));
});

test('malformed serialization and runtime admission boundaries fail safely', async () => {
  for (const mutate of [f => f.current.system.attributes.hp.max = 'secret', f => f.current.system.movement.speeds.land.type = 'fly', f => f.current.type = 'character']) {
    const f = fixture(); mutate(f);
    await assert.rejects(readActor({ ...f.selector, sections: ['statistics'] }), error => error.rpcError.code === 'ReadFailed' && !error.message.includes('secret'));
  }
  const getterFixture=fixture();let getterCalls=0;
  Object.defineProperty(getterFixture.current,'type',{get(){getterCalls++;return 'npc';}});
  getterFixture.actor.toObject=flag=>flag?structuredClone(getterFixture.source):getterFixture.current;
  await assert.rejects(readActor({...getterFixture.selector,sections:['statistics']}),error=>error.rpcError.code==='ReadFailed');
  assert.equal(getterCalls,0);
  for (const [mutate, code] of [[() => game.system.id = 'other', 'UnsupportedSystem'], [() => game.ready = false, 'NotReady'], [() => game.user.isGM = false, 'PermissionDenied']]) {
    const f = fixture(); mutate(); await assert.rejects(readActor({ ...f.selector, sections: ['statistics'] }), error => error.rpcError.code === code); assert.deepEqual(f.calls, []);
  }
  const f = fixture(); f.actor.type = 'hazard';
  await assert.rejects(readActor({ ...f.selector, sections: ['statistics'] }), error => error.rpcError.code === 'UnsupportedType');
});

test('statistics count and byte limits reject requests before serialization', async () => {
  const f = fixture();
  for (const limits of [{ limit: 0 }, { limit: 101 }, { max_bytes: 7999 }, { max_bytes: 48001 }]) await assert.rejects(readActor({ ...f.selector, sections: ['statistics'], ...limits }), error => error.rpcError.code === 'InvalidRequest');
  assert.deepEqual(f.calls, []);
});

test('discovery scopes effective flags to partial character/NPC statistics and the verified runtime', async () => {
  fixture();
  const registry=await getActorTypes();
  const statistics=registry.actor_sections.find(section=>section.name==='statistics');
  assert.equal(statistics.source_supported,false);
  assert.equal(statistics.mapped_supported,true);
  assert.equal(statistics.effective_supported,true);
  assert.match(statistics.limitations.join(' '),/Always partial/);
  assert.match(statistics.limitations.join(' '),/Familiar current statistics remain unsupported/);
  for(const type of ['character','npc'])assert.equal(registry.actor_types.find(actor=>actor.type===type).effective_supported,true);
  assert.equal(registry.actor_types.find(actor=>actor.type==='familiar').effective_supported,false);
  game.system.id='other';
  const unsupported=await getActorTypes();
  assert.equal(unsupported.availability.supported,false);
  assert.equal(unsupported.actor_sections.find(section=>section.name==='statistics').effective_supported,false);
});
