import test from 'node:test';
import assert from 'node:assert/strict';
import {webcrypto} from 'node:crypto';
import {getJournalWriteContext, getJournalOwnershipContext, writeJournal} from '../../foundry-module/scripts/journalAuthoring.js';
import {registerWritingGuidanceSettings, getWritingGuidance} from '../../foundry-module/scripts/writingGuidance.js';
import {getJournalAuthoringOptions} from '../../foundry-module/scripts/journalAuthoringOptions.js';
import {insertJournalImage} from '../../foundry-module/scripts/journalImageEmbedding.js';

globalThis.crypto ??= webcrypto;

export function fixture() {
  const settings = new Map(), created = [], updates = [];
  const gm = {id: 'gm', isGM: true, name: 'GM'};
  globalThis.game = {ready: true, version: '14.369', world: {id: 'test'}, user: gm,
    users: new Map([['gm', gm], ['player', {id: 'player', isGM: false, name: 'Player'}]]),
    folders: new Map(), journal: new Map(), settings: {
      register(ns, key, options) {settings.set(key, structuredClone(options.default));},
      get(ns, key) {return structuredClone(settings.get(key));}
    }};
  registerWritingGuidanceSettings();
  globalThis.CONST = {JOURNAL_ENTRY_PAGE_FORMATS: {HTML: 1}};
  globalThis.DOMParser = class {parseFromString(html) {return {querySelectorAll: () => [], body: {innerHTML: html, textContent: html}};}};
  function put(target, path, value) {
    const parts = path.split('.');
    for (const key of parts.slice(0, -1)) target = target[key] ??= {};
    target[parts.at(-1)] = structuredClone(value);
  }
  class Doc {
    constructor(kind, data, parent = null) {
      this.documentName = kind; this.data = structuredClone(data); this.id = data._id;
      this.parent = parent; this.pages = new Map(); this.categories = new Map();
      this.uuid = parent ? parent.uuid + '.' + kind + '.' + this.id : kind + '.' + this.id;
      this.compendium = null; this.inCompendium = false;
    }
    get name() {return this.data.name;}
    get type() {return this.data.type;}
    get folder() {return game.folders.get(this.data.folder) ?? null;}
    testUserPermission() {return !this.denied;}
    toObject(source) {assert.equal(source, true); return structuredClone(this.data);}
    getFlag(ns, key) {return this.data.flags?.[ns]?.[key];}
    async update(patch) {
      if (this.writeError) throw Error('Simulated server write error');
      updates.push({uuid: this.uuid, patch});
      for (const [key, value] of Object.entries(patch)) put(this.data, key, value);
      return this;
    }
    async createEmbeddedDocuments(kind, rows, options) {
      assert.equal(options.keepId, true);
      return rows.map(row => {
        const collection = kind === 'JournalEntryPage' ? this.pages : this.categories;
        if (collection.has(row._id)) throw Error('Duplicate ID');
        const doc = new Doc(kind, row, this); collection.set(doc.id, doc); created.push(doc); return doc;
      });
    }
  }
  function factory(kind, collection) {
    return {implementation: {async create(data, options) {
      assert.equal(options.keepId, true);
      if (collection.has(data._id)) throw Error('Duplicate ID');
      const doc = new Doc(kind, data); collection.set(doc.id, doc); created.push(doc); return doc;
    }}};
  }
  globalThis.foundry = {documents: {Folder: factory('Folder', game.folders), JournalEntry: factory('JournalEntry', game.journal)},
    applications: {settings: {menus: {FontConfig: {getAvailableFonts: () => ['Arial', '文字']}}}}};
  const folder = new Doc('Folder', {_id: 'folder', type: 'JournalEntry', name: 'Notes', folder: null, sorting: 'a'});
  game.folders.set(folder.id, folder);
  const journal = new Doc('JournalEntry', {_id: 'entry', name: 'Handout', folder: folder.id, ownership: {default: 0}});
  game.journal.set(journal.id, journal);
  const page = new Doc('JournalEntryPage', {_id: 'page', name: 'Text', type: 'text', text: {content: '<p>Before</p>', format: 1}, ownership: {default: -1}}, journal);
  journal.pages.set(page.id, page);
  return {folder, journal, page, created, updates, settings};
}

let serial = 0;
async function request(action, extra = {}) {
  const id = 'journal-request-' + String(++serial).padStart(8, '0');
  return {request_id: id, gm_authorized: true, action, expected_guidance: getWritingGuidance(),
    request_digest: 'a'.repeat(64), ...extra};
}
const code = value => error => error.rpcError?.code === value;

test('world folder and entry creation keep reader selectors, GM access and retry identities', async () => {
  const f = fixture();
  const folder = await writeJournal(await request({operation: 'create_folder', name: 'Preparation', color: '#254c84', sorting: 'manual'}));
  assert.equal(folder.identity.kind, 'folder');
  assert.equal(game.folders.get(folder.identity.folder_id).data.sorting, 'm');
  const p = await request({operation: 'create_journal', name: 'New handout'});
  const first = await writeJournal(p), retry = await writeJournal(p);
  assert.equal(first.identity.journal_id, retry.identity.journal_id);
  assert.equal(f.created.length, 2);
  assert.equal(game.journal.get(first.identity.journal_id).data.ownership.gm, 3);
  assert.equal(first.read_next_call.tool, 'get_journal_contents');
  await assert.rejects(writeJournal({...p, request_digest: 'b'.repeat(64)}), code('RequestConflict'));
});

test('page create, append, replace and rename preserve siblings and use actual read page UUIDs', async () => {
  const f = fixture(), original = JSON.stringify(f.page.data);
  const parent = await getJournalWriteContext({target: {kind: 'journal', journal_id: 'entry'}});
  const created = await writeJournal(await request({operation: 'create_page', journal_id: 'entry', parent_revision: parent.revision,
    name: 'Session notes', type: 'text', content: '<p>First</p>'}));
  assert.equal(created.identity.page_uuid, 'JournalEntry.entry.JournalEntryPage.' + created.identity.page_id);
  assert.equal(created.read_next_call.tool, 'read_journal_page');
  const target = {kind: 'page', page_uuid: created.identity.page_uuid};
  let context = await getJournalWriteContext({target});
  const append = await request({operation: 'update_page', page_uuid: target.page_uuid, expected_revision: context.revision,
    content: '<p>Second</p>', mode: 'append', name: 'Updated notes'});
  await writeJournal(append); await writeJournal(append);
  const page = f.journal.pages.get(created.identity.page_id);
  assert.equal(page.data.text.content, '<p>First</p><p>Second</p>');
  context = await getJournalWriteContext({target});
  await writeJournal(await request({operation: 'update_page', page_uuid: target.page_uuid, expected_revision: context.revision, content: '<p>Replacement</p>'}));
  assert.equal(page.data.text.content, '<p>Replacement</p>');
  assert.equal(page.data.name, 'Updated notes');
  assert.equal(JSON.stringify(f.page.data), original);
});

test('stale document or guidance revisions and missing GM authorization reject before mutation', async () => {
  const f = fixture(), target = {kind: 'page', page_uuid: f.page.uuid};
  const context = await getJournalWriteContext({target});
  const p = await request({operation: 'update_page', page_uuid: f.page.uuid, expected_revision: context.revision, content: 'New'});
  f.page.data.text.content = 'Manual GM change';
  await assert.rejects(writeJournal(p), code('ContentChanged')); assert.equal(f.updates.length, 0);
  const next = await request({operation: 'create_journal', name: 'Notes'});
  f.settings.set('writingGuidance', {html: 'New GM rules', saved_at: '2026-10-31T21:00:00.000Z'});
  await assert.rejects(writeJournal(next), code('GuidanceChanged')); assert.equal(f.created.length, 0);
  await assert.rejects(writeJournal({...next, gm_authorized: false}), code('PermissionDenied'));
});

test('deterministic create IDs and persisted request flags prevent duplicate creation after module reload', async () => {
  const f = fixture(), p = await request({operation: 'create_journal', name: 'One only'});
  const first = await writeJournal(p);
  const fresh = await import('../../foundry-module/scripts/journalAuthoring.js?retry-test');
  const second = await fresh.writeJournal(p);
  assert.equal(first.identity.uuid, second.identity.uuid); assert.equal(f.created.length, 1);
});

test('compendium/nontext/denied targets, malformed inputs and folder cycles cannot cause writes', async () => {
  const f = fixture();
  await assert.rejects(getJournalWriteContext({target: {kind: 'page', page_uuid: 'Compendium.pack.JournalEntry.entry.JournalEntryPage.page'}}), code('InvalidRequest'));
  f.page.data.type = 'image';
  const context = await getJournalWriteContext({target: {kind: 'page', page_uuid: f.page.uuid}});
  await assert.rejects(writeJournal(await request({operation: 'update_page', page_uuid: f.page.uuid, expected_revision: context.revision, content: 'x'})), code('UnsupportedType'));
  f.journal.denied = true;
  await assert.rejects(getJournalWriteContext({target: {kind: 'journal', journal_id: 'entry'}}), code('PermissionDenied'));
  await assert.rejects(writeJournal(await request({operation: 'create_folder', name: 'X', color: 'red'})), code('InvalidRequest'));
  await assert.rejects(writeJournal(await request({operation: 'create_page', journal_id: 'entry', parent_revision: 'x', name: 'X', type: 'video', content: 'x'})), code('InvalidRequest'));
  assert.equal(f.created.length, 0); assert.equal(f.updates.length, 0);
});

test('authoring options paginate offline players without GM selectors and reject changed lists', async () => {
  fixture();
  game.users.set('offline', {id: 'offline', name: 'Offline player', isGM: false, active: false});
  let result = await getJournalAuthoringOptions({kind: 'players', limit: 1});
  assert.equal(result.total, 2); assert.equal(result.complete, false);
  assert.deepEqual(result.entries, [{user_id: 'offline', name: 'Offline player'}]);
  const cursor = result.next_cursor;
  result = await getJournalAuthoringOptions({kind: 'players', limit: 1, cursor});
  assert.equal(result.complete, true); assert.equal(result.entries[0].user_id, 'player');
  game.users.get('player').name = 'Changed';
  await assert.rejects(getJournalAuthoringOptions({kind: 'players', cursor}), code('ContentChanged'));
  const fonts = await getJournalAuthoringOptions({kind: 'fonts'});
  assert.deepEqual(fonts.entries, [{font_family: 'Arial'}, {font_family: '文字'}]);
  game.user = game.users.get('player');
  await assert.rejects(getJournalAuthoringOptions({kind: 'players'}), code('PermissionDenied'));
});

test('structured formatting wraps only the supplied fragment and validates fonts and point sizes', async () => {
  const f = fixture(), target = {kind: 'page', page_uuid: f.page.uuid};
  let context = await getJournalWriteContext({target});
  await writeJournal(await request({operation: 'update_page', page_uuid: f.page.uuid, expected_revision: context.revision,
    content: '<p>After</p>', mode: 'append', format: {font_family: '文字', font_size: 'custom', custom_size_pt: 14.5, font_color: '#254c84'}}));
  assert.equal(f.page.data.text.content, '<p>Before</p><div style="font-family: \'文字\'; font-size: 14.5pt; color: #254c84"><p>After</p></div>');
  context = await getJournalWriteContext({target});
  for (const format of [{font_size: 'custom', custom_size_pt: 0}, {font_family: 'Missing'}, {font_color: 'red'}, {font_size: 'small', custom_size_pt: 12}]) {
    await assert.rejects(writeJournal(await request({operation: 'update_page', page_uuid: f.page.uuid, expected_revision: context.revision, content: 'Bad', format})), code('InvalidRequest'));
  }
  assert.equal(f.updates.length, 1);
});

test('ownership previews and writes preserve unrelated overrides and every GM', async () => {
  const f = fixture();
  game.users.set('other', {id: 'other', name: 'Other', isGM: false});
  game.users.set('gm2', {id: 'gm2', name: 'Second GM', isGM: true});
  f.journal.data.ownership.other = 2;
  const scope = {target: {kind: 'folder', folder_id: 'folder'}, user_ids: ['player', 'other']};
  const preview = await getJournalOwnershipContext(scope);
  assert.equal(preview.count, 1); assert.equal(preview.entries[0].players[0].present, false);
  const action = {operation: 'set_ownership', ...scope, expected_revision: preview.revision,
    all_players: 'none', players: [{user_id: 'player', level: 'observer'}, {user_id: 'other', level: 'no_change'}]};
  const p = await request(action), result = await writeJournal(p);
  assert.equal(result.status, 'complete'); assert.equal(result.entries[0].status, 'updated');
  assert.deepEqual(f.journal.data.ownership, {default: 0, other: 2, player: 2, gm: 3, gm2: 3});
  await writeJournal(p); assert.equal(f.updates.length, 1);
  assert.equal(f.folder.data.ownership, undefined);
  const fresh = await import('../../foundry-module/scripts/journalAuthoring.js?ownership-retry');
  const retry = await fresh.writeJournal(p);
  assert.equal(retry.entries[0].status, 'already_applied'); assert.equal(f.updates.length, 1);
});

test('ownership rejects GM targets, changed previews and over-limit folder batches before writes', async () => {
  const f = fixture(), scope = {target: {kind: 'folder', folder_id: 'folder'}};
  const preview = await getJournalOwnershipContext(scope);
  await assert.rejects(writeJournal(await request({operation: 'set_ownership', ...scope, expected_revision: preview.revision,
    players: [{user_id: 'gm', level: 'none'}]})), code('PermissionDenied'));
  f.journal.data.ownership.player = 1;
  await assert.rejects(writeJournal(await request({operation: 'set_ownership', ...scope, expected_revision: preview.revision, all_players: 'observer'})), code('ContentChanged'));
  const parent = await getJournalWriteContext({target: scope.target});
  await writeJournal(await request({operation: 'create_journal', name: 'Other handout', folder_id: 'folder', parent_revision: parent.revision}));
  await assert.rejects(getJournalOwnershipContext({...scope, limit: 1}), code('ScopeTooLarge'));
  await assert.rejects(getJournalOwnershipContext({...scope, user_ids: ['gm']}), code('InvalidRequest'));
  assert.equal(f.updates.length, 0);
});

test('folder ownership stops after failure with per-document outcomes and no silent partial success', async () => {
  const f = fixture();
  const parent = await getJournalWriteContext({target: {kind: 'folder', folder_id: 'folder'}});
  const created = await writeJournal(await request({operation: 'create_journal', name: 'Other', folder_id: 'folder', parent_revision: parent.revision}));
  const docs = [...game.journal.values()].sort((a,b) => a.uuid.localeCompare(b.uuid));
  docs[1].writeError = true;
  const scope = {target: {kind: 'folder', folder_id: 'folder'}, recursive: true};
  const preview = await getJournalOwnershipContext(scope);
  const p = await request({operation: 'set_ownership', ...scope, expected_revision: preview.revision, all_players: 'observer'});
  const result = await writeJournal(p);
  assert.equal(result.status, 'partial');
  assert.deepEqual(result.entries.map(entry => entry.status), ['updated', 'failed']);
  assert.equal(result.entries[1].error, 'WriteOutcomeUnknown');
  assert.equal(f.updates.length, 1);
  assert.deepEqual(await writeJournal(p), result); assert.equal(f.updates.length, 1);
  assert.ok(created.identity.journal_id);
});

test('page ownership preview binds parent ownership and cannot use folder-only selectors', async () => {
  const f = fixture(), scope = {target: {kind: 'page', page_uuid: f.page.uuid}, user_ids: ['player']};
  const preview = await getJournalOwnershipContext(scope);
  assert.equal(preview.entries[0].ownership_default.value, -1);
  assert.equal(typeof preview.entries[0].players[0].parent_can_observe, 'boolean');
  f.journal.data.ownership.player = 2;
  await assert.rejects(writeJournal(await request({operation: 'set_ownership', ...scope, expected_revision: preview.revision, players: [{user_id: 'player', level: 'observer'}]})), code('ContentChanged'));
  await assert.rejects(getJournalOwnershipContext({...scope, recursive: true}), code('InvalidRequest'));
  assert.equal(f.updates.length, 0);
});

test('empty folder ownership still rejects stale preview revisions', async () => {
  const f = fixture(); game.journal.clear();
  const scope = {target: {kind: 'folder', folder_id: f.folder.id}};
  const preview = await getJournalOwnershipContext(scope);
  assert.equal(preview.count, 0);
  f.folder.data.name = 'Changed after preview';
  await assert.rejects(writeJournal(await request({operation: 'set_ownership', ...scope, expected_revision: preview.revision, all_players: 'none'})), code('ContentChanged'));
});

test('ownership receipt byte budget is checked before any large batch mutation', async () => {
  const f = fixture(); game.journal.clear();
  for (let i = 0; i < 10; i++) await foundry.documents.JournalEntry.implementation.create({_id: 'entry'+i, name: '😀'.repeat(256), folder: f.folder.id, ownership: {default: 0}}, {keepId: true});
  const scope = {target: {kind: 'folder', folder_id: f.folder.id}};
  const preview = await getJournalOwnershipContext({...scope, max_bytes: 48000});
  await assert.rejects(writeJournal(await request({operation: 'set_ownership', ...scope, expected_revision: preview.revision, all_players: 'none'})), code('ResponseTooLarge'));
  assert.equal(f.updates.length, 0);
});

test('a folder cannot move beneath itself', async () => {
  const f = fixture(), ctx = await getJournalWriteContext({target: {kind: 'folder', folder_id: f.folder.id}});
  await assert.rejects(writeJournal(await request({operation: 'update_folder', folder_id: f.folder.id, expected_revision: ctx.revision,
    parent_folder_id: f.folder.id, parent_revision: ctx.revision})), code('InvalidHierarchy'));
  assert.equal(f.updates.length, 0);
});

function imageFixture() {
  const f = fixture(), state = {loads: 0, source: 'assets/α image.png'};
  class Picker {
    constructor() {this.sources = {data: {target: ''}};}
    static async browse() {
      state.onBrowse?.();
      return {target: 'assets', dirs: [], files: state.missing ? [] : [state.source]};
    }
  }
  foundry.applications.apps = {FilePicker: {implementation: Picker}};
  globalThis.Image = class {
    naturalWidth = 80; naturalHeight = 40;
    set src(value) {if (value) {state.loads++; queueMicrotask(() => state.broken ? this.onerror?.() : this.onload?.());}}
  };
  return {...f, state, image: {source: 'data', directory: 'assets', src: state.source}};
}

test('embedding validates a selected source, escapes alt/dimensions and preserves surrounding HTML exactly on append', async () => {
  const f = imageFixture(), original = f.page.data.text.content;
  const context = await getJournalWriteContext({target: {kind: 'page', page_uuid: f.page.uuid}});
  const action = {operation: 'embed_image', page_uuid: f.page.uuid, expected_revision: context.revision, image: f.image,
    alt: 'A "map" & <route>', width: 320, height: 160};
  const p = await request(action), first = await writeJournal(p);
  assert.equal(first.identity.page_uuid, f.page.uuid);
  assert.equal(f.page.data.text.content, original + '<img src="assets/α image.png" alt="A &quot;map&quot; &amp; &lt;route&gt;" width="320" height="160">');
  assert.equal(f.page.data.ownership.gm, 3);
  await writeJournal(p); assert.equal(f.updates.length, 1); assert.equal(f.state.loads, 1);
  const fresh = await import('../../foundry-module/scripts/journalAuthoring.js?image-retry');
  const replay = await fresh.writeJournal(p);
  assert.equal(replay.status, 'already_applied'); assert.equal(f.updates.length, 1); assert.equal(f.state.loads, 1);
});

test('missing/broken images and content changed while checking the asset cause no write', async () => {
  for (const scenario of ['missing', 'broken', 'changed']) {
    const f = imageFixture(), context = await getJournalWriteContext({target: {kind: 'page', page_uuid: f.page.uuid}});
    if (scenario === 'changed') f.state.onBrowse = () => {f.page.data.text.content = 'Manual GM change';};
    else f.state[scenario] = true;
    await assert.rejects(writeJournal(await request({operation: 'embed_image', page_uuid: f.page.uuid, expected_revision: context.revision,
      image: f.image, alt: ''})), code({missing: 'ImageNotFound', broken: 'ImageUnavailable', changed: 'ContentChanged'}[scenario]));
    assert.equal(f.updates.length, 0);
  }
});

test('insertion validates dimensions and anchor combinations before native image reads', async () => {
  const f = imageFixture();
  const base = {operation: 'embed_image', page_uuid: f.page.uuid, expected_revision: 'before', image: f.image, alt: ''};
  for (const extra of [{width: 0}, {height: 8193}, {width: true}, {position: 'after'}, {anchor: {tag: 'p', text: 'Before'}},
    {image: {...f.image, src: 'javascript:bad.png'}}, {image: {...f.image, src: 'assets/image.txt'}}, {alt: '\0'}]) {
    await assert.rejects(writeJournal(await request({...base, ...extra})), code('InvalidRequest'));
  }
  assert.equal(f.state.loads, 0); assert.equal(f.updates.length, 0);
});

test('anchored insertion chooses exact unique block text and rejects absent or ambiguous matches', () => {
  const f = imageFixture();
  globalThis.DOMParser = class {parseFromString(source) {
    let value = source;
    const blocks = [...source.matchAll(/<(p|h2)>([^<]*)<\/\1>/g)];
    return {body: {get innerHTML() {return value;}, querySelectorAll: tag => blocks.filter(match => match[1] === tag).map(match => ({
      textContent: match[2], insertAdjacentHTML(position, html) {value = value.replace(match[0], position === 'beforebegin' ? html + match[0] : match[0] + html);}
    }))}};
  }};
  const action = {image: f.image, alt: 'Map', position: 'after', anchor: {tag: 'h2', text: 'Map location'}};
  const source = '<p>Keep before</p><h2>Map location</h2><p>Keep after</p>';
  assert.equal(insertJournalImage(source, action), '<p>Keep before</p><h2>Map location</h2><img src="assets/α image.png" alt="Map"><p>Keep after</p>');
  assert.throws(() => insertJournalImage(source, {...action, anchor: {tag: 'h2', text: 'Missing'}}), code('AnchorNotFound'));
  assert.throws(() => insertJournalImage(source + '<h2>Map location</h2>', action), code('AmbiguousAnchor'));
});

test('image load deadline is bounded and cannot mutate a page on timeout', async () => {
  const f = imageFixture(), context = await getJournalWriteContext({target: {kind: 'page', page_uuid: f.page.uuid}});
  const timers = {setTimeout, clearTimeout};
  globalThis.Image = class {set src(value) {}};
  globalThis.setTimeout = (callback, delay) => {assert.equal(delay, 5000); queueMicrotask(callback); return 1;};
  globalThis.clearTimeout = () => {};
  try {
    await assert.rejects(writeJournal(await request({operation: 'embed_image', page_uuid: f.page.uuid, expected_revision: context.revision, image: f.image, alt: ''})), code('ImageUnavailable'));
    assert.equal(f.updates.length, 0);
  } finally {Object.assign(globalThis, timers);}
});

test('image insertion retains source-size bounds without truncating the existing page', async () => {
  const f = imageFixture(); f.page.data.text.content = '<p>' + 'x'.repeat(999990) + '</p>';
  const context = await getJournalWriteContext({target: {kind: 'page', page_uuid: f.page.uuid}});
  await assert.rejects(writeJournal(await request({operation: 'embed_image', page_uuid: f.page.uuid, expected_revision: context.revision, image: f.image, alt: ''})), code('InvalidRequest'));
  assert.equal(f.updates.length, 0); assert.equal(f.page.data.text.content.length, 999997);
});
