/**
 * Public document boundary for the PF2e-specific Actor/Item readers.
 * Core 14.369 APIs: Actor/Item.toObject(true), parent, uuid, compendium,
 * testUserPermission, TokenDocument.actor/baseActor/isLinked, async fromUuid.
 * https://foundryvtt.com/api/v14/classes/foundry.documents.Item.html
 * https://foundryvtt.com/api/v14/classes/foundry.documents.TokenDocument.html
 * No sheet/preparation data, roll context or PF2e relationship getters are used.
 */
import { fail, selector } from "./actorReadUtils.js";

export const ACTOR_TYPES = ["character", "npc", "familiar"];
export const ITEM_TYPES = ["melee", "action", "feat", "spell", "spellcastingEntry", "lore", "condition", "effect", "affliction", "ancestry", "heritage", "background", "class", "deity", "weapon", "armor", "shield", "equipment", "consumable", "ammo", "backpack", "book", "kit", "treasure"];

/** Current runtime identity, without treating a manifest as a browser check. */
export function runtime() {
  return { core_version: String(game.version), system_id: String(game.system?.id ?? ""), system_version: String(game.system?.version ?? "") };
}

/**
 * PF2e-specific admission: only core14.369/system8.6.1 has the audited schema.
 * All 3 Actor/24 Item types initially expose selected core source metadata only.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/system.pf2e.json
 */
export function ready(interpret = true) {
  if (!globalThis.game?.ready || !game.actors || !game.items) fail("NotReady", "Foundry documents are not ready.", "Wait for the existing world to finish loading.");
  if (!game.user?.isGM) fail("PermissionDenied", "Actor and Item tools require the connected GM.", "Connect the authorized test-world GM browser.");
  const value = runtime();
  if (interpret && value.system_id !== "pf2e") fail("UnsupportedSystem", "Actor/Item mappings require PF2e.", "Inspect get_actor_types and select a supported PF2e world.");
  if (interpret && (value.core_version !== "14.369" || value.system_version !== "8.6.1")) fail("UnsupportedVersion", "This Actor/Item contract is verified for core14.369/PF2e8.6.1.", "Inspect get_actor_types; verify the new version before enabling its schemas.");
  return value;
}

/** Explicit document/pack authorization, rechecked on every request. */
export function permitted(document) {
  return typeof document?.testUserPermission === "function" && document.testUserPermission(game.user, "OBSERVER") === true;
}

export function requirePermission(document) {
  if (!permitted(document)) fail("PermissionDenied", "The selected document or pack is not readable.", "Have an authorized GM grant OBSERVER access, then retry.");
}

/** Clip display context only; canonical selectors are never clipped. */
export function named(document) {
  const source = String(document?.name ?? "");
  return { name: [...source].slice(0, 256).join(""), name_truncated: [...source].length > 256 };
}

/** Resolve only a canonical full UUID through the public async resolver. */
async function resolve(uuid, kind) {
  selector(uuid, `${kind.toLowerCase()}_uuid`);
  if (!/^(Actor\.|Item\.|Compendium\.|Scene\.)/.test(uuid) || uuid.includes("#")) fail("InvalidRequest", "Use a canonical absolute document UUID, without an anchor.");
  let document;
  try { document = await foundry.utils.fromUuid(uuid); }
  catch { fail("ReadFailed", "Document resolution failed.", "Retry once or inspect the development browser console."); }
  if (!document) fail("DocumentNotFound", "Selected document no longer exists.", "Rediscover the UUID in its original world, pack or scene.");
  requirePermission(document);
  if (document.documentName !== kind || document.uuid !== uuid) fail("InvalidRequest", `Use the returned canonical ${kind} UUID.`);
  return document;
}

/** PF2e-specific 8.6.1 type boundary; ACTOR_TYPES/ITEM_TYPES do not infer role. */
function supported(document) {
  const allowed = document.documentName === "Actor" ? ACTOR_TYPES : ITEM_TYPES;
  if (!allowed.includes(document.type)) fail("UnsupportedType", `Type '${String(document.type)}' has no supported Actor/Item interpretation.`, "Inspect get_actor_types for supported types.");
}

/** Read public identities with permission checks on every related record. */
export function documentIdentity(document, actor, token) {
  const pack = document.compendium ?? actor?.compendium ?? null;
  if (pack) requirePermission(pack);
  const folder = document.folder && permitted(document.folder) ? document.folder : null;
  let instance = null;
  if (token) {
    const base = token.baseActor;
    instance = { scene_uuid: token.parent.uuid, scene_name: named(token.parent).name,
      token_uuid: token.uuid, token_name: named(token).name, actor_link: token.isLinked,
      base_actor: base && permitted(base) ? { uuid: base.uuid, ...named(base) } : null };
  }
  return { document_name: document.documentName, id: document.id, uuid: document.uuid, ...named(document), type: document.type,
    source_kind: token ? "token" : pack ? "compendium" : "world",
    folder: folder ? { id: folder.id, uuid: folder.uuid, ...named(folder) } : null,
    pack: pack ? { id: pack.collection, title: String(pack.title).slice(0, 256) } : null,
    actor: actor ? { uuid: actor.uuid, ...named(actor) } : null, instance };
}

/** Resolve a world/pack Actor or token; PF2e-specific supported type filter. */
export async function actorTarget(params) {
  if ((params.actor_uuid == null) === (params.token_uuid == null)) fail("InvalidRequest", "Provide exactly one of actor_uuid or token_uuid.");
  let actor; let token = null;
  if (params.token_uuid != null) {
    if (typeof params.token_uuid !== "string" || !/^Scene\.[^.]+\.Token\.[^.]+$/.test(params.token_uuid)) fail("InvalidRequest", "token_uuid must select a placed Scene Token.");
    token = await resolve(params.token_uuid, "Token");
    if (token.parent?.documentName !== "Scene") fail("InvalidRequest", "Select a placed Scene Token.");
    requirePermission(token.parent);
    actor = token.actor;
    if (!actor) fail("ActorUnavailable", "The token's current Actor is unavailable.", "Inspect its Actor association; the base template cannot substitute current state.");
    requirePermission(actor);
  } else {
    if (typeof params.actor_uuid !== "string" || !/^(Actor\.|Compendium\.)/.test(params.actor_uuid)) fail("InvalidRequest", "Use actor_uuid for a world/pack Actor or token_uuid for a scene instance.");
    actor = await resolve(params.actor_uuid, "Actor");
  }
  supported(actor);
  return { document: actor, actor: null, token, identity: documentIdentity(actor, null, token) };
}

/** Resolve an Item with its owner/instance; PF2e-specific 8.6.1 type filter. */
export async function itemTarget(params) {
  selector(params.item_uuid, "item_uuid");
  if (params.token_uuid != null) {
    const target = await actorTarget({ token_uuid: params.token_uuid });
    const item = [...target.document.items.values()].find(candidate => candidate.uuid === params.item_uuid);
    if (!item) fail("DocumentNotFound", "Item does not belong to the selected token Actor.", "Call list_actor_items for that token and reuse its Item UUID and token_uuid.");
    requirePermission(item); supported(item);
    return { document: item, actor: target.document, token: target.token, identity: documentIdentity(item, target.document, target.token) };
  }
  if (params.item_uuid.startsWith("Scene.")) fail("InvalidRequest", "Synthetic-owned Item reads also require token_uuid.", "Reuse the Item UUID and token_uuid from list_actor_items.");
  const item = await resolve(params.item_uuid, "Item");
  const actor = item.parent?.documentName === "Actor" ? item.parent : null;
  if (actor) { requirePermission(actor); supported(actor); }
  supported(item);
  return { document: item, actor, token: null, identity: documentIdentity(item, actor, null) };
}

/** Build owned Item identity; PF2e-specific 8.6.1 type filter, no derived data. */
export function embeddedIdentity(item, owner) {
  requirePermission(item); supported(item);
  return documentIdentity(item, owner.document, owner.token);
}
