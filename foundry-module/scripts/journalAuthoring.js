/** Core14 world-journal authoring boundary; no PF2e/private system APIs.
 * Public Document.toObject/getFlag/update/create, embedded creation and keepId:
 * https://foundryvtt.com/api/v14/classes/foundry.abstract.Document.html
 * https://foundryvtt.com/api/v14/interfaces/foundry.abstract.types.DatabaseCreateOperation.html
 * JournalEntry/JournalEntryPage/Folder schema fields, not sheet or DOM state.
 * GM prose is checked by the caller; exact current guidance is checked here.
 */
import {fail, validateParams, integer, digest} from './actorReadUtils.js';
import {getWritingGuidance} from './writingGuidance.js';
import {normalizeTextHTML} from './textHtml.js';
import {formatJournalHTML, journalPlayers} from './journalAuthoringOptions.js';

const encoder = new TextEncoder(), ledgers = new WeakMap();
const bytes = value => encoder.encode(JSON.stringify(value)).length;
const localId = value => typeof value === 'string' && /^[^.\s#]{1,64}$/.test(value);
const pageUuid = value => typeof value === 'string' && /^JournalEntry\.[^.\s#]+\.JournalEntryPage\.[^.\s#]+$/.test(value) && value.length <= 512;
const revision = value => typeof value === 'string' && value.length > 0 && value.length <= 128;
const named = name => ({name: [...name].slice(0, 256).join(''), name_truncated: [...name].length > 256});

function ready() {
  if (!globalThis.game?.ready || !game.journal || !game.folders || !game.users || !game.world?.id) fail('NotReady', 'Wait for the existing world.');
  if (!game.user?.isGM) fail('PermissionDenied', 'Journal authoring requires the connected GM.');
  if (!String(game.version).startsWith('14.')) fail('UnsupportedVersion', 'Journal authoring requires Foundry14.');
}
function permission(doc) {
  if (doc.inCompendium || doc.compendium) fail('UnsupportedDocument', 'Compendium journals are strictly read-only.');
  if (!doc.testUserPermission(game.user, 'OWNER')) fail('PermissionDenied', 'The selected journal document is not writable by the GM.');
}

/** Canonical selectors are shared with journal readers; names never resolve. */
function resolve(target) {
  validateParams(target, target?.kind === 'folder' ? ['kind', 'folder_id'] : target?.kind === 'journal' ? ['kind', 'journal_id'] : ['kind', 'page_uuid']);
  let doc;
  if (target.kind === 'folder' && localId(target.folder_id)) {
    doc = game.folders.get(target.folder_id);
    if (doc && doc.type !== 'JournalEntry') fail('UnsupportedType', 'Choose a JournalEntry folder from get_journal_tree.');
  } else if (target.kind === 'journal' && localId(target.journal_id)) doc = game.journal.get(target.journal_id);
  else if (target.kind === 'page' && pageUuid(target.page_uuid)) {
    const [, entryId, , id] = target.page_uuid.split('.');
    const entry = game.journal.get(entryId);
    if (!entry) fail('DocumentNotFound', 'Journal entry missing; rediscover it.');
    permission(entry); doc = entry.pages.get(id);
  } else fail('InvalidRequest', 'Use a canonical world journal/folder ID or page UUID from the journal readers.');
  if (!doc) fail('DocumentNotFound', 'Selected journal document is missing; rediscover it.');
  permission(doc);
  return doc;
}

function identity(doc, source) {
  const base = {uuid: doc.uuid, ...named(source.name)};
  if (doc.documentName === 'Folder') return {...base, kind: 'folder', folder_id: doc.id, parent_folder_id: source.folder ?? null};
  if (doc.documentName === 'JournalEntry') return {...base, kind: 'journal', journal_id: doc.id, folder_id: source.folder ?? null};
  return {...base, kind: 'page', page_uuid: doc.uuid, page_id: doc.id, journal_id: doc.parent.id, type: source.type};
}

/** Selected source snapshot: revision covers only this document's editable
 * source/ownership and its containing entry/folder context, not unrelated prose.
 * No entire source document or flags are returned to the LLM.
 */
function snapshot(doc) {
  permission(doc);
  const source = doc.toObject(true);
  if (typeof source.name !== 'string') fail('ReadFailed', 'Selected source name is malformed.');
  const data = {name: source.name, folder: source.folder, sort: source.sort, ownership: source.ownership};
  if (doc.documentName === 'Folder') Object.assign(data, {type: source.type, color: source.color, sorting: source.sorting});
  if (doc.documentName === 'JournalEntry') {
    if (doc.pages.size > 1000) fail('ReadFailed', 'Journal authoring context exceeds 1000 pages.');
    data.pages = [...doc.pages.values()].map(page => ({id: page.id, type: page.type})).sort((a,b) => a.id.localeCompare(b.id));
  }
  if (doc.documentName === 'JournalEntryPage') {
    permission(doc.parent);
    Object.assign(data, {type: source.type, category: source.category, text: source.type === 'text' ? source.text : null,
      parent: {uuid: doc.parent.uuid, name: doc.parent.name, folder: doc.parent.folder?.id ?? null, ownership: doc.parent.toObject(true).ownership}});
    if ((source.text?.content?.length ?? 0) + (source.text?.markdown?.length ?? 0) > 1000000) fail('ReadFailed', 'Page source exceeds one million UTF-16 units.');
  }
  const ancestors = [], seen = new Set();
  for (let parent = doc.documentName === 'Folder' ? doc.folder : doc.documentName === 'JournalEntry' ? doc.folder : doc.parent.folder; parent; parent = parent.folder) {
    if (seen.has(parent.id) || seen.size >= 64) fail('InvalidHierarchy', 'Folder ancestry is cyclic or too deep.');
    seen.add(parent.id); permission(parent); ancestors.push({id: parent.id, name: parent.name});
  }
  return {source, identity: identity(doc, source), data: {...data, ancestors}};
}

function follow(id) {
  return id.kind === 'folder' ? {tool: 'get_journal_tree', arguments: {folder_id: id.folder_id}}
    : id.kind === 'journal' ? {tool: 'get_journal_contents', arguments: {journal_id: id.journal_id}}
      : {tool: 'read_journal_page', arguments: {page_uuid: id.page_uuid}};
}

/** Read a small named edit context; revisions are change markers, not locks. */
export async function getJournalWriteContext(params = {}) {
  validateParams(params, ['target', 'max_bytes']); ready();
  const max = integer(params.max_bytes, 8000, 8000, 48000, 'max_bytes');
  const doc = resolve(params.target), first = snapshot(doc), serial = JSON.stringify(first.data);
  const rev = await digest(first.data);
  ready();
  if (JSON.stringify(snapshot(resolve(params.target)).data) !== serial) fail('ContentChanged', 'Document changed during context reading; reread it.');
  const ownership = first.source.ownership;
  const result = {identity: first.identity, revision: rev, sort: first.source.sort ?? null,
    ownership_default: doc.documentName === 'Folder' ? null : {present: Object.hasOwn(ownership ?? {}, 'default'), ...(Object.hasOwn(ownership ?? {}, 'default') ? {value: ownership.default} : {})},
    read_next_call: follow(first.identity)};
  if (bytes(result) > max) fail('ResponseTooLarge', 'Raise max_bytes for this edit context.');
  return result;
}

function ownershipSelection(params) {
  const root = resolve(params.target), recursive = params.recursive ?? false;
  if (typeof recursive !== 'boolean') fail('InvalidRequest', 'recursive must be boolean.');
  const limit = integer(params.limit, 10, 1, 100, 'limit');
  if (root.documentName !== 'Folder' && (recursive || params.journal_ids !== undefined)) fail('InvalidRequest', 'recursive/journal_ids are folder-only selectors.');
  const ids = params.journal_ids;
  if (ids !== undefined && (!Array.isArray(ids) || !ids.length || ids.length > 100 || ids.some(id => !localId(id)) || new Set(ids).size !== ids.length)) fail('InvalidRequest', 'journal_ids must be 1–100 unique returned world IDs.');
  const users = params.user_ids ?? [];
  if (!Array.isArray(users) || users.length > 100 || new Set(users).size !== users.length || users.some(id => !localId(id) || !game.users.get(id) || game.users.get(id).isGM)) fail('InvalidRequest', 'user_ids must contain at most100 unique non-GM User IDs from authoring options.');
  let documents = [root];
  if (root.documentName === 'Folder') {
    if (game.journal.size > 10000 || game.folders.size > 10000) fail('ScopeTooLarge', 'World enumeration exceeds10000 journals/folders; select individual journals.');
    const inFolder = entry => {
      const seen = new Set();
      for (let folder = entry.folder; folder; folder = recursive ? folder.folder : null) {
        if (seen.has(folder.id) || seen.size >= 64) fail('InvalidHierarchy', 'Folder ancestry is cyclic or too deep.');
        seen.add(folder.id);
        if (folder.id === root.id) return true;
      }
      return false;
    };
    documents = [...game.journal.values()].filter(inFolder);
    if (ids) {
      const available = new Set(documents.map(doc => doc.id));
      if (ids.some(id => !available.has(id))) fail('InvalidRequest', 'A journal_ids selector is outside the selected folder scope; rediscover.');
      documents = documents.filter(doc => ids.includes(doc.id));
    }
  }
  if (documents.length > limit) fail('ScopeTooLarge', `Selected scope contains ${documents.length} journals; raise limit up to100 or select a smaller journal_ids subset from get_journal_tree. No writes occurred.`);
  documents.sort((a,b) => a.uuid.localeCompare(b.uuid));
  return {root, documents, users, recursive, ids: ids ? [...ids].sort() : null, limit};
}

function ownershipState(params) {
  const selection = ownershipSelection(params);
  const snapshots = selection.documents.map(snapshot);
  return {...selection, snapshots, data: [game.world.id, snapshot(selection.root).data,
    selection.recursive, selection.ids, selection.users, journalPlayers(), [...game.users.values()].map(user => [user.id, user.isGM]).sort(),
    snapshots.map(snap => [snap.identity.uuid, snap.data])]};
}

/** Preview an explicit bounded batch; folders carry no persisted ownership. */
export async function getJournalOwnershipContext(params = {}) {
  validateParams(params, ['target', 'recursive', 'journal_ids', 'user_ids', 'limit', 'max_bytes']); ready();
  const max = integer(params.max_bytes, 8000, 8000, 48000, 'max_bytes');
  const state = ownershipState(params), serial = JSON.stringify(state.data), world = game.world.id, user = game.user;
  const revision = await digest(state.data);
  ready();
  if (world !== game.world.id || user !== game.user || JSON.stringify(ownershipState(params).data) !== serial) fail('ContentChanged', 'Ownership scope changed; obtain a fresh preview.');
  const stored = ownership => ({present: Object.hasOwn(ownership ?? {}, 'default'), ...(Object.hasOwn(ownership ?? {}, 'default') ? {value: ownership.default} : {})});
  const entries = state.snapshots.map((snap, index) => {
    const doc = state.documents[index], ownership = snap.source.ownership ?? {};
    return {identity: snap.identity, ownership_default: stored(ownership), players: state.users.map(id => ({user_id: id,
      present: Object.hasOwn(ownership, id), ...(Object.hasOwn(ownership, id) ? {value: ownership[id]} : {}),
      can_observe: doc.testUserPermission(game.users.get(id), 'OBSERVER'),
      parent_can_observe: doc.documentName === 'JournalEntryPage' ? doc.parent.testUserPermission(game.users.get(id), 'OBSERVER') : null}))};
  });
  const result = {target: snapshot(state.root).identity, revision, count: entries.length, recursive: state.recursive, entries,
    limitations: ['Folder ownership applies only to these existing journals; no inherited ACL or future-entry policy.',
      'Stored ownership and current OBSERVER checks are distinct; page access also depends on its parent and Foundry rendering. Limited is not full text read access.']};
  if (bytes(result) > max) fail('ResponseTooLarge', 'Raise max_bytes or select fewer journals/users; no preview is truncated.');
  return result;
}

const LEVELS = {none: 0, limited: 1, observer: 2, owner: 3};
function validateOwnershipAction(action) {
  if (!revision(action.expected_revision)) fail('InvalidRequest', 'Pass expected_revision from get_journal_ownership_context.');
  if (!['no_change', ...Object.keys(LEVELS)].includes(action.all_players ?? 'no_change')) fail('InvalidRequest', 'Choose no_change/none/limited/observer/owner.');
  const players = action.players ?? [];
  if (!Array.isArray(players) || players.length > 100) fail('InvalidRequest', 'players must contain at most100 overrides.');
  const seen = new Set();
  for (const player of players) {
    validateParams(player, ['user_id', 'level']);
    if (!localId(player.user_id) || seen.has(player.user_id) || !['no_change', ...Object.keys(LEVELS)].includes(player.level)) fail('InvalidRequest', 'Use unique player User IDs and published ownership levels.');
    seen.add(player.user_id);
  }
  if ((action.all_players ?? 'no_change') === 'no_change' && players.every(player => player.level === 'no_change')) fail('InvalidRequest', 'Select at least one actual ownership change.');
}

async function executeOwnership(params, fingerprint, context, state) {
  const a = params.action, before = ownershipState(a), serial = JSON.stringify(before.data);
  for (const player of a.players ?? []) if (!game.users.get(player.user_id) || game.users.get(player.user_id).isGM) fail('PermissionDenied', 'GM users cannot be ownership targets; rediscover player IDs.');
  const applied = before.documents.map(doc => prior(doc, params.request_id, fingerprint));
  const fullyReplayed = applied.length > 0 && applied.every(Boolean);
  if (!fullyReplayed && await digest(before.data) !== a.expected_revision) fail('ContentChanged', 'Ownership preview changed; reconcile completed targets and obtain a new preview.');
  const entries = before.snapshots.map((snap, i) => ({identity: snap.identity, status: applied[i] ? 'already_applied' : 'updated'}));
  const result = {request_id: params.request_id, status: 'complete', count: entries.length, entries};
  // Reserve worst-case per-document error fields before any mutation.
  if (bytes({...result, entries: entries.map(entry => ({...entry, status: 'not_attempted', error: 'WriteOutcomeUnknown'}))}) > (params.max_bytes ?? 8000)) fail('ResponseTooLarge', 'Raise max_bytes or select fewer journals before writing.');
  const plans = before.documents.map((doc, i) => {
    const ownership = gmOwnership(before.snapshots[i].source.ownership);
    if ((a.all_players ?? 'no_change') !== 'no_change') ownership.default = LEVELS[a.all_players];
    for (const player of a.players ?? []) if (player.level !== 'no_change') ownership[player.user_id] = LEVELS[player.level];
    return {doc, data: {ownership, 'flags.foundry-mcp.journalWrites': historyFlags(doc, params.request_id, fingerprint)}};
  });
  ready(); guidance(params.expected_guidance);
  if (game !== context.game || game.world.id !== context.world || game.user !== context.user || JSON.stringify(ownershipState(a).data) !== serial) fail('ContentChanged', 'Ownership scope or GM changed before writing.');
  for (let i = 0; i < plans.length; i++) {
    if (applied[i]) continue;
    try {
      ready(); guidance(params.expected_guidance);
      if (game !== context.game || game.world.id !== context.world || game.user !== context.user) fail('ContextChanged', 'World/GM changed.');
      if (JSON.stringify(snapshot(plans[i].doc).data) !== JSON.stringify(before.snapshots[i].data)) fail('ContentChanged', 'A selected document changed.');
      state.started = true;
      await plans[i].doc.update(plans[i].data);
    } catch (error) {
      result.status = 'partial';
      entries[i].status = 'failed'; entries[i].error = error.rpcError?.code ?? 'WriteOutcomeUnknown';
      for (let next = i + 1; next < entries.length; next++) if (!applied[next]) entries[next].status = 'not_attempted';
      break;
    }
  }
  return result;
}

const ACTIONS = {
  set_ownership: ['target', 'recursive', 'journal_ids', 'user_ids', 'limit', 'expected_revision', 'all_players', 'players'],
  create_folder: ['name', 'parent_folder_id', 'parent_revision', 'color', 'sorting', 'sort'],
  update_folder: ['folder_id', 'expected_revision', 'name', 'parent_folder_id', 'parent_revision', 'color', 'sorting', 'sort'],
  create_journal: ['name', 'folder_id', 'parent_revision', 'sort'],
  update_journal: ['journal_id', 'expected_revision', 'name', 'folder_id', 'parent_revision', 'sort'],
  create_page: ['journal_id', 'parent_revision', 'name', 'type', 'content', 'sort', 'format'],
  update_page: ['page_uuid', 'expected_revision', 'name', 'content', 'mode', 'sort', 'format'],
};
function validateAction(action) {
  if (!ACTIONS[action?.operation]) fail('InvalidRequest', 'Choose a published journal-writing operation.');
  validateParams(action, ['operation', ...ACTIONS[action.operation]]);
  if (action.operation === 'set_ownership') {validateOwnershipAction(action); return;}
  const create = action.operation.startsWith('create_');
  if ((create || Object.hasOwn(action, 'name')) && (typeof action.name !== 'string' || !action.name.trim() || [...action.name].length > 256)) fail('InvalidRequest', 'name must contain 1–256 Unicode characters.');
  for (const key of ['folder_id', 'journal_id', 'parent_folder_id']) if (Object.hasOwn(action, key) && action[key] !== null && !localId(action[key])) fail('InvalidRequest', 'Use a returned local ID for ' + key + '.');
  if (action.operation === 'update_page' && !pageUuid(action.page_uuid)) fail('InvalidRequest', 'Use a returned world page_uuid.');
  if (!create && !revision(action.expected_revision)) fail('InvalidRequest', 'An update requires expected_revision from get_journal_write_context.');
  if (action.operation === 'create_page' && (!localId(action.journal_id) || !revision(action.parent_revision))) fail('InvalidRequest', 'Page creation requires its journal ID and parent revision.');
  if (Object.hasOwn(action, 'type') && action.type !== 'text') fail('InvalidRequest', 'Only type=text is supported.');
  if (Object.hasOwn(action, 'color') && action.color !== null && (typeof action.color !== 'string' || !/^#[0-9a-fA-F]{6}$/.test(action.color))) fail('InvalidRequest', 'Folder color must be #RRGGBB or null.');
  if (Object.hasOwn(action, 'sorting') && !['alphabetical', 'manual'].includes(action.sorting)) fail('InvalidRequest', 'Choose alphabetical or manual sorting.');
  if (Object.hasOwn(action, 'sort')) integer(action.sort, 0, -2147483648, 2147483647, 'sort');
  if ((action.operation === 'create_page' || Object.hasOwn(action, 'content')) && (typeof action.content !== 'string' || encoder.encode(action.content).length > 16000)) fail('InvalidRequest', 'Page content must be HTML within 16000 UTF-8 bytes.');
  if (Object.hasOwn(action, 'mode') && (!Object.hasOwn(action, 'content') || !['replace', 'append'].includes(action.mode))) fail('InvalidRequest', 'mode requires content and must be replace or append.');
  if (Object.hasOwn(action, 'format') && !Object.hasOwn(action, 'content')) fail('InvalidRequest', 'format requires content; it wraps only the supplied fragment.');
  if (!create && !ACTIONS[action.operation].some(key => !['folder_id', 'journal_id', 'page_uuid', 'expected_revision', 'parent_revision', 'mode'].includes(key) && Object.hasOwn(action, key))) fail('InvalidRequest', 'An update needs at least one changed field.');
}

function guidance(expected) {
  const current = getWritingGuidance();
  if (!expected || current.world_id !== expected.world_id || current.saved_at !== expected.saved_at || current.html !== expected.html) fail('GuidanceChanged', 'Writing guidance changed; call get_writing_guidance and reconsider the requested edit.');
}
function gmOwnership(original = {}) {
  const result = {...original};
  for (const user of game.users.values()) if (user.isGM) result[user.id] = 3;
  return result;
}
function prior(doc, id, fingerprint) {
  const value = doc.getFlag('foundry-mcp', 'journalWrites')?.[id];
  if (value === undefined) return false;
  if (value !== fingerprint) fail('RequestConflict', 'This request_id was already used with different input.');
  return true;
}
function historyFlags(doc, id, fingerprint) {
  const previous = doc?.getFlag('foundry-mcp', 'journalWrites') ?? {};
  if (Object.keys(previous).length >= 1000 && !Object.hasOwn(previous, id)) fail('WriteHistoryFull', 'This document has 1000 retained write receipts; reconcile history with the GM before further automation.');
  return {...previous, [id]: fingerprint};
}
async function receipt(doc, requestId, status, maxBytes) {
  const snap = snapshot(doc);
  const result = {request_id: requestId, status, identity: snap.identity, revision: await digest(snap.data), read_next_call: follow(snap.identity)};
  if (bytes(result) > maxBytes) fail('ResponseTooLarge', 'Mutation may have completed; read the target before any retry.');
  return result;
}

async function checkedRevision(doc, expected) {
  const first = snapshot(doc), serial = JSON.stringify(first.data);
  if (await digest(first.data) !== expected) fail('ContentChanged', 'Document or destination changed; read it and get a new write context.');
  ready();
  if (JSON.stringify(snapshot(doc).data) !== serial) fail('ContentChanged', 'Document changed while checking its revision.');
  return first.source;
}

async function execute(params, fingerprint, context, state) {
  ready(); guidance(params.expected_guidance);
  if (game !== context.game || game.world.id !== context.world || game.user !== context.user) fail('ContextChanged', 'World or GM changed; reconcile in the original world.');
  if (params.action.operation === 'set_ownership') return executeOwnership(params, fingerprint, context, state);
  const a = params.action, create = a.operation.startsWith('create_'), max = params.max_bytes ?? 8000;
  let parent = null, doc = null, source = null;
  const kind = a.operation.endsWith('folder') ? 'Folder' : a.operation.endsWith('journal') ? 'JournalEntry' : 'JournalEntryPage';
  const parentId = kind === 'Folder' ? a.parent_folder_id : kind === 'JournalEntry' ? a.folder_id : a.journal_id;
  if (parentId != null) {
    parent = resolve(kind === 'JournalEntryPage' ? {kind: 'journal', journal_id: parentId} : {kind: 'folder', folder_id: parentId});
    if (!revision(a.parent_revision)) fail('InvalidRequest', 'A selected destination requires parent_revision from get_journal_write_context.');
  }
  let id;
  if (create) {
    id = (await digest([context.world, kind, parentId ?? null, params.request_id])).replace(/[^A-Za-z0-9]/g, '').slice(-16).padStart(16, '0');
    doc = kind === 'Folder' ? game.folders.get(id) : kind === 'JournalEntry' ? game.journal.get(id) : parent.pages.get(id);
    if (doc) {
      permission(doc);
      if (!prior(doc, params.request_id, fingerprint)) fail('RequestConflict', 'Generated ID is occupied; choose a new request_id after reconciling the existing document.');
      return receipt(doc, params.request_id, 'already_applied', max);
    }
  } else {
    doc = resolve(kind === 'Folder' ? {kind: 'folder', folder_id: a.folder_id} : kind === 'JournalEntry' ? {kind: 'journal', journal_id: a.journal_id} : {kind: 'page', page_uuid: a.page_uuid});
    if (prior(doc, params.request_id, fingerprint)) return receipt(doc, params.request_id, 'already_applied', max);
    source = await checkedRevision(doc, a.expected_revision);
  }
  if (parent) await checkedRevision(parent, a.parent_revision);
  const data = {};
  for (const key of ['name', 'sort', 'color']) if (Object.hasOwn(a, key)) data[key] = a[key];
  if (Object.hasOwn(a, 'sorting')) data.sorting = a.sorting === 'manual' ? 'm' : 'a';
  const folderKey = kind === 'Folder' ? 'parent_folder_id' : 'folder_id';
  if (kind !== 'JournalEntryPage' && Object.hasOwn(a, folderKey)) data.folder = a[folderKey];
  if (kind === 'Folder') {
    if (create) {data.type = 'JournalEntry'; data.folder ??= null; data.sorting ??= 'a';}
    for (let next = parent, seen = new Set(); next; next = next.folder) {
      if (next === doc || seen.has(next.id) || seen.size >= 64) fail('InvalidHierarchy', 'Folder move would create cyclic/deep ancestry.');
      seen.add(next.id);
    }
  } else {
    data.ownership = gmOwnership(create ? {default: kind === 'JournalEntryPage' ? -1 : 0} : source.ownership);
    if (create && kind === 'JournalEntry') data.folder ??= null;
  }
  if (kind === 'JournalEntryPage') {
    if (!create && source.type !== 'text') fail('UnsupportedType', 'Only text pages can be edited; choose a text page or create a new one.');
    if (create) data.type = 'text';
    if (Object.hasOwn(a, 'content')) {
      const content = normalizeTextHTML(formatJournalHTML(a.content, a.format), {links: true});
      if (!create && a.mode === 'append' && source.text?.format !== CONST.JOURNAL_ENTRY_PAGE_FORMATS.HTML) fail('UnsupportedFormat', 'Appending requires an HTML page; read and explicitly replace other formats.');
      const combined = (!create && a.mode === 'append' ? source.text?.content ?? '' : '') + content;
      if (combined.length > 1000000) fail('InvalidRequest', 'The resulting page exceeds one million UTF-16 units.');
      data['text.content'] = combined; data['text.format'] = CONST.JOURNAL_ENTRY_PAGE_FORMATS.HTML; data['text.markdown'] = '';
    }
  }
  const flags = historyFlags(doc, params.request_id, fingerprint);
  if (create) {
    data._id = id; data.flags = {'foundry-mcp': {journalWrites: flags}};
    // Embedded creation takes nested page source; update uses documented paths.
    if (kind === 'JournalEntryPage') {
      data.text = {content: data['text.content'], format: data['text.format'], markdown: ''};
      delete data['text.content']; delete data['text.format']; delete data['text.markdown'];
    }
  } else data['flags.foundry-mcp.journalWrites'] = flags;
  ready(); guidance(params.expected_guidance);
  if (game !== context.game || game.world.id !== context.world || game.user !== context.user) fail('ContextChanged', 'World or GM changed before writing.');
  state.started = true;
  try {
    if (create) doc = kind === 'JournalEntryPage'
      ? (await parent.createEmbeddedDocuments(kind, [data], {keepId: true, renderSheet: false}))[0]
      : await foundry.documents[kind].implementation.create(data, {keepId: true, renderSheet: false});
    else doc = await doc.update(data);
  } catch {
    fail('WriteOutcomeUnknown', 'Foundry did not confirm this write; inspect its source and reuse the identical request_id only after reconciliation.');
  }
  if (!doc) fail('WriteOutcomeUnknown', 'Foundry returned no document; reconcile before retrying.');
  return receipt(doc, params.request_id, create ? 'created' : 'updated', max);
}

/** Shared serial/coalescing mutation boundary. Stable create IDs plus retained
 * request flags prevent duplicate creates/repeated appends after reconnects.
 * expected_guidance/request_digest are server-validated internal RPC fields,
 * not caller-controlled document patches or a way to change GM instructions.
 */
export async function writeJournal(params = {}) {
  validateParams(params, ['request_id', 'gm_authorized', 'action', 'expected_guidance', 'request_digest', 'max_bytes']);
  if (typeof params.request_id !== 'string' || !/^[A-Za-z0-9-]{16,64}$/.test(params.request_id)) fail('InvalidRequest', 'Use a unique request_id of 16–64 letters/digits/hyphens.');
  if (params.gm_authorized !== true) fail('PermissionDenied', 'Confirm the GM explicitly authorized this edit, including any permission required by writing guidance.');
  if (typeof params.request_digest !== 'string' || !/^[0-9a-f]{64}$/.test(params.request_digest)) fail('InvalidRequest', 'Missing server-validated request digest.');
  validateAction(params.action); integer(params.max_bytes, 8000, 8000, 48000, 'max_bytes');
  ready();
  const context = {game, world: game.world.id, user: game.user};
  const fingerprint = await digest([context.world, params.request_id, params.action, params.request_digest]);
  if (game !== context.game || game.world.id !== context.world || game.user !== context.user) fail('ContextChanged', 'World or GM changed before admission.');
  let ledger = ledgers.get(game);
  if (!ledger) {ledger = {requests: new Map(), tail: Promise.resolve()}; ledgers.set(game, ledger);}
  const key = context.world + ':' + params.request_id, previous = ledger.requests.get(key);
  if (previous) {
    guidance(params.expected_guidance);
    if (previous.fingerprint !== fingerprint) fail('RequestConflict', 'Reuse request_id only with identical write inputs.');
    return previous.promise;
  }
  if (ledger.requests.size >= 1000) fail('WriteLedgerFull', 'Reconcile pending writes before reloading the GM browser.');
  const state = {fingerprint, started: false};
  state.promise = ledger.tail.then(() => execute(params, fingerprint, context, state));
  ledger.requests.set(key, state);
  ledger.tail = state.promise.catch(() => {if (!state.started) ledger.requests.delete(key);});
  return state.promise;
}
