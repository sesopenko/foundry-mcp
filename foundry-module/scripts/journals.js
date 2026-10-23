/**
 * Read-only world-journal RPCs. Foundry dependencies are documented in
 * docs/journal-tools.md (v13/v14). Never use sheet internals or game.journal.tree.
 * Source HTML/Markdown is sliced, never parsed and reserialized for reading.
 */
import { actorTarget, itemTarget, permitted, ready as actorReady } from "./actorDocuments.js";
import { validateParams } from "./actorReadUtils.js";
const MAX_BYTES = 48000; // Leave room for RPC framing below the 64 KiB transport cap.
const encoder = new TextEncoder();

function fail(type, message) {
  const error = new Error(message);
  error.rpcError = { type, message };
  throw error;
}

function ready() {
  if (!globalThis.game?.ready || !game.journal || !game.folders) {
    fail("FoundryNotReady", "Wait for the Foundry world to finish loading and retry.");
  }
  if (!game.user?.isGM) fail("GMRequired", "Journal preparation tools require a connected GM browser.");
}

function integer(value, fallback, min, max, name) {
  value ??= fallback;
  if (!Number.isInteger(value) || value < min || value > max) {
    fail("InvalidParameters", `${name} must be an integer from ${min} to ${max}.`);
  }
  return value;
}

function selector(value, name, optional = false) {
  if (value == null && optional) return null;
  if (typeof value !== "string" || !value.trim() || value.length > 512) {
    fail("InvalidParameters", `${name} must be a nonempty identifier from a journal tool result.`);
  }
  return value;
}

function folder(id) {
  if (id == null) return null;
  selector(id, "folder_id");
  const doc = game.folders.get(id);
  if (!doc || doc.type !== "JournalEntry") {
    fail("FolderNotFound", "Journal folder not found. Refresh get_journal_tree and use a returned folder_id.");
  }
  return doc;
}

function journal(id) {
  selector(id, "journal_id");
  const doc = game.journal.get(id);
  if (!doc) fail("JournalNotFound", "Journal not found. Refresh get_journal_tree or search_journals.");
  return doc;
}

function pageFromUuid(uuid) {
  selector(uuid, "page_uuid");
  if (uuid.startsWith("Compendium.")) fail("UnsupportedDocument", "Only world journals are supported, not compendiums.");
  const match = /^JournalEntry\.([^.]+)\.JournalEntryPage\.([^.]+)$/.exec(uuid);
  if (!match) fail("InvalidParameters", "Use a full page_uuid from get_journal_contents or search_journals, without a heading anchor.");
  const entry = journal(match[1]);
  const page = entry.pages.get(match[2]);
  if (!page) fail("PageNotFound", "Page not found. Refresh get_journal_contents for this entry.");
  return { entry, page };
}

function scalarSlice(value, start, end) {
  if (start > 0 && /[\uDC00-\uDFFF]/.test(value[start]) && /[\uD800-\uDBFF]/.test(value[start - 1])) start--;
  if (end < value.length && /[\uD800-\uDBFF]/.test(value[end - 1]) && /[\uDC00-\uDFFF]/.test(value[end])) end--;
  return value.slice(start, end);
}

function name(doc) {
  const value = String(doc.name ?? "");
  // Metadata only: source content is never clipped here.
  return { name: scalarSlice(value, 0, 256), name_truncated: value.length > 256 };
}

function path(doc) {
  const result = [];
  const seen = new Set();
  while (doc) {
    if (seen.has(doc.id)) fail("InvalidHierarchy", "Folder containment contains a cycle; repair folders in Foundry.");
    seen.add(doc.id);
    result.unshift({ folder_id: doc.id, ...name(doc) });
    doc = doc.folder;
  }
  return result;
}

function compare(mode = "m") {
  return (a, b) => (mode === "a" ? String(a.name).localeCompare(String(b.name)) : (a.sort ?? 0) - (b.sort ?? 0))
    || String(a.id).localeCompare(String(b.id));
}

function categories(entry) {
  // Both versioned schemas document categories; older builds may omit it.
  return [...(entry.categories?.contents ?? [])].sort(compare());
}

function orderedPages(entry) {
  const pages = [...entry.pages.contents];
  const groups = categories(entry);
  const ids = new Set(groups.map(c => c.id));
  return groups.flatMap(c => pages.filter(p => p.category === c.id).sort(compare()))
    .concat(pages.filter(p => !ids.has(p.category)).sort(compare()));
}

async function revision(value) {
  const data = encoder.encode(JSON.stringify(value));
  if (globalThis.crypto?.subtle) {
    const digest = await crypto.subtle.digest("SHA-256", data);
    return Array.from(new Uint8Array(digest), n => n.toString(16).padStart(2, "0")).join("");
  }
  // Web Crypto requires a secure context, but ordinary HTTP Foundry worlds
  // can still use preparation tools. This is a change marker, not an auth token.
  let a = 2166136261; let b = 5381;
  for (const byte of data) { a = Math.imul(a ^ byte, 16777619) >>> 0; b = (Math.imul(b, 33) ^ byte) >>> 0; }
  return `http-${data.length}-${a.toString(16)}-${b.toString(16)}`;
}

function cursor(tool, scope, rev, offset) {
  const bytes = encoder.encode(JSON.stringify({ tool, scope, revision: rev, offset }));
  return btoa(Array.from(bytes, n => String.fromCharCode(n)).join(""));
}

function position(token, tool, scope, rev, total) {
  if (token == null) return 0;
  if (typeof token !== "string" || token.length > 4096) fail("InvalidCursor", "Use the returned next_cursor unchanged, with the same inputs.");
  let data;
  try {
    data = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(Uint8Array.from(atob(token), c => c.charCodeAt(0))));
  } catch {
    fail("InvalidCursor", "Use the returned next_cursor unchanged, with the same inputs.");
  }
  if (data.tool !== tool || JSON.stringify(data.scope) !== JSON.stringify(scope)
      || !Number.isInteger(data.offset) || data.offset < 0 || data.offset > total) {
    fail("InvalidCursor", "Continuation belongs to different inputs. Restart without cursor or reuse the original inputs.");
  }
  if (data.revision !== rev) fail("ContentChanged", "Journal data changed. Restart this tool without cursor.");
  return data.offset;
}

function bytes(value) { return encoder.encode(JSON.stringify(value)).length; }
function bounded(value) {
  if (bytes(value) > MAX_BYTES) fail("ResponseTooLarge", "Journal metadata exceeds the response budget. Select a smaller folder, entry, or page.");
  return value;
}

function paginate(items, start, limit, base, field, tool, scope, rev,
  { offsetBase = 0, total = items.length, decorate = () => {} } = {}) {
  const result = { ...base, revision: rev, [field]: [], total, complete: false, next_cursor: null };
  let end = start;
  for (; end < items.length && end - start < limit; end++) {
    result[field].push(items[end]);
    result.next_cursor = cursor(tool, scope, rev, offsetBase + end + 1);
    decorate(result);
    if (bytes(result) > MAX_BYTES) {
      result[field].pop();
      break;
    }
  }
  if (end === start && start < items.length) fail("ResponseTooLarge", "One metadata record is too large. Use a narrower journal selector.");
  result.complete = offsetBase + end === total;
  result.next_cursor = result.complete ? null : cursor(tool, scope, rev, offsetBase + end);
  decorate(result);
  return bounded(result);
}

function entryNode(entry) {
  const text = entry.pages.contents.filter(p => p.type === "text").length;
  return { kind: "journal", journal_id: entry.id, journal_uuid: entry.uuid, ...name(entry),
    folder_id: entry.folder?.id ?? null, sort: entry.sort ?? 0,
    text_page_count: text, non_text_page_count: entry.pages.size - text };
}

/** Nested directory view assembled exclusively from document relationships. */
export async function getJournalTree(params = {}) {
  ready();
  const selected = folder(params.folder_id);
  const depth = integer(params.max_depth, 3, 0, 8, "max_depth");
  const limit = integer(params.limit, 50, 1, 100, "limit");
  const folders = game.folders.contents.filter(f => f.type === "JournalEntry");
  const folderSet = new Set(folders);
  const entries = game.journal.contents;
  // Validate ancestry even for branches beyond the requested depth.
  folders.forEach(f => path(f));
  const rev = await revision([folders.map(f => [f.id, f.name, f.folder?.id, f.sort, f.sorting]),
    entries.map(e => [e.id, e.name, e.folder?.id, e.sort, e.pages.contents.map(p => [p.id, p.type])])]);
  const scope = { folder_id: selected?.id ?? null, max_depth: depth };
  const children = parent => {
    const id = parent?.id ?? null;
    const mode = parent?.sorting ?? "a";
    return [...folders.filter(f => (f.folder?.id ?? null) === id).sort(compare(mode)),
      ...entries.filter(e => (e.folder?.id ?? null) === id).sort(compare(mode))];
  };
  const direct = children(selected);
  const start = position(params.cursor, "tree", scope, rev, direct.length);
  // A global node budget bounds expansion. Each collapsed folder supplies its
  // own selector, so no descendant is silently lost through root pagination.
  let budget = 100;
  const node = (doc, remaining) => {
    if (!folderSet.has(doc)) return entryNode(doc);
    const list = children(doc);
    const out = { kind: "folder", folder_id: doc.id, ...name(doc), parent_folder_id: doc.folder?.id ?? null,
      sorting: doc.sorting, sort: doc.sort ?? 0, child_count: list.length, children: [],
      complete: list.length === 0, expand: null };
    if (list.length && (remaining <= 0 || list.length > budget)) {
      out.complete = false;
      out.expand = { folder_id: doc.id };
      return out;
    }
    budget -= list.length;
    out.children = list.map(child => node(child, remaining - 1));
    out.complete = out.children.every(c => c.kind !== "folder" || c.complete);
    if (!out.complete) out.expand = { folder_id: doc.id };
    return out;
  };
  const nodes = direct.slice(start, start + limit).map(doc => node(doc, depth));
  const base = { foundry_version: game.version, folder_path: path(selected), folder_id: selected?.id ?? null,
    view: "core_document_hierarchy", tree_complete: false };
  // Collapse large expanded branches before paginating immediate children.
  for (const item of nodes) {
    if (bytes(item) > MAX_BYTES / 2 && item.kind === "folder") {
      item.children = []; item.complete = false; item.expand = { folder_id: item.folder_id };
    }
  }
  const result = paginate(nodes, 0, nodes.length, base, "children", "tree", scope, rev,
    { offsetBase: start, total: direct.length });
  result.tree_complete = result.complete && result.children.every(c => c.kind !== "folder" || c.complete);
  return bounded(result);
}

function headings(page) {
  if (page.type !== "text") return [];
  const toc = page.toc ?? {};
  const parent = new Map();
  for (const [anchor, heading] of Object.entries(toc)) for (const child of heading.children ?? []) parent.set(child, anchor);
  return Object.entries(toc).sort((a, b) => a[1].order - b[1].order).map(([anchor, h]) => {
    const ancestors = []; const seen = new Set([anchor]); let id = parent.get(anchor);
    while (id && !seen.has(id)) { seen.add(id); ancestors.unshift(id); id = parent.get(id); }
    return { kind: "heading", anchor, ...name({ name: h.text }), level: h.level,
      parent_anchor: parent.get(anchor) ?? null, ancestor_anchors: ancestors };
  });
}

function pageNode(page, groups) {
  const outline = headings(page);
  const group = groups.find(c => c.id === page.category);
  return { kind: "page", page_id: page.id, page_uuid: page.uuid, ...name(page), type: page.type,
    readable: page.type === "text", sort: page.sort, title_level: page.title.level, title_show: page.title.show,
    category: group ? { category_id: group.id, ...name(group) } : null,
    heading_outline: outline.slice(0, 20), heading_count: outline.length, headings_complete: outline.length <= 20,
    headings_next_call: outline.length > 20 ? { journal_id: page.parent.id, page_id: page.id } : null };
}

export async function getJournalContents(params = {}) {
  ready();
  const entry = journal(params.journal_id);
  const limit = integer(params.limit, 20, 1, 50, "limit");
  const groups = categories(entry);
  const categoriesOnly = params.categories_only ?? false;
  if (typeof categoriesOnly !== "boolean" || (categoriesOnly && params.page_id != null)) {
    fail("InvalidParameters", "categories_only must be boolean and cannot be combined with page_id.");
  }
  const rev = await revision([entry.name, entry.folder?.id, groups.map(c => [c.id, c.name, c.sort]),
    entry.pages.contents.map(p => [p.id, p.name, p.type, p.sort, p.title, p.category, p.text?.content])]);
  const scope = { journal_id: entry.id, page_id: params.page_id ?? null, categories_only: categoriesOnly };
  const base = { foundry_version: game.version, journal_id: entry.id, journal_uuid: entry.uuid,
    ...name(entry), folder_path: path(entry.folder) };
  if (categoriesOnly) {
    const items = groups.map(c => ({ kind: "category", category_id: c.id, ...name(c), sort: c.sort,
      page_count: entry.pages.contents.filter(p => p.category === c.id).length }));
    const start = position(params.cursor, "contents", scope, rev, items.length);
    return paginate(items, start, limit, { ...base, mode: "categories" }, "groups", "contents", scope, rev);
  }
  if (params.page_id != null) {
    selector(params.page_id, "page_id");
    const page = entry.pages.get(params.page_id);
    if (!page) fail("PageNotFound", "Refresh get_journal_contents and use a returned page_id.");
    const outline = headings(page);
    const start = position(params.cursor, "contents", scope, rev, outline.length);
    return paginate(outline, start, limit, { ...base, page_id: page.id, page_uuid: page.uuid, mode: "headings" },
      "heading_outline", "contents", scope, rev);
  }
  const pages = orderedPages(entry).map(p => pageNode(p, groups));
  const start = position(params.cursor, "contents", scope, rev, pages.length);
  const decorate = result => {
    const present = new Set(result.pages.map(p => p.category?.category_id ?? null));
    const empty = groups.filter(c => !entry.pages.contents.some(p => p.category === c.id));
    const preview = new Set(empty.slice(0, 20).map(c => c.id));
    result.groups = groups.filter(c => present.has(c.id) || preview.has(c.id))
      .map(c => ({ kind: "category", category_id: c.id, ...name(c), sort: c.sort,
        page_uuids: result.pages.filter(p => p.category?.category_id === c.id).map(p => p.page_uuid) }));
    result.category_count = groups.length;
    result.groups_complete = result.groups.length === groups.length;
    result.categories_next_call = result.groups_complete ? null : { journal_id: entry.id, categories_only: true };
  };
  return paginate(pages, start, limit, { ...base, mode: "pages" }, "pages", "contents", scope, rev, { decorate });
}

/** Derived search text only. Never used for source reads or source positions. */
function normalizeSearchText(text) {
  return text.replace(/@UUID\[[^\]]+\]\{([^}]+)\}/g, "$1")
    .replace(/@UUID\[[^\]]+\]/g, " ").replace(/\s+/g, " ").trim();
}

export function searchableText(html) {
  const doc = new DOMParser().parseFromString(html ?? "", "text/html");
  const block = new Set(["P", "DIV", "SECTION", "ARTICLE", "H1", "H2", "H3", "H4", "H5", "H6", "LI", "TR", "TD", "TH", "BLOCKQUOTE", "BR"]);
  function visit(node) {
    if (node.nodeType === 3) return node.textContent;
    if (node.nodeType !== 1) return "";
    if (["SCRIPT", "STYLE", "TEMPLATE"].includes(node.tagName)) return "";
    const children = Array.from(node.childNodes);
    let text = children.map(visit).join("");
    // Split heading spans often contain a title and encounter rating.
    if (/^H[1-6]$/.test(node.tagName)) {
      text = children.map((child, index) => {
        const adjacentSpans = index > 0 && child.tagName === "SPAN" && children[index - 1].tagName === "SPAN";
        return (adjacentSpans ? " " : "") + visit(child);
      }).join("");
    }
    return block.has(node.tagName) ? ` ${text} ` : text;
  }
  return normalizeSearchText(visit(doc.body));
}

export async function searchJournals(params = {}) {
  ready();
  const query = selector(params.query, "query").replace(/\s+/g, " ").trim().toLowerCase();
  if (params.folder_id != null && params.journal_id != null) fail("InvalidParameters", "Choose folder_id or journal_id, not both.");
  const selectedFolder = folder(params.folder_id);
  const selectedEntry = params.journal_id == null ? null : journal(params.journal_id);
  const limit = integer(params.limit, 20, 1, 50, "limit");
  const scope = { query, folder_id: selectedFolder?.id ?? null, journal_id: selectedEntry?.id ?? null };
  const entries = game.journal.contents.filter(e => (!selectedEntry || e.id === selectedEntry.id)
    && (!selectedFolder || path(e.folder).some(f => f.folder_id === selectedFolder.id)))
    .sort(compare("a"));
  const sources = entries.flatMap(e => orderedPages(e).filter(p => p.type === "text").map(p => ({ e, p })));
  const rev = await revision(sources.map(({ e, p }) => [e.id, e.name, e.folder?.id, p.id, p.name, p.sort, p.text]));
  const matches = [];
  for (const { e, p } of sources) {
    const text = typeof p.text.content === "string" ? searchableText(p.text.content)
      : normalizeSearchText(p.text.markdown ?? "");
    const lower = text.toLowerCase();
    const offsets = []; let at = 0;
    while ((at = lower.indexOf(query, at)) >= 0) { offsets.push(at); at += query.length; }
    const titleMatch = p.name.replace(/\s+/g, " ").toLowerCase().includes(query);
    if (!titleMatch && !offsets.length) continue;
    matches.push({ journal_id: e.id, journal_name: name(e).name, journal_name_truncated: name(e).name_truncated,
      page_id: p.id, page_uuid: p.uuid, page_name: name(p).name, page_name_truncated: name(p).name_truncated,
      folder_path: path(e.folder), matched_fields: [titleMatch ? "page_name" : null, offsets.length ? "text" : null].filter(Boolean),
      text_match_count: offsets.length, excerpts_derived: true,
      excerpts: offsets.slice(0, 3).map(n => scalarSlice(text, Math.max(0, n - 100), n + query.length + 200)),
      excerpts_complete: offsets.length <= 3 });
  }
  const start = position(params.cursor, "search", scope, rev, matches.length);
  return paginate(matches, start, limit, { foundry_version: game.version, scope, searched_text_pages: sources.length },
    "matches", "search", scope, rev);
}

function references(content, sourcePage, source) {
  const result = []; let count = 0;
  for (const match of content.matchAll(/@UUID\[([^\]]+)\](?:\{([^}]+)\})?/g)) {
    count++;
    if (result.length >= 20) continue;
    const [uuid, ...parts] = match[1].split("#");
    const ref = { target: scalarSlice(match[1], 0, 512), target_truncated: match[1].length > 512,
      label: scalarSlice(match[2] ?? "", 0, 256), label_truncated: (match[2]?.length ?? 0) > 256,
      anchor: scalarSlice(parts.join("#"), 0, 512) || null, anchor_truncated: parts.join("#").length > 512,
      journal_id: null, page_uuid: null,
      resolution: "outside_world_journals" };
    ref.resolve_next_call = !ref.target_truncated && /^(Actor\.|Item\.|Compendium\.|Scene\.|\.)/.test(uuid)
      ? { tool: "resolve_journal_reference", arguments: { page_uuid: sourcePage.uuid, target: match[1], source } } : null;
    if (uuid.startsWith("JournalEntry.") || uuid.startsWith(".")) {
      ref.resolution = "unresolved";
      try {
        const doc = foundry.utils.fromUuidSync(uuid, { relative: sourcePage, strict: false });
        if (doc?.documentName === "JournalEntry" && !doc.inCompendium) {
          ref.journal_id = doc.id; ref.resolution = "resolved";
        } else if (doc?.documentName === "JournalEntryPage" && !doc.inCompendium) {
          ref.journal_id = doc.parent.id; ref.page_uuid = doc.uuid; ref.resolution = "resolved";
        }
      } catch { /* Broken references remain explicit; source is never rewritten. */ }
    }
    result.push(ref);
  }
  return { references: result, references_complete: count <= 20,
    references_scope: "complete UUID notation within this source fragment" };
}

/** Check the current world text-page source and authorization, never a cached
 * fragment. Public JournalEntryPage.text/parent and Document.testUserPermission:
 * https://foundryvtt.com/api/v14/classes/foundry.documents.JournalEntryPage.html
 */
function referenceOrigin(pageUuid, source, target) {
  ready();
  const { entry, page } = pageFromUuid(pageUuid);
  if (!permitted(entry) || !permitted(page)) fail("PermissionDenied", "The originating journal or page is not readable; refresh journal navigation with an authorized GM.");
  if (page.type !== "text") fail("UnsupportedPageType", "Only world text pages can supply references.");
  const content = source === "html" ? page.text.content : page.text.markdown;
  if (typeof content !== "string") fail("SourceUnavailable", "The selected source is not stored; reread the page and use an available source.");
  let present = false;
  for (const match of content.matchAll(/@UUID\[([^\]]+)\]/g)) {
    if (match[1] === target) { present = true; break; }
  }
  if (!present) {
    fail("ReferenceChanged", "The exact reference is absent from this source; reread the page and reuse its current target.");
  }
  return page;
}

/** Resolve exactly one authored journal reference without importing or reading
 * target source. Public core14 fromUuid(uuid,{relative:Document}):
 * https://foundryvtt.com/api/v14/functions/foundry.utils.fromUuid.html
 * PF2e-specific Actor/Item branch delegates supported type/source/instance
 * identity to actorDocuments (tested core14.369/PF2e8.6.1); other systems are
 * unsupported for these readers. Actor.token supplies synthetic context:
 * https://foundryvtt.com/api/v14/classes/foundry.documents.Actor.html#token
 * No preparation state, private APIs, name matching or recursive hydration.
 */
export async function resolveJournalReference(params = {}) {
  validateParams(params, ["page_uuid", "target", "source"]);
  selector(params.page_uuid, "page_uuid");
  selector(params.target, "target");
  const source = params.source ?? "html";
  if (!["html", "markdown"].includes(source)) fail("InvalidParameters", "source must be html or markdown.");
  const page = referenceOrigin(params.page_uuid, source, params.target);
  const [uuid, ...anchors] = params.target.split("#");
  const result = status => bounded({ foundry_version: game.version, page_uuid: page.uuid,
    source, target: params.target, anchor: anchors.join("#") || null, status, identity: null, next_call: null });
  const recheck = () => {
    if (referenceOrigin(params.page_uuid, source, params.target) !== page) {
      fail("ReferenceChanged", "The originating page changed; reread its source before resolving references.");
    }
  };
  if (!/^(Actor\.|Item\.|Compendium\.|Scene\.|\.)/.test(uuid)) return result("outside_scope");
  let document;
  try { document = await foundry.utils.fromUuid(uuid, { relative: page }); }
  catch { recheck(); return result("unverified"); }
  recheck();
  if (!document) return result("missing");
  const owner = document.parent?.documentName === "Actor" ? document.parent : null;
  const pack = document.compendium ?? owner?.compendium ?? null;
  if (!permitted(document) || (owner && !permitted(owner)) || (pack && !permitted(pack))) return result("denied");
  if (!["Actor", "Item", "Token"].includes(document.documentName)) return result("outside_scope");
  let selected; let nextCall;
  try {
    // PF2e-specific reader admission checks supported runtime and document types.
    actorReady();
    if (document.documentName === "Token") {
      selected = await actorTarget({ token_uuid: document.uuid });
      nextCall = { tool: "read_actor", arguments: { token_uuid: document.uuid } };
    } else {
      const actor = document.documentName === "Actor" ? document : owner;
      let tokenUuid = null;
      if (document.uuid?.startsWith("Scene.")) {
        tokenUuid = actor?.token?.uuid;
        if (!tokenUuid) { recheck(); return result("unverified"); }
        const instance = await actorTarget({ token_uuid: tokenUuid });
        if (instance.document.uuid !== actor.uuid) { recheck(); return result("unverified"); }
      }
      const arguments_ = document.documentName === "Actor"
        ? (tokenUuid ? { token_uuid: tokenUuid } : { actor_uuid: document.uuid })
        : { item_uuid: document.uuid, ...(tokenUuid ? { token_uuid: tokenUuid } : {}) };
      selected = document.documentName === "Actor" ? await actorTarget(arguments_) : await itemTarget(arguments_);
      nextCall = { tool: document.documentName === "Actor" ? "read_actor" : "read_item", arguments: arguments_ };
      if (selected.document.uuid !== document.uuid) { recheck(); return result("unverified"); }
    }
  } catch (error) {
    recheck();
    const code = error?.rpcError?.type;
    return result(code === "PermissionDenied" ? "denied" : code === "DocumentNotFound" || code === "ActorUnavailable" ? "missing"
      : ["UnsupportedSystem", "UnsupportedVersion", "UnsupportedType", "InvalidRequest"].includes(code) ? "unsupported" : "unverified");
  }
  recheck();
  // Recheck related records after all asynchronous reads before disclosing identity.
  const currentPack = selected.document.compendium ?? selected.actor?.compendium ?? null;
  if (!permitted(selected.document) || (selected.actor && !permitted(selected.actor))
      || (currentPack && !permitted(currentPack)) || (selected.token && (!permitted(selected.token) || !permitted(selected.token.parent)))) return result("denied");
  return bounded({ ...result("resolved"), identity: selected.identity, next_call: nextCall });
}

export async function readJournalPage(params = {}) {
  ready();
  const { entry, page } = pageFromUuid(params.page_uuid);
  if (page.type !== "text") fail("UnsupportedPageType", `Page type '${page.type}' is not readable. Only text pages are supported; use get_journal_contents to select one.`);
  const source = params.source ?? "html";
  if (!["html", "markdown"].includes(source)) fail("InvalidParameters", "source must be html or markdown.");
  const limit = integer(params.max_chars, 12000, 1, 20000, "max_chars");
  const available = [...(typeof page.text.content === "string" ? ["html"] : []),
    ...(typeof page.text.markdown === "string" ? ["markdown"] : [])];
  if (source === "markdown" && !available.includes(source)) fail("SourceUnavailable", "Original Markdown is not stored for this page. Read source=html instead.");
  const content = (source === "html" ? page.text.content : page.text.markdown) ?? "";
  const rev = await revision([page.uuid, page.text]);
  const scope = { page_uuid: page.uuid, source };
  const start = position(params.cursor, "read", scope, rev, content.length);
  if (start > 0 && /[\uDC00-\uDFFF]/.test(content[start]) && /[\uD800-\uDBFF]/.test(content[start - 1])) {
    fail("InvalidCursor", "Continuation splits a Unicode character. Restart without cursor.");
  }
  let end = Math.min(content.length, start + limit);
  // Avoid splitting UTF-16 surrogate pairs, even if max_chars is one.
  if (end < content.length && /[\uD800-\uDBFF]/.test(content[end - 1]) && /[\uDC00-\uDFFF]/.test(content[end])) end--;
  if (end === start && end < content.length) end = Math.min(content.length, start + 2);
  const make = () => ({ foundry_version: game.version, revision: rev, journal_id: entry.id,
    journal_name: name(entry).name, journal_name_truncated: name(entry).name_truncated,
    page_id: page.id, page_uuid: page.uuid, page_name: name(page).name, page_name_truncated: name(page).name_truncated,
    folder_path: path(entry.folder), source, stored_format: page.text.format, available_sources: available,
    content: content.slice(start, end), source_present: typeof (source === "html" ? page.text.content : page.text.markdown) === "string",
    offset: start, end_offset: end, total_chars: content.length, offset_units: "UTF-16 code units",
    fragment: start > 0 || end < content.length, complete: end === content.length,
    ...references(content.slice(start, end), page, source),
    next_cursor: end === content.length ? null : cursor("read", scope, rev, end) });
  let result = make();
  while (bytes(result) > MAX_BYTES && end > start) {
    end = start + Math.floor((end - start) / 2);
    if (end < content.length && /[\uD800-\uDBFF]/.test(content[end - 1]) && /[\uDC00-\uDFFF]/.test(content[end])) end--;
    result = make();
  }
  if (end === start && start < content.length) fail("ResponseTooLarge", "Page metadata exceeds the response budget.");
  return bounded(result);
}
