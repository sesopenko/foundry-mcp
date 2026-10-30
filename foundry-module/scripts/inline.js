/** PF2e-specific source verification for Foundry14.369/PF2e8.6.1.
 * Authored arithmetic only, never Actor-derived values. Syntax/vocabulary:
 * https://github.com/foundryvtt/pf2e/wiki/Style-Guide
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/system/damage/values.ts
 * Core public APIs: Roll.validate (no evaluation), async fromUuid, document
 * uuid/documentName/compendium and document/pack testUserPermission.
 * https://foundryvtt.com/api/v14/classes/foundry.dice.Roll.html#validate
 * https://foundryvtt.com/api/v14/classes/foundry.documents.Item.html
 */
import { ready, requirePermission } from './actorDocuments.js';
import { fail } from './actorReadUtils.js';

/** PF2e-specific shared admission, core14.369/system8.6.1; no source reads. */
function verify(params) {
  const runtime = ready();
  if (typeof params?.text !== 'string' || !params.text || new TextEncoder().encode(params.text).length > 8000 ||
      !Array.isArray(params.formulas) || params.formulas.length > 48) {
    fail('InvalidRequest', 'Malformed inline verification packet.', 'Use the typed builder through MCP.');
  }
  for (const formula of params.formulas) {
    // Only server-generated additive dice/integer arithmetic crosses this RPC.
    if (typeof formula !== 'string' || formula.length > 256 || !/^-?\d+(?:d(?:100|20|12|10|8|6|4))?(?:[+-]\d+(?:d(?:100|20|12|10|8|6|4))?)*$/.test(formula)) {
      fail('InvalidRequest', 'Only structured additive arithmetic is supported.', 'Use typed amounts, not expressions.');
    }
    let valid = false;
    try { valid = foundry.dice.Roll.validate(formula) === true; } catch { /* public validation failure */ }
    if (!valid) fail('InvalidFormula', 'Foundry rejected generated arithmetic.', 'Correct the structured dice/amount and retry.');
  }
  return { text: params.text, runtime };
}

/** PF2e-specific roll admission/validation; never rolls or sends messages. */
export function verifyPF2eInlineRoll(params) { return verify(params); }

/** PF2e-specific check admission; server owns the typed vocabulary, no Actor DC calculation. */
export function verifyPF2eInlineCheck(params) { return verify(params); }

/** PF2e-specific embed identity/access check; no Item body or source is read. */
export async function verifyPF2eInlineEmbed(params) {
  const result = verify(params);
  const uuid = params.item_uuid;
  if (typeof uuid !== 'string' || uuid.length > 512 || !/^Compendium\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.Item\.[A-Za-z0-9]{16}$/.test(uuid)) {
    fail('InvalidRequest', 'Use a canonical compendium Item UUID.', 'Rediscover with search_compendium_actors.');
  }
  const pack = game.packs.get(uuid.split('.').slice(1, 3).join('.'));
  if (!pack) fail('DocumentNotFound', 'Compendium is unavailable.', 'Rediscover an installed Item pack.');
  requirePermission(pack);
  if (pack.documentName !== 'Item') fail('InvalidRequest', 'Embed requires an Item pack.', 'Select an Item compendium.');
  let item;
  try { item = await foundry.utils.fromUuid(uuid); }
  catch { fail('DocumentAccessFailed', 'Compendium Item resolution failed.', 'Check pack availability and retry.'); }
  // Recheck runtime and permissions after asynchronous hydration.
  ready();
  if (game.packs.get(pack.collection) !== pack) fail('DocumentNotFound', 'Compendium changed during resolution.', 'Rediscover and retry.');
  requirePermission(pack);
  if (!item) fail('DocumentNotFound', 'Compendium Item is missing.', 'Rediscover its UUID.');
  requirePermission(item);
  if (item.documentName !== 'Item' || item.uuid !== uuid || item.compendium !== pack || item.parent) {
    fail('InvalidRequest', 'Resolved document is not the selected canonical compendium Item.', 'Rediscover its canonical Item UUID.');
  }
  return result;
}
