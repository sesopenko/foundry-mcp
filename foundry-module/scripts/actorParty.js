/**
 * PF2e-specific official world-party membership, core14.369/PF2e8.6.1.
 * Reads persisted party system.details.members[].uuid, not prepared members,
 * ownership, active users or game.actors.party. World Actor references only.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/party/data.ts
 * Public core game.actors, Actor.toObject(true), uuid and testUserPermission:
 * https://foundryvtt.com/api/v14/classes/foundry.documents.Actor.html
 */
import {ready, runtime, named, permitted, requirePermission, ACTOR_TYPES} from './actorDocuments.js';
import {fail, validateParams, integer, digest, paginate} from './actorReadUtils.js';
import {PHYSICAL_TYPES} from './actorPhysical.js';

const worldUuid = value => typeof value === 'string' && value.length <= 512 && /^Actor\.[^.\s#]+$/.test(value);
const identity = actor => ({uuid: actor.uuid, ...named(actor), type: actor.type});
const follow = (tool, uuid) => ({tool, arguments: {[tool === 'get_party_members' ? 'party_uuid' : 'actor_uuid']: uuid}});

/** PF2e-specific8.6.1 shared world-party selection for roster and stash.
 * No source or derived reads; selects only permitted world party Actors.
 * Candidate follow-ups retain the caller's tool, not a generic Actor reader.
 */
function partySelection(partyUuid, tool) {
  ready();
  if (game.actors.size > 12000) fail('ReadFailed', 'Party discovery exceeds 12000 world Actors.');
  const parties = [...game.actors.values()].filter(actor => actor.type === 'party');
  if (parties.length > 200) fail('ReadFailed', 'Party discovery exceeds 200 parties.');
  const readable = parties.filter(permitted).sort((a, b) => a.uuid < b.uuid ? -1 : a.uuid > b.uuid ? 1 : 0);
  let party = null;
  if (partyUuid != null) {
    party = game.actors.get(partyUuid.slice(6));
    if (!party || party.uuid !== partyUuid) fail('DocumentNotFound', 'Selected world party no longer exists.', 'Call get_party_members without party_uuid to rediscover.');
    requirePermission(party);
    if (party.type !== 'party') fail('UnsupportedType', 'party_uuid must identify a PF2e party Actor.', 'Use a party candidate from get_party_members.');
  } else if (readable.length === 1) party = readable[0];

  const reasons = [];
  if (!party && readable.length !== parties.length) reasons.push('parties_denied');
  if (!party) {
    return {runtime: runtime(), mode: 'parties', party: null,
      scope_status: reasons.length ? 'partial' : 'complete', reasons,
      entries: readable.map(actor => ({kind: 'party', identity: identity(actor), next_call: {tool, arguments: {party_uuid: actor.uuid}}})),
      membership: null};
  }
  return {document: party};
}

/** PF2e-specific persisted party roster; selection/permissions shared with stash.
 * Only system.details.members[].uuid, never prepared membership or inventory.
 */
function snapshot(partyUuid) {
  const selected = partySelection(partyUuid, 'get_party_members');
  if (!selected.document) return selected;
  const party = selected.document, reasons = [];
  const source = party.toObject(true);
  const claims = source?.system?.details?.members;
  if (source?.type !== 'party' || !Array.isArray(claims) || claims.length > 200
      || claims.some(claim => !claim || typeof claim.uuid !== 'string' || !claim.uuid || claim.uuid.length > 512)) {
    fail('ReadFailed', 'Party membership source is invalid or exceeds 200 references.', 'Inspect party membership in Foundry; missing membership is not an empty party.');
  }
  const entries = [], seen = new Set();
  for (const [index, claim] of claims.entries()) {
    if (seen.has(claim.uuid)) { reasons.push('duplicate_member_references'); continue; }
    seen.add(claim.uuid);
    const row = {kind: 'member', index, status: 'unsupported', identity: null, next_call: null};
    if (worldUuid(claim.uuid)) {
      const actor = game.actors.get(claim.uuid.slice(6));
      if (!actor || actor.uuid !== claim.uuid) row.status = 'missing';
      else if (!permitted(actor)) row.status = 'denied';
      else {
        row.identity = identity(actor);
        if (ACTOR_TYPES.includes(actor.type)) {
          row.status = 'resolved';
          row.next_call = follow('read_actor', actor.uuid);
        }
      }
    }
    if (row.status !== 'resolved') reasons.push('member_' + row.status);
    entries.push(row);
  }
  return {runtime: runtime(), mode: 'members', party: identity(party),
    scope_status: reasons.length ? 'partial' : 'complete', reasons: [...new Set(reasons)].sort(),
    entries, membership: claims.map(claim => claim.uuid)};
}

/** PF2e-specific bounded party discovery/roster read; schema and versions above.
 * Auto-selects the sole readable party; otherwise returns named candidates.
 * Pagination completion is separate from readable membership completeness.
 * Revisions include stored claims and current identity/permission outcomes.
 */
export async function getPartyMembers(params = {}) {
  validateParams(params, ['party_uuid', 'limit', 'max_bytes', 'cursor']);
  if (params.party_uuid != null && !worldUuid(params.party_uuid)) fail('InvalidRequest', 'party_uuid must be a canonical world Actor UUID from get_party_members.');
  const limit = integer(params.limit, 10, 1, 100, 'limit');
  const maxBytes = integer(params.max_bytes, 8000, 8000, 48000, 'max_bytes');
  const first = snapshot(params.party_uuid);
  const revision = await digest(first);
  const {entries, membership, ...context} = first;
  const page = await paginate(entries, {contract_version: 2, ...context, revision},
    {...params, limit, max_bytes: maxBytes}, {tool: 'get_party_members', party_uuid: params.party_uuid ?? null});
  if (await digest(snapshot(params.party_uuid)) !== revision) {
    fail('ContentChanged', 'Party roster changed during the read.', 'Discard accumulated pages and restart without cursor.');
  }
  const {records, ...result} = page;
  return {...result, entries: records};
}

/** PF2e-specific8.6.1 physical source leaf for stash summaries. Quantity is
 * stored stock, not currency value; containerId is a local Item-ID claim.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/physical/data.ts
 * Missing is explicit, not null/zero. No prepared Item field is substituted.
 */
function stashLeaf(source, key) {
  if (!source.system || !Object.hasOwn(source.system, key)) return {present: false};
  const value = source.system[key];
  const valid = key === 'quantity' ? Number.isFinite(value) && value >= 0
    : value === null || typeof value === 'string' && value.length <= 512;
  if (!valid) fail('ReadFailed', 'Invalid stored stash ' + key + '.', 'Inspect the selected party Item source.');
  return {present: true, value};
}

/** PF2e-specific party8.6.1 stash = actual embedded physical Items. Public
 * Actor.items, Item.parent/uuid/testUserPermission/toObject(true) only.
 * Party document source, member inventories, campaign Items and derived totals
 * are never read. Revision covers selected source values and permission scope.
 */
function stashSnapshot(partyUuid, select) {
  const selected = partySelection(partyUuid, 'get_party_stash');
  if (!selected.document) {
    const {membership, ...result} = selected;
    return {...result, basis: 'source'};
  }
  const party = selected.document, entries = [], reasons = new Set();
  if (!party.items || party.items.size > 12000) fail('ReadFailed', 'Stash exceeds 12000 owned Items or is unavailable.');
  for (const item of party.items.values()) {
    if (!permitted(item)) {reasons.add('stash_items_denied'); continue;}
    if (!PHYSICAL_TYPES.includes(item.type)) {reasons.add('stash_nonphysical_excluded'); continue;}
    if (item.parent !== party || item.uuid !== party.uuid + '.Item.' + item.id
        || typeof item.id !== 'string' || !/^[^.\s#]+$/.test(item.id) || item.uuid.length > 512) {
      fail('ReadFailed', 'Stash Item identity does not match its selected owner.');
    }
    const source = item.toObject(true);
    if (source?.type !== item.type || typeof source.name !== 'string') fail('ReadFailed', 'Invalid stash Item source identity.');
    const entry = {kind: 'item', identity: {uuid: item.uuid, ...named(source), type: source.type}};
    if (select.quantity) entry.quantity = stashLeaf(source, 'quantity');
    if (select.container) entry.container = stashLeaf(source, 'containerId');
    if (select.follow_up) entry.next_call = {tool: 'read_item', arguments: {item_uuid: item.uuid}};
    entries.push(entry);
  }
  entries.sort((a,b) => a.identity.uuid < b.identity.uuid ? -1 : a.identity.uuid > b.identity.uuid ? 1 : 0);
  return {runtime: runtime(), mode: 'stash', party: identity(party), basis: 'source',
    scope_status: reasons.size ? 'partial' : 'complete', reasons: [...reasons].sort(), entries};
}

/** PF2e-specific bounded party stash source summary, core14.369/PF2e8.6.1.
 * Select before pagination; follow read_item for optional source/description
 * evidence. Source schema and read restrictions are documented above.
 */
export async function getPartyStash(params = {}) {
  validateParams(params, ['party_uuid', 'select', 'limit', 'max_bytes', 'cursor']);
  if (params.party_uuid != null && !worldUuid(params.party_uuid)) fail('InvalidRequest', 'Use a world party Actor UUID from get_party_members or get_party_stash.');
  const choices = params.select === undefined ? {} : validateParams(params.select, ['quantity', 'container', 'follow_up']);
  if (Object.values(choices).some(value => typeof value !== 'boolean')) fail('InvalidRequest', 'select fields must be booleans.');
  const select = {quantity: true, container: false, follow_up: true, ...choices};
  const limit = integer(params.limit, 10, 1, 100, 'limit');
  const maxBytes = integer(params.max_bytes, 8000, 8000, 48000, 'max_bytes');
  const first = stashSnapshot(params.party_uuid, select), revision = await digest(first);
  const {entries, ...context} = first;
  const page = await paginate(entries, {contract_version: 2, ...context, revision},
    {...params, limit, max_bytes: maxBytes}, {tool: 'get_party_stash', party_uuid: params.party_uuid ?? null, select});
  if (await digest(stashSnapshot(params.party_uuid, select)) !== revision) fail('ContentChanged', 'Party stash changed during the read.', 'Discard accumulated pages and restart without cursor.');
  const {records, ...result} = page;
  return {...result, entries: records};
}
