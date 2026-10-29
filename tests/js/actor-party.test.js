import test from 'node:test';
import assert from 'node:assert/strict';
import {getPartyMembers} from '../../foundry-module/scripts/actorParty.js';

function fixture() {
  const actors = new Map();
  function add(id, type = 'character', members = []) {
    const source = {type, system: {details: {members: members.map(uuid => ({uuid}))}}};
    const actor = {id, uuid: 'Actor.' + id, type, name: 'Same name', documentName: 'Actor',
      testUserPermission() {return !this.denied;},
      toObject(basis) {assert.equal(basis, true); assert.equal(type, 'party'); return structuredClone(source);}};
    Object.defineProperty(actor, 'members', {get() {throw Error('Prepared members forbidden');}});
    actors.set(id, actor);
    return {actor, source};
  }
  globalThis.game = {ready: true, version: '14.369', system: {id: 'pf2e', version: '8.6.1'},
    user: {isGM: true}, actors, items: new Map()};
  add('one'); add('two'); add('npc', 'npc'); add('spare');
  const party = add('party', 'party', ['Actor.one', 'Actor.two', 'Actor.npc']);
  return {...party, add};
}
const code = value => error => error.rpcError?.code === value;

test('official membership, not all characters; source preserved, only party source read', async () => {
  const {source} = fixture(), before = JSON.stringify(source);
  const result = await getPartyMembers();
  assert.equal(result.mode, 'members');
  assert.equal(result.party.uuid, 'Actor.party');
  assert.equal(result.scope_status, 'complete');
  assert.equal(result.pagination.complete, true);
  assert.deepEqual(result.entries.map(e => e.identity.uuid), ['Actor.one', 'Actor.two', 'Actor.npc']);
  assert.equal(result.entries.filter(e => e.identity.type === 'character').length, 2);
  assert.deepEqual(result.entries[0].next_call, {tool: 'read_actor', arguments: {actor_uuid: 'Actor.one'}});
  assert.equal(JSON.stringify(source), before);
});

test('multiple, empty, missing, inaccessible and explicitly selected parties differ', async () => {
  const {add} = fixture(); add('other', 'party');
  let result = await getPartyMembers();
  assert.equal(result.mode, 'parties');
  assert.deepEqual(result.entries.map(e => e.identity.uuid), ['Actor.other', 'Actor.party']);
  assert.deepEqual(result.entries[0].next_call, {tool: 'get_party_members', arguments: {party_uuid: 'Actor.other'}});
  result = await getPartyMembers({party_uuid: 'Actor.other'});
  assert.equal(result.mode, 'members'); assert.deepEqual(result.entries, []);
  assert.equal(result.scope_status, 'complete');
  game.actors.get('other').denied = true;
  result = await getPartyMembers(); assert.equal(result.party.uuid, 'Actor.party');
  game.actors.get('party').denied = true;
  result = await getPartyMembers(); assert.equal(result.mode, 'parties');
  assert.equal(result.scope_status, 'partial'); assert.deepEqual(result.entries, []);
  await assert.rejects(getPartyMembers({party_uuid: 'Actor.other'}), code('PermissionDenied'));
  game.actors.delete('other'); game.actors.delete('party');
  result = await getPartyMembers(); assert.equal(result.scope_status, 'complete');
  assert.deepEqual(result.entries, []);
  await assert.rejects(getPartyMembers({party_uuid: 'Actor.party'}), code('DocumentNotFound'));
  await assert.rejects(getPartyMembers({party_uuid: 'Actor.one'}), code('UnsupportedType'));
});

test('missing/denied/unsupported claims and duplicates remain explicit without denied identity leakage', async () => {
  const {source, add} = fixture();
  add('vehicle', 'vehicle'); game.actors.get('two').denied = true;
  Object.defineProperty(game.actors.get('two'), 'name', {get() {throw Error('Denied name');}});
  source.system.details.members.push(...['Actor.missing', 'Compendium.pack.Actor.a', 'Actor.vehicle', 'Actor.one'].map(uuid => ({uuid})));
  const result = await getPartyMembers();
  assert.equal(result.scope_status, 'partial');
  assert.deepEqual(result.entries.map(e => e.status), ['resolved', 'denied', 'resolved', 'missing', 'unsupported', 'unsupported']);
  assert.deepEqual(result.reasons, ['duplicate_member_references', 'member_denied', 'member_missing', 'member_unsupported']);
  assert.equal(result.entries[1].identity, null); assert.equal(result.entries[1].next_call, null);
  assert.ok(!JSON.stringify(result).includes('Actor.two'));
  assert.ok(!JSON.stringify(result).includes('Compendium.pack'));
  assert.equal(result.entries[5].identity.type, 'vehicle');
});

test('pagination reconstructs roster once and respects UTF-8 byte budget', async () => {
  const {source, add} = fixture();
  source.system.details.members = [];
  for (let i = 0; i < 30; i++) {
    const {actor} = add('long' + i); actor.name = '漢'.repeat(300);
    source.system.details.members.push({uuid: actor.uuid});
  }
  let cursor = null; const entries = [];
  for (let calls = 0; calls < 10; calls++) {
    const result = await getPartyMembers({limit: 100, cursor});
    assert.ok(Buffer.byteLength(JSON.stringify(result)) <= 8000);
    entries.push(...result.entries); cursor = result.pagination.next_cursor;
    if (result.pagination.complete) break;
  }
  assert.equal(cursor, null); assert.equal(entries.length, 30);
  assert.equal(new Set(entries.map(e => e.identity.uuid)).size, 30);
  assert.ok(entries.every(e => e.identity.name_truncated));
});

test('continuations bind selection/bounds and changes in membership, names and access', async () => {
  for (const change of ['membership', 'name', 'permission', 'new-party']) {
    const {source, add} = fixture();
    const first = await getPartyMembers({limit: 1});
    for (const params of [{limit: 2}, {limit: 1, max_bytes: 9000}, {limit: 1, party_uuid: 'Actor.party'}]) {
      await assert.rejects(getPartyMembers({...params, cursor: first.pagination.next_cursor}), code('CursorMismatch'));
    }
    if (change === 'membership') source.system.details.members.pop();
    if (change === 'name') game.actors.get('two').name = 'Changed';
    if (change === 'permission') game.actors.get('two').denied = true;
    if (change === 'new-party') add('another', 'party');
    await assert.rejects(getPartyMembers({limit: 1, cursor: first.pagination.next_cursor}), code('ContentChanged'));
  }
});

test('invalid requests and malformed membership never appear empty; runtime admission enforced', async () => {
  const {source} = fixture();
  for (const params of [{unknown: 1}, {party_uuid: 'party'}, {party_uuid: 'Actor.a.b'}, {limit: true}, {limit: 0}, {max_bytes: 7999}]) {
    await assert.rejects(getPartyMembers(params), code('InvalidRequest'));
  }
  await assert.rejects(getPartyMembers({cursor: 'bad'}), code('InvalidCursor'));
  for (const claims of [null, {}, [{uuid: 3}], Array(201).fill({uuid: 'Actor.one'})]) {
    source.system.details.members = claims;
    await assert.rejects(getPartyMembers(), code('ReadFailed'));
  }
  fixture(); game.system.id = 'other'; await assert.rejects(getPartyMembers(), code('UnsupportedSystem'));
  fixture(); game.version = '13'; await assert.rejects(getPartyMembers(), code('UnsupportedVersion'));
  fixture(); game.user.isGM = false; await assert.rejects(getPartyMembers(), code('PermissionDenied'));
  fixture(); game.ready = false; await assert.rejects(getPartyMembers(), code('NotReady'));
});

test('mutation across an asynchronous digest is detected before response', async () => {
  const {actor, source} = fixture(); let reads = 0;
  actor.toObject = () => {
    const value = structuredClone(source);
    if (++reads === 1) source.system.details.members.pop();
    return value;
  };
  await assert.rejects(getPartyMembers(), code('ContentChanged'));
});
