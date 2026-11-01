import test from 'node:test';
import assert from 'node:assert/strict';
import {getWritingGuidance, saveWritingGuidance, registerWritingGuidanceSettings, registerWritingGuidanceMenu} from '../../foundry-module/scripts/writingGuidance.js';

function fixture() {
  const settings = new Map(), definitions = new Map(), menus = new Map();
  globalThis.game = {ready: true, version: '14.369', world: {id: 'test'}, user: {isGM: true}, settings: {
    register(ns, key, value) {definitions.set(key, value); settings.set(key, structuredClone(value.default));},
    registerMenu(ns, key, value) {menus.set(key, value);},
    get(ns, key) {return structuredClone(settings.get(key));},
    async set(ns, key, value) {settings.set(key, structuredClone(value));}
  }};
  globalThis.foundry = {applications: {api: {DialogV2: class {constructor(options) {this.options = options;}}}}};
  globalThis.Hooks = {on() {}};
  registerWritingGuidanceSettings();
  return {settings, definitions, menus};
}
const code = name => error => error.rpcError?.code === name;

test('world setting and GM-only menu preserve configured HTML and save timestamp', async () => {
  const f = fixture();
  assert.equal(f.definitions.get('writingGuidance').scope, 'world');
  assert.equal(f.definitions.get('writingGuidance').config, false);
  assert.deepEqual(getWritingGuidance(), {world_id: 'test', html: null, saved_at: null});
  registerWritingGuidanceMenu(); assert.equal(f.menus.get('writingGuidance').restricted, true);
  const source = '<p>Do not edit <strong>Official Adventure</strong> without my permission.</p>';
  const saved = await saveWritingGuidance(source);
  assert.equal(saved.html, source); assert.ok(Number.isFinite(Date.parse(saved.saved_at)));
  assert.deepEqual(getWritingGuidance(), saved);
  const empty = await saveWritingGuidance(''); assert.equal(empty.html, ''); assert.ok(empty.saved_at > saved.saved_at);
});

test('same-clock saves remain distinguishable and stale configuration editors cannot overwrite', async t => {
  fixture(); t.mock.method(Date, 'now', () => 1000);
  const first = await saveWritingGuidance('<p>First</p>');
  const second = await saveWritingGuidance('<p>Second</p>', first);
  assert.notEqual(second.saved_at, first.saved_at);
  await assert.rejects(saveWritingGuidance('<p>Stale</p>', first), code('ContentChanged'));
  assert.equal(getWritingGuidance().html, '<p>Second</p>');
});

test('configuration save and reads enforce ready GM, core version, input bounds and unknown fields', async () => {
  fixture();
  assert.throws(() => getWritingGuidance({extra: true}), code('InvalidRequest'));
  await assert.rejects(saveWritingGuidance('😀'.repeat(3001)), code('InvalidRequest'));
  for (const value of [null, 123, {}]) await assert.rejects(saveWritingGuidance(value), code('InvalidRequest'));
  game.user.isGM = false;
  assert.throws(() => getWritingGuidance(), code('PermissionDenied'));
  await assert.rejects(saveWritingGuidance('x'), code('PermissionDenied'));
  assert.throws(() => registerWritingGuidanceMenu(), code('PermissionDenied'));
  fixture(); game.ready = false; assert.throws(() => getWritingGuidance(), code('NotReady'));
  fixture(); game.version = '13.0'; assert.throws(() => getWritingGuidance(), code('UnsupportedVersion'));
});

test('malformed saved settings are errors, never unconfigured guidance', () => {
  for (const value of [null, {html: 'text', saved_at: null}, {html: null, saved_at: 'bad'}, {html: '', saved_at: 'bad'}, {html: '', saved_at: null, extra: true}]) {
    const f = fixture(); f.settings.set('writingGuidance', value);
    assert.throws(() => getWritingGuidance(), code('ReadFailed'));
  }
});
