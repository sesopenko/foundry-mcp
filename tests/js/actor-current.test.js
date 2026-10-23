import test from 'node:test';
import assert from 'node:assert/strict';
import { currentStatisticFields } from '../../foundry-module/scripts/actorCurrent.js';

function fixture(type = 'npc') {
  const statistic = { value: 11, totalModifier: 12, breakdown: 'selected explanation' };
  return { type, system: {
    abilities: Object.fromEntries(['str', 'dex', 'con', 'int', 'wis', 'cha'].map(key => [key, { mod: 3, base: 2 }])),
    attributes: { ac: { value: 22, breakdown: 'AC explanation', details: '' }, hp: { value: 7, max: 30, temp: 0 } },
    saves: Object.fromEntries(['fortitude', 'reflex', 'will'].map(key => [key, { ...statistic, rank: 2 }])),
    perception: { ...statistic, vision: false, rank: 0 },
    movement: { speeds: { land: { value: 30, base: 25, type: 'land', source: null }, travel: { value: 25, base: 25, type: 'travel', source: '' }, burrow: null, climb: null, fly: { value: 20, base: 15, type: 'fly', source: 'effect' }, swim: null } },
  } };
}
const byPath = (result, path) => result.fields.find(field => field.path === `/system/${path}`);

test('current NPC snapshot retains independent transformed numbers and explicit null modes', () => {
  const input = fixture();
  const result = currentStatisticFields(input);
  assert.deepEqual(result.reasons, ['other_statistics_pending']);
  assert.equal(byPath(result, 'saves/fortitude/value').value, 11);
  assert.equal(byPath(result, 'saves/fortitude/totalModifier').value, 12);
  assert.deepEqual(byPath(result, 'movement/speeds/burrow'), { path: '/system/movement/speeds/burrow', present: true, value: null, concept: 'current_burrow_movement', limitations: ['serialized_current_value_not_target_context'] });
  assert.equal(byPath(result, 'movement/speeds/land/source').value, null);
  assert.equal(byPath(result, 'perception/vision').value, false);
  assert.equal(byPath(result, 'abilities/str/base'), undefined);
  assert.equal(byPath(result, 'saves/fortitude/rank'), undefined);
  assert.deepEqual(input, fixture());
});

test('character base is separate from mod and all TEML labels are exact', () => {
  for (const [rank, label] of ['Untrained', 'Trained', 'Expert', 'Master', 'Legendary'].entries()) {
    const input = fixture('character'); input.system.perception.rank = rank;
    const result = currentStatisticFields(input);
    assert.equal(byPath(result, 'abilities/str/mod').value, 3);
    assert.equal(byPath(result, 'abilities/str/base').value, 2);
    assert.deepEqual(byPath(result, 'perception/rank').mapped_value, { rank, label });
    assert.deepEqual(byPath(result, 'saves/will/rank').mapped_value, { rank: 2, label: 'Expert' });
  }
});

test('mapped concepts identify book statistics rather than raw schema locations', () => {
  const result = currentStatisticFields(fixture('character'));
  for (const [path, concept] of [
    ['abilities/str/mod', 'current_attribute_modifier_str'],
    ['abilities/str/base', 'current_attribute_base_modifier_str'],
    ['attributes/ac/value', 'current_armor_class'],
    ['attributes/ac/details', 'current_armor_class_exception_notes'],
    ['attributes/hp/max', 'current_maximum_hit_points'],
    ['attributes/hp/temp', 'current_temporary_hit_points'],
    ['saves/will/totalModifier', 'current_will_save_total_modifier'],
    ['saves/will/rank', 'current_will_save_proficiency_rank'],
    ['perception/vision', 'current_standard_vision'],
    ['movement/speeds/travel/value', 'current_travel_speed'],
    ['movement/speeds/fly/base', 'current_fly_base_speed'],
    ['movement/speeds/fly/source', 'current_fly_movement_source_label'],
    ['movement/speeds/fly/type', 'current_fly_movement_type'],
  ]) assert.equal(byPath(result, path).concept, concept);
});

test('missing values remain absent without source fallback or calculated defaults', () => {
  const input = fixture();
  delete input.system.perception.totalModifier;
  delete input.system.perception.rank;
  delete input.system.movement.speeds.climb;
  input._source = { system: { perception: { totalModifier: 99 } } };
  input.system.attributes.speed = { value: 999 };
  const result = currentStatisticFields(input);
  assert.deepEqual(result.reasons, ['other_statistics_pending', 'current_fields_unavailable']);
  for (const path of ['perception/totalModifier', 'perception/rank', 'movement/speeds/climb/value']) {
    const row = byPath(result, path); assert.equal(row.present, false); assert.equal(Object.hasOwn(row, 'value'), false);
  }
});

test('malformed admitted primitives, ranks, containers and mode literals fail', () => {
  for (const value of [null, '12', NaN, Infinity, {}, []]) {
    const input = fixture(); input.system.attributes.ac.value = value;
    assert.throws(() => currentStatisticFields(input), TypeError);
  }
  for (const rank of [-1, 5, 1.5, '2', null]) {
    const input = fixture(); input.system.perception.rank = rank;
    assert.throws(() => currentStatisticFields(input), TypeError);
  }
  for (const value of [null, [], 12]) {
    const input = fixture(); input.system.attributes.ac = value;
    assert.throws(() => currentStatisticFields(input), TypeError);
  }
  const input = fixture(); input.system.movement.speeds.fly.type = 'swim';
  assert.throws(() => currentStatisticFields(input), TypeError);
  input.system.movement.speeds.fly.type = 'fly'; input.system.movement.speeds.land = null;
  assert.throws(() => currentStatisticFields(input), TypeError);
});

test('unknown data stays unread; admitted getters fail without invocation', () => {
  const input = fixture();
  Object.defineProperty(input.system, 'actions', { get() { throw Error('must not read'); } });
  input.system.skills = { nature: { totalModifier: 900 } };
  input.system.flags = { secret: 'excluded' };
  assert.equal(JSON.stringify(currentStatisticFields(input)).includes('secret'), false);
  Object.defineProperty(input.system.perception, 'value', { get() { throw Error('must not invoke'); } });
  assert.throws(() => currentStatisticFields(input), TypeError);
});

test('serialized HP own data leaves remain readable on a nonplain container without inherited access', () => {
  class SerializedHitPoints {
    constructor() { this.value = 7; this.max = 30; this.temp = 0; }
    get privateSentinel() { throw Error('must not inspect prototype'); }
  }
  const input = fixture(); input.system.attributes.hp = new SerializedHitPoints();
  const result = currentStatisticFields(input);
  assert.equal(byPath(result, 'attributes/hp/value').value, 7);
  assert.equal(byPath(result, 'attributes/hp/max').value, 30);
  assert.equal(byPath(result, 'attributes/hp/temp').value, 0);
  assert.ok(!JSON.stringify(result).includes('privateSentinel'));
  delete input.system.attributes.hp.value;
  Object.defineProperty(SerializedHitPoints.prototype, 'value', { get() { throw Error('must not read inherited statistic'); } });
  const missing = byPath(currentStatisticFields(input), 'attributes/hp/value');
  assert.equal(missing.present, false); assert.equal(Object.hasOwn(missing, 'value'), false);
  Object.defineProperty(input.system.attributes.hp, 'value', { get() { throw Error('must not invoke own getter'); } });
  assert.throws(() => currentStatisticFields(input), TypeError);
});

test('familiar and excluded types have no independent current-statistic contract', () => {
  for (const type of ['familiar', 'hazard', 'vehicle', 'loot', 'party', 'army', 'unknown']) assert.equal(currentStatisticFields({ type }), null);
});
