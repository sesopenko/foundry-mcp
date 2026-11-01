import test from 'node:test';
import assert from 'node:assert/strict';
import {webcrypto} from 'node:crypto';
import {browseJournalImages} from '../../foundry-module/scripts/journalImages.js';

globalThis.crypto ??= webcrypto;
const code = value => error => error.rpcError?.code === value;
function fixture() {
  const state = {calls: [], result: {target: 'assets', dirs: ['assets/sub folder'], files: ['assets/α image.png', 'assets/other.webp']}};
  globalThis.game = {ready: true, version: '14.369', world: {id: 'test'}, user: {isGM: true}};
  class Picker {
    constructor() {this.sources = {data: {target: ''}, public: {target: ''}};}
    static async browse(...args) {state.calls.push(args); if (state.error) throw state.error; return state.result;}
  }
  globalThis.foundry = {applications: {apps: {FilePicker: {implementation: Picker}}}};
  return state;
}

test('image paths and directory followups paginate with exact source selectors', async () => {
  const f = fixture();
  const first = await browseJournalImages({directory: 'assets', limit: 1});
  assert.equal(first.total, 3); assert.equal(first.complete, false);
  assert.deepEqual(first.entries[0].next_call, {tool: 'browse_journal_images', arguments: {source: 'data', directory: 'assets/sub folder'}});
  const rest = await browseJournalImages({directory: 'assets', cursor: first.next_cursor});
  assert.equal(rest.complete, true); assert.equal(rest.entries.length, 2);
  const unicode = rest.entries.find(entry => entry.name === 'α image.png');
  assert.deepEqual(unicode.image, {source: 'data', directory: 'assets', src: 'assets/α image.png'});
  assert.deepEqual(f.calls[0], ['data', 'assets', {extensions: ['.apng','.avif','.bmp','.gif','.jpeg','.jpg','.png','.svg','.tiff','.webp'], wildcard: false}]);
});

test('literal filtering matches full names and changed listings/selections invalidate continuation', async () => {
  const f = fixture(), first = await browseJournalImages({directory: 'assets', limit: 1});
  f.result.files.push('assets/new.png');
  await assert.rejects(browseJournalImages({directory: 'assets', cursor: first.next_cursor}), code('ContentChanged'));
  await assert.rejects(browseJournalImages({directory: 'assets', name_contains: 'other', cursor: first.next_cursor}), code('ContentChanged'));
  f.result.files = ['assets/' + 'x'.repeat(270) + 'suffix.png']; f.result.dirs = [];
  const filtered = await browseJournalImages({directory: 'assets', name_contains: 'suffix'});
  assert.equal(filtered.total, 1); assert.equal(filtered.entries[0].name_truncated, true);
  assert.ok(filtered.entries[0].image.src.endsWith('suffix.png'));
});

test('invalid path/source/GM requests fail before any native browse', async () => {
  const f = fixture();
  for (const directory of ['../private', '%2e%2e/private', '/etc', 'C:\\private', 'assets/*', 'https://example.org/'])
    await assert.rejects(browseJournalImages({directory}), code('InvalidRequest'));
  await assert.rejects(browseJournalImages({source: 's3'}), code('InvalidRequest'));
  await assert.rejects(browseJournalImages({bucket: 'not-applicable'}), code('InvalidRequest'));
  game.user.isGM = false;
  await assert.rejects(browseJournalImages({}), code('PermissionDenied'));
  assert.equal(f.calls.length, 0);
});

test('missing/denied, empty, malformed and oversized native listings remain distinct', async () => {
  const f = fixture(); f.error = Error('Private host details');
  await assert.rejects(browseJournalImages({}), error => code('BrowseFailed')(error) && !JSON.stringify(error.rpcError).includes('Private host'));
  f.error = null; f.result = {target: '', dirs: [], files: []};
  const empty = await browseJournalImages({}); assert.equal(empty.complete, true); assert.equal(empty.total, 0);
  f.result.files = ['javascript:unsafe.png'];
  await assert.rejects(browseJournalImages({}), code('ReadFailed'));
  f.result.files = Array.from({length: 10001}, (_,i) => `assets/${i}.png`);
  await assert.rejects(browseJournalImages({}), code('DirectoryTooLarge'));
});

test('byte-bound pages preserve long canonical paths and exact continuation', async () => {
  const f = fixture(); f.result.dirs = [];
  f.result.files = Array.from({length: 10}, (_,i) => 'assets/' + 'x'.repeat(2000) + i + '.png');
  const pages = [], entries = []; let cursor;
  do {
    const page = await browseJournalImages({directory: 'assets', ...(cursor ? {cursor} : {})});
    assert.ok(new TextEncoder().encode(JSON.stringify(page)).length <= 8000);
    pages.push(page); entries.push(...page.entries); cursor = page.next_cursor;
  } while (cursor && pages.length < 10);
  assert.equal(cursor, null); assert.equal(entries.length, 10); assert.ok(pages.length > 1);
  assert.deepEqual(entries.map(entry => entry.image.src).sort(), f.result.files.sort());
});

test('native extension matching requires leading dots and must not produce a false empty directory', async () => {
  fixture();
  foundry.applications.apps.FilePicker.implementation.browse = async (source, target, options) => ({target, dirs: [],
    files: ['icons/svg/test.svg'].filter(path => options.extensions.includes('.' + path.split('.').at(-1)))});
  const result = await browseJournalImages({source: 'public', directory: 'icons/svg'});
  assert.equal(result.total, 1);
  assert.equal(result.entries[0].image.src, 'icons/svg/test.svg');
});
