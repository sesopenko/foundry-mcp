/**
 * PF2e-specific detached transformed casting-resource selector for character/NPC
 * Actors and spell Items. Supported schema: PF2e8.6.1, immutable sources:
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/character/data.ts
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/creature/data.ts
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/spell/data.ts
 * CharacterResources/CreatureResources focus value/max/cap are numbers (not a
 * declared integer range); SpellCastData.focusPoints is ZeroToThree. These are
 * transformed document data, never persisted-source fallbacks or calculations.
 * The caller must establish PF2e, authorization and public toObject(false)
 * serialization before calling. This pure helper calls no Foundry API.
 */

/** PF2e-specific own data lookup; never traverse prototypes or invoke getters. */
function selected(serialized, keys) {
  let value = serialized;
  for (const key of keys) {
    if (value === null || typeof value !== 'object' || Array.isArray(value)) {
      throw new TypeError(`Current casting /${keys.join('/')} has a malformed container.`);
    }
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    if (!descriptor) return { present: false };
    if (!Object.hasOwn(descriptor, 'value')) throw new TypeError('Current casting requires detached data properties.');
    value = descriptor.value;
    if (value === undefined) return { present: false };
  }
  return { present: true, value };
}

/**
 * PF2e-specific selected current resources from detached toObject(false) data.
 * documentType is the public document kind "Actor" or "Item", not subtype.
 * Returns null for unsupported kinds/subtypes (including familiar); otherwise
 * returns {fields, reasons}. Every field has path, present, concept, limitations
 * and value only when present. Missing/undefined fields stay absent; malformed
 * selected containers, accessors or primitive values throw TypeError.
 * Own data on nonplain containers is accepted. No full availability, cast rank,
 * casting options, slot expenditure or source fallback is inferred. Consumers
 * must retain transformed provenance separately from source records.
 */
export function castingCurrentFields(serialized, documentType) {
  if (!['Actor', 'Item'].includes(documentType)) return null;
  const type = selected(serialized, ['type']);
  if (!type.present || !(documentType === 'Actor' ? ['character', 'npc'] : ['spell']).includes(type.value)) return null;
  const specifications = documentType === 'Actor'
    ? ['value', 'max', 'cap'].map(leaf => ({ keys: ['system', 'resources', 'focus', leaf], concept: { value: 'current_focus_points', max: 'current_focus_pool_maximum', cap: 'current_focus_pool_cap' }[leaf] }))
    : [{ keys: ['system', 'cast', 'focusPoints'], concept: 'current_spell_focus_point_cost' }];
  const fields = specifications.map(({ keys, concept }) => {
    const result = selected(serialized, keys);
    const path = `/${keys.join('/')}`;
    if (result.present && (typeof result.value !== 'number' || !Number.isFinite(result.value)
      || documentType === 'Item' && (!Number.isInteger(result.value) || result.value < 0 || result.value > 3))) {
      throw new TypeError(`Current casting ${path} has an unexpected type or value.`);
    }
    return { path, ...result, concept, limitations: ['casting_availability_not_evaluated'] };
  });
  return { fields, reasons: ['casting_availability_not_evaluated', ...(fields.some(field => !field.present) ? ['current_fields_unavailable'] : [])] };
}
