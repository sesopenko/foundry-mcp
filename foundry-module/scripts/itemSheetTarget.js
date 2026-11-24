/** PF2e-specific 8.7.0 physical Item authoring via public Foundry 14.370 APIs.
 * Source, transformed values and world/token provenance are kept separate.
 * https://foundryvtt.com/api/v14/classes/foundry.abstract.Document.html
 * https://github.com/foundryvtt/pf2e/blob/52dfeee703b887237f5e454747bcae45b136f9af/src/module/item/physical/data.ts
 */
import {itemTarget, ready} from './actorDocuments.js';
import {PHYSICAL_TYPES} from './actorPhysical.js';
import {fail} from './actorReadUtils.js';

/** PF2e-specific nine physical types. Recheck live membership independently of source data. */
export async function sheetTarget(params) {
  const runtime = ready();
  if (runtime.core_version !== '14.370' || runtime.system_version !== '8.7.0') {
    fail('UnsupportedVersion', 'The physical Item form requires Foundry 14.370 and PF2e 8.7.0.', 'Use read_item with select for source evidence.');
  }
  const target = await itemTarget(params);
  const {actor, token, document: item} = target;
  if (!PHYSICAL_TYPES.includes(item.type)) fail('UnsupportedType', 'Select a physical Item.', 'Use read_item without sheet for other types.');
  let reason = null;
  if (item.compendium || actor?.compendium || item.uuid.startsWith('Compendium.')) reason = 'Compendium Items are read-only.';
  else if (token?.isLinked) reason = 'Linked token shares inventory. Use the canonical Actor Item UUID without token_uuid: ' + item.uuid;
  else if (actor) {
    const ownerMember = token
      ? game.scenes?.get(token.parent.id) === token.parent && token.parent.tokens.get(token.id) === token &&
        token.actor === actor && actor.uuid.startsWith(token.uuid + '.Actor.')
      : game.actors.get(actor.id) === actor && actor.uuid === 'Actor.' + actor.id;
    if (!ownerMember || item.parent !== actor || actor.items.get(item.id) !== item ||
        item.uuid !== actor.uuid + '.Item.' + item.id) reason = 'Item is outside the selected inventory.';
  } else if (item.parent || item.uuid !== 'Item.' + item.id || game.items.get(item.id) !== item) {
    reason = 'Select an existing standalone world Item or a direct inventory member.';
  }
  if (!reason && (!item.canUserModify(game.user, 'update') || (actor && !actor.canUserModify(game.user, 'update')))) {
    reason = 'GM lacks update permission on the Item or owner.';
  }
  return {...target, runtime, reason};
}
