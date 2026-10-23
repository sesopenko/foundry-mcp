/**
 * PF2e-specific transformed character/NPC document-data allowlist, tested boundary
 * Foundry14.369/PF2e8.6.1. Detached public toObject(false) output only:
 * https://foundryvtt.com/api/v14/classes/foundry.abstract.DataModel.html#toobject
 * System contracts (creature/data.ts, character/data.ts, data/base.ts and
 * system/statistic/{data,speed,armor-class,perception,hit-points}.ts):
 * https://github.com/foundryvtt/pf2e/tree/28d9d156f252d084371d994dc359509b49eadf18/src/module
 * Transformed values stay distinct from persisted source and target-context
 * calculations. No runtime methods, getters, preparation or source fallbacks.
 */
const LIMITATION = 'serialized_current_value_not_target_context';
const RANKS = ['Untrained', 'Trained', 'Expert', 'Master', 'Legendary'];

/** PF2e-specific book concepts for the pinned transformed document-data leaves. */
function concept(keys) {
  const [group, key, leaf, speedLeaf] = keys;
  if (group === 'abilities') return `current_attribute_${leaf === 'base' ? 'base_' : ''}modifier_${key}`;
  if (group === 'attributes' && key === 'ac') return { value: 'current_armor_class', breakdown: 'current_armor_class_breakdown', details: 'current_armor_class_exception_notes' }[leaf];
  if (group === 'attributes') return { value: 'current_hit_points', max: 'current_maximum_hit_points', temp: 'current_temporary_hit_points' }[leaf];
  if (group === 'saves') return `current_${key}_save_${{ value: 'modifier', totalModifier: 'total_modifier', breakdown: 'breakdown', rank: 'proficiency_rank' }[leaf]}`;
  if (group === 'perception') return { value: 'current_perception_modifier', totalModifier: 'current_perception_total_modifier', breakdown: 'current_perception_breakdown', vision: 'current_standard_vision', rank: 'current_perception_proficiency_rank' }[key];
  return `current_${leaf}_${speedLeaf === undefined ? 'movement' : { value: 'speed', base: 'base_speed', type: 'movement_type', source: 'movement_source_label' }[speedLeaf]}`;
}

/**
 * PF2e-specific own transformed-data lookup; malformed admitted containers fail.
 * Public serialization can retain an HP object prototype in the verified runtime.
 * Only selected own data descriptors are admitted; prototypes are never traversed
 * and accessors are never invoked, regardless of the container's prototype.
 */
function selected(serialized, keys) {
  let value = serialized;
  for (const key of keys) {
    if (value === null || typeof value !== 'object' || Array.isArray(value)) {
      throw new TypeError(`Current statistic /${keys.join('/')} has a malformed container.`);
    }
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    if (!descriptor) return { present: false };
    if (!Object.hasOwn(descriptor, 'value')) throw new TypeError('Current statistics require detached data properties.');
    value = descriptor.value;
    if (value === undefined) return { present: false };
  }
  return { present: true, value };
}

/** PF2e-specific character/NPC transformed primitives; no derived arithmetic. */
export function currentStatisticFields(serialized) {
  const actorType = selected(serialized, ['type']);
  if (!actorType.present || !['character', 'npc'].includes(actorType.value)) return null;
  const fields = [];
  /** PF2e-specific transformed scalar selection; never invoke a runtime getter. */
  const add = (keys, type, nullable = false, literal) => {
    const result = selected(serialized, ['system', ...keys]);
    const path = `/system/${keys.join('/')}`;
    if (result.present) {
      const value = result.value;
      const valid = nullable && value === null || (type === 'rank'
        ? Number.isInteger(value) && value >= 0 && value <= 4
        : typeof value === type && (type !== 'number' || Number.isFinite(value)));
      if (!valid || (literal !== undefined && value !== literal)) throw new TypeError(`Current statistic ${path} has an unexpected type or value.`);
    }
    const field = { path, ...result, concept: concept(keys), limitations: [LIMITATION] };
    if (result.present && type === 'rank') field.mapped_value = { rank: result.value, label: RANKS[result.value] };
    fields.push(field);
  };
  for (const ability of ['str', 'dex', 'con', 'int', 'wis', 'cha']) {
    add(['abilities', ability, 'mod'], 'number');
    if (actorType.value === 'character') add(['abilities', ability, 'base'], 'number');
  }
  for (const [key, type] of [['value', 'number'], ['breakdown', 'string'], ['details', 'string']]) add(['attributes', 'ac', key], type);
  for (const key of ['value', 'max', 'temp']) add(['attributes', 'hp', key], 'number');
  for (const save of ['fortitude', 'reflex', 'will']) {
    for (const [key, type] of [['value', 'number'], ['totalModifier', 'number'], ['breakdown', 'string']]) add(['saves', save, key], type);
    if (actorType.value === 'character') add(['saves', save, 'rank'], 'rank');
  }
  for (const [key, type] of [['value', 'number'], ['totalModifier', 'number'], ['breakdown', 'string'], ['vision', 'boolean'], ['rank', 'rank']]) add(['perception', key], type);
  for (const mode of ['land', 'burrow', 'climb', 'fly', 'swim', 'travel']) {
    const keys = ['movement', 'speeds', mode];
    const modeData = selected(serialized, ['system', ...keys]);
    if (!['land', 'travel'].includes(mode) && modeData.present && modeData.value === null) {
      add(keys, 'object', true);
      continue;
    }
    for (const [key, type] of [['value', 'number'], ['base', 'number'], ['type', 'string'], ['source', 'string']]) {
      add([...keys, key], type, key === 'source', key === 'type' ? mode : undefined);
    }
  }
  return { fields, reasons: ['other_statistics_pending', ...(fields.some(field => !field.present) ? ['current_fields_unavailable'] : [])] };
}
