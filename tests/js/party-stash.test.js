import test from 'node:test';
import assert from 'node:assert/strict';
import * as parties from '../../foundry-module/scripts/actorParty.js';
import {readItem, readActor} from '../../foundry-module/scripts/actors.js';

export function fixture() {
  const actors = new Map(), docs = new Map(), sources = new Map();
  function addParty(id = 'party') {
    const actor = {id, uuid: 'Actor.' + id, name: 'Same party', type: 'party', documentName: 'Actor',
      parent: null, compendium: null, items: new Map(), testUserPermission() { return !this.denied; },
      toObject() { throw Error('Stash must not read party or member source'); }};
    for (const key of ['inventory', 'members', 'sheet']) Object.defineProperty(actor, key, {get() { throw Error('Forbidden prepared state'); }});
    actors.set(id, actor); docs.set(actor.uuid, actor); return actor;
  }
  const party = addParty();
  function add(id, type = 'equipment', system = {}, owner = party) {
    const source = {name: 'Stored ' + id, type, system}; sources.set(id, source);
    const item = {id, uuid: owner.uuid + '.Item.' + id, name: 'Prepared name', type, documentName: 'Item',
      parent: owner, compendium: null, folder: null, testUserPermission() { return !this.denied; },
      toObject(basis) { assert.equal(basis, true); return structuredClone(source); }};
    owner.items.set(id, item); docs.set(item.uuid, item); return item;
  }
  add('bag', 'backpack', {quantity: 1, containerId: null});
  add('coins', 'treasure', {quantity: 0, containerId: 'bag', price: {value: {gp: 1}, per: 1}});
  add('missing');
  globalThis.game = {ready: true, version: '14.369', system: {id: 'pf2e', version: '8.6.1'}, user: {isGM: true}, actors, items: new Map()};
  globalThis.foundry = {utils: {fromUuid: async uuid => docs.get(uuid)}};
  return {party, add, addParty, sources};
}
const code = expected => error => error.rpcError?.code === expected;
const get = args => { assert.equal(typeof parties.getPartyStash, 'function', 'stash handler must be implemented'); return parties.getPartyStash(args); };

test('stash reads actual party-owned physical Items with source quantity and reusable identities', async () => {
  const f = fixture(), before = JSON.stringify([...f.sources]);
  const result = await get({party_uuid: f.party.uuid});
  assert.equal(result.mode, 'stash'); assert.equal(result.scope_status, 'complete');
  assert.equal(result.party.uuid, f.party.uuid); assert.equal(result.basis, 'source');
  assert.deepEqual(result.entries.map(e => e.identity.name), ['Stored bag', 'Stored coins', 'Stored missing']);
  assert.deepEqual(result.entries[1].quantity, {present: true, value: 0});
  assert.deepEqual(result.entries[2].quantity, {present: false});
  assert.equal('container' in result.entries[0], false);
  for (const row of result.entries) {
    assert.deepEqual(row.next_call, {tool: 'read_item', arguments: {item_uuid: row.identity.uuid}});
    const read = await readItem({...row.next_call.arguments, sections: ['source']});
    assert.equal(read.identity.actor.type, 'party'); assert.equal(read.identity.actor.uuid, f.party.uuid);
  }
  assert.equal(JSON.stringify([...f.sources]), before);
  await assert.rejects(readActor({actor_uuid: f.party.uuid}), code('UnsupportedType'));
});

test('select precedes paging; byte limits and full traversal retain every identity exactly once', async () => {
  fixture(); const rows = []; let cursor, calls = 0;
  do {
    const result = await get({limit: 1, select: {quantity: false, container: true, follow_up: false}, ...(cursor ? {cursor} : {})});
    assert.ok(new TextEncoder().encode(JSON.stringify(result)).length <= 8000); calls++;
    for (const row of result.entries) { assert.equal('quantity' in row, false); assert.equal('next_call' in row, false); }
    rows.push(...result.entries); cursor = result.pagination.next_cursor;
  } while (cursor && calls < 5);
  assert.equal(calls, 3); assert.equal(cursor, null);
  assert.equal(new Set(rows.map(r => r.identity.uuid)).size, 3);
  assert.deepEqual(rows[1].container, {present: true, value: 'bag'});
  const first = await get({limit: 1});
  await assert.rejects(get({limit: 1, cursor: first.pagination.next_cursor, select: {quantity: false}}), code('CursorMismatch'));
});

test('UTF-8 budget pages heavy Unicode identities without losing entries or stable selectors', async () => {
  const f = fixture();
  for (let i = 0; i < 20; i++) {
    f.add('long' + String(i).padStart(2, '0'));
    f.sources.get('long' + String(i).padStart(2, '0')).name = '😀'.repeat(300);
  }
  const uuids = []; let cursor, calls = 0, sawByteBound = false;
  do {
    const page = await get(cursor ? {cursor} : {});
    assert.ok(new TextEncoder().encode(JSON.stringify(page)).length <= 8000);
    assert.ok(page.entries.length <= 10);
    sawByteBound ||= !page.pagination.complete && page.entries.length < 10;
    for (const entry of page.entries) {
      uuids.push(entry.identity.uuid);
      if (entry.identity.uuid.includes('.Item.long')) {
        assert.equal([...entry.identity.name].length, 256);
        assert.equal(entry.identity.name_truncated, true);
      }
    }
    cursor = page.pagination.next_cursor; calls++;
  } while (cursor && calls < 10);
  assert.equal(cursor, null); assert.equal(sawByteBound, true);
  assert.equal(uuids.length, 23); assert.equal(new Set(uuids).size, 23);
});

test('denied Items never disclose identity or source; campaign Items are explicitly excluded', async () => {
  const f = fixture(), denied = f.add('secret'); denied.denied = true;
  for (const key of ['name', 'uuid']) Object.defineProperty(denied, key, {get() {throw Error('Denied identity');}});
  denied.toObject = () => {throw Error('Denied source');};
  const campaign = f.add('campaign', 'campaignFeature'); campaign.toObject = () => {throw Error('Campaign source');};
  const result = await get({});
  assert.equal(result.scope_status, 'partial');
  assert.deepEqual(result.reasons, ['stash_items_denied', 'stash_nonphysical_excluded']);
  assert.equal(result.entries.length, 3); assert.ok(!JSON.stringify(result).includes('secret'));
});

test('party discovery, empty and denied scopes remain distinct', async () => {
  const f = fixture(); const other = f.addParty('other');
  let result = await get({}); assert.equal(result.mode, 'parties'); assert.equal(result.entries.length, 2);
  assert.deepEqual(result.entries[0].next_call, {tool: 'get_party_stash', arguments: {party_uuid: other.uuid}});
  result = await get({party_uuid: other.uuid}); assert.equal(result.mode, 'stash'); assert.deepEqual(result.entries, []);
  other.denied = true; f.party.denied = true;
  result = await get({}); assert.equal(result.scope_status, 'partial'); assert.deepEqual(result.reasons, ['parties_denied']);
  await assert.rejects(get({party_uuid: other.uuid}), code('PermissionDenied'));
  await assert.rejects(get({party_uuid: 'Actor.gone'}), code('DocumentNotFound'));
});

test('stale source, membership, permission and identity invalidate continuation', async () => {
  for (const change of ['quantity', 'container', 'membership', 'permission', 'name']) {
    const f = fixture(), first = await get({limit: 1, select: {container: true}});
    if (change === 'quantity') f.sources.get('coins').system.quantity++;
    if (change === 'container') f.sources.get('coins').system.containerId = null;
    if (change === 'membership') f.party.items.delete('coins');
    if (change === 'permission') f.party.items.get('coins').denied = true;
    if (change === 'name') f.sources.get('coins').name = 'Changed';
    await assert.rejects(get({limit: 1, select: {container: true}, cursor: first.pagination.next_cursor}), code('ContentChanged'));
  }
});

test('invalid inputs, malformed source, runtime and ownership fail closed', async () => {
  const f = fixture();
  for (const args of [{party_uuid: 'Name'}, {party_uuid: 'Actor.party\n'}, {limit: true}, {max_bytes: 48001}, {select: {unknown: true}}, {select: {quantity: 1}}, {unknown: true}])
    await assert.rejects(get(args), code('InvalidRequest'));
  f.sources.get('coins').system.quantity = '0'; await assert.rejects(get({}), code('ReadFailed'));
  fixture(); game.system.id = 'other'; await assert.rejects(get({}), code('UnsupportedSystem'));
  fixture(); game.user.isGM = false; await assert.rejects(get({}), code('PermissionDenied'));
  const fresh = fixture(); fresh.party.items.get('bag').parent = null;
  await assert.rejects(get({}), code('ReadFailed'));
});

test('world party admission cannot enable campaign, pack, detached or token party Item reads', async () => {
  for (const change of ['campaign', 'pack', 'detached', 'token']) {
    const f = fixture(), item = f.party.items.get('coins');
    if (change === 'campaign') item.type = 'campaignFeature';
    if (change === 'pack') f.party.compendium = {testUserPermission: () => true};
    if (change === 'detached') f.party.items.delete('coins');
    if (change === 'token') f.party.parent = {documentName: 'Token'};
    await assert.rejects(readItem({item_uuid: item.uuid, sections: ['source']}), code('UnsupportedType'));
  }
});

test('scope change across asynchronous hashing rejects the entire read', async () => {
  const f = fixture(), previous = Object.getOwnPropertyDescriptor(globalThis, 'crypto');
  Object.defineProperty(globalThis, 'crypto', {configurable: true, value: {subtle: {digest: async () => {
    f.party.denied = true; return new Uint8Array(32).buffer;
  }}}});
  try { await assert.rejects(get({party_uuid: f.party.uuid}), code('PermissionDenied')); }
  finally {if (previous) Object.defineProperty(globalThis, 'crypto', previous); else delete globalThis.crypto;}
});
