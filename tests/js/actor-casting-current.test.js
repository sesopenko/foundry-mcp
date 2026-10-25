import test from 'node:test';
import assert from 'node:assert/strict';
import { castingCurrentFields } from '../../foundry-module/scripts/actorCastingCurrent.js';

const actor = (type = 'character') => ({ type, system: { resources: { focus: { value: 1, max: 2, cap: 3 } } } });
const spell = focusPoints => ({ type: 'spell', system: { cast: { focusPoints } } });

test('character/NPC transformed focus preserves independent values and exact descriptors', () => {
  for (const type of ['character', 'npc']) {
    const input = actor(type);
    const result = castingCurrentFields(input, 'Actor');
    assert.deepEqual(result.fields[0], { path: '/system/resources/focus/value', present: true, value: 1, concept: 'current_focus_points', limitations: ['casting_availability_not_evaluated'] });
    assert.deepEqual(result.fields.map(field => field.concept), ['current_focus_points', 'current_focus_pool_maximum', 'current_focus_pool_cap']);
    assert.deepEqual(result.fields.map(field => field.value), [1, 2, 3]);
    assert.deepEqual(input, actor(type));
    input.system.resources.focus = { value: -1.25, max: 17.5, cap: -8 };
    assert.deepEqual(castingCurrentFields(input, 'Actor').fields.map(field => field.value), [-1.25, 17.5, -8]);
  }
});

test('spell focus cost admits exactly integer zero through three', () => {
  for (const value of [0, 1, 2, 3]) assert.deepEqual(castingCurrentFields(spell(value), 'Item').fields[0], { path: '/system/cast/focusPoints', present: true, value, concept: 'current_spell_focus_point_cost', limitations: ['casting_availability_not_evaluated'] });
  for (const value of [-1, 4, 1.5]) assert.throws(() => castingCurrentFields(spell(value), 'Item'), TypeError);
});

test('missing fields stay absent, including undefined, without source fallback', () => {
  const input = { type: 'character', system: {}, _source: actor().system };
  const result = castingCurrentFields(input, 'Actor');
  assert.deepEqual(result.reasons, ['casting_availability_not_evaluated', 'current_fields_unavailable']);
  for (const field of result.fields) assert.equal(Object.hasOwn(field, 'value'), false);
  assert.equal(castingCurrentFields(spell(undefined), 'Item').fields[0].present, false);
});

test('malformed selected values and containers fail rather than coerce', () => {
  for (const value of [true, false, null, '1', {}, [], NaN, Infinity, -Infinity]) {
    const input = actor(); input.system.resources.focus.value = value;
    assert.throws(() => castingCurrentFields(input, 'Actor'), TypeError);
    assert.throws(() => castingCurrentFields(spell(value), 'Item'), TypeError);
  }
  for (const value of [null, true, [], 1]) {
    const input = actor(); input.system.resources.focus = value;
    assert.throws(() => castingCurrentFields(input, 'Actor'), TypeError);
  }
});

test('nonplain own data is accepted; inherited data/getters are excluded', () => {
  class Focus { constructor() { this.value = 1; this.max = 2; this.cap = 3; } }
  const input = actor(); input.system.resources.focus = new Focus();
  assert.deepEqual(castingCurrentFields(input, 'Actor').fields.map(field => field.value), [1, 2, 3]);
  delete input.system.resources.focus.value;
  Object.defineProperty(Focus.prototype, 'value', { get() { throw Error('must not invoke'); } });
  assert.equal(castingCurrentFields(input, 'Actor').fields[0].present, false);
  Object.defineProperty(input.system.resources.focus, 'value', { get() { throw Error('must not invoke'); } });
  assert.throws(() => castingCurrentFields(input, 'Actor'), TypeError);
  const inherited = Object.create({ type: 'character' });
  assert.equal(castingCurrentFields(inherited, 'Actor'), null);
});

test('selected ancestor/type getters reject without invocation; unrelated getters unread', () => {
  for (const key of ['type', 'system']) {
    const input = actor(); Object.defineProperty(input, key, { get() { throw Error('getter invoked'); } });
    assert.throws(() => castingCurrentFields(input, 'Actor'), TypeError);
  }
  const input = actor(); Object.defineProperty(input.system, 'slots', { get() { throw Error('must not invoke'); } });
  assert.equal(castingCurrentFields(input, 'Actor').fields.length, 3);
});

test('unknown kinds/subtypes and familiar have no current casting interpretation', () => {
  for (const type of ['familiar', 'hazard', 'vehicle', 'loot', 'party', 'army', 'spell', 'unknown']) assert.equal(castingCurrentFields({ type }, 'Actor'), null);
  for (const type of ['spellcastingEntry', 'character', 'unknown']) assert.equal(castingCurrentFields({ type }, 'Item'), null);
  assert.equal(castingCurrentFields(null, 'unknown'), null);
});
