import test from "node:test";
import assert from "node:assert/strict";
import { webcrypto } from "node:crypto";
import { getJournalTree, getJournalContents, readJournalPage, searchJournals, searchableText } from "../../foundry-module/scripts/journals.js";
import { handleRpcMessage } from "../../foundry-module/scripts/foundryBridge.js";

if (!globalThis.crypto) Object.defineProperty(globalThis, "crypto", { value: webcrypto, configurable: true });
const collection = docs => ({ contents: docs, size: docs.length, get: id => docs.find(d => d.id === id) });
const text = value => ({ nodeType: 3, textContent: value });
const element = (tagName, ...childNodes) => ({ nodeType: 1, tagName, childNodes });
// Browser DOM behavior is verified live. These known trees exercise traversal
// without bundling a second HTML parser into the module or test dependencies.
const markup = '<h2><span>E1. East Room</span><span>Low 6</span></h2><p>Ri<strong>pnugget</strong> &amp; @UUID[JournalEntry.other]{Ally}</p><script>hidden</script><table><tr><td>one</td><td>two</td></tr></table>';
globalThis.DOMParser = class {
  parseFromString(html) {
    return { body: html === markup ? element("BODY",
      element("H2", element("SPAN", text("E1. East Room")), element("SPAN", text("Low 6"))),
      element("P", text("Ri"), element("STRONG", text("pnugget")), text(" & @UUID[JournalEntry.other]{Ally}")),
      element("SCRIPT", text("hidden")), element("TABLE", element("TR", element("TD", text("one")), element("TD", text("two")))))
      : element("BODY", text(html)) };
  }
};

function fixture() {
  const a = { id: "a", name: "A", type: "JournalEntry", folder: null, sorting: "a", sort: 0 };
  const b = { id: "b", name: "B", type: "JournalEntry", folder: a, sorting: "m", sort: 0 };
  const empty = { id: "empty", name: "Empty", type: "JournalEntry", folder: null, sorting: "a", sort: 0 };
  const entry = { id: "j", name: "Notes", uuid: "JournalEntry.j", folder: b, sort: 0,
    categories: collection([{ id: "c", name: "Clues", sort: 20 }]) };
  const page = (id, name, content, sort = 0, extra = {}) => ({ id, name, parent: entry,
    uuid: `JournalEntry.j.JournalEntryPage.${id}`, type: "text", sort,
    title: { level: 1, show: true }, text: { content, format: 1 }, toc: {}, ...extra });
  entry.pages = collection([
    page("late", "Late", "Ripnugget then Ally Ripnugget", 300),
    page("media", "Map", undefined, 200, { type: "image" }),
    page("early", "First clue", markup, 100, { category: "c", toc: {
      root: { text: "East Room", level: 2, order: 0, children: ["child"] },
      child: { text: "Clue", level: 3, order: 1, children: [] },
    } }),
  ]);
  const root = { id: "root", uuid: "JournalEntry.root", name: "Unfiled", folder: null, sort: 0, pages: collection([]), categories: collection([]) };
  globalThis.game = { version: "14.369", ready: true, user: { isGM: true }, folders: collection([b, empty, a]), journal: collection([entry, root]) };
  globalThis.foundry = { utils: { fromUuidSync(uuid, { relative }) {
    if (uuid === ".early") return { documentName: "JournalEntryPage", parent: relative.parent, uuid: entry.pages.get("early").uuid };
    if (uuid === "JournalEntry.root") return { documentName: "JournalEntry", id: "root" };
    return null;
  } } };
  return { a, b, empty, entry, root };
}

test("journal retrieval", async t => {
  await t.test("selective defaults omit outlines, excerpts and references, with bound continuations", async () => {
    fixture();
    const contents=await getJournalContents({journal_id:'j',limit:1,max_bytes:8000,select:{}});
    assert.equal(contents.contract_version,2);
    assert.equal(contents.pages.length,1);
    assert.ok(!Object.hasOwn(contents.pages[0],'heading_outline'));
    assert.ok(!Object.hasOwn(contents,'folder_path'));
    const categories=await getJournalContents({journal_id:'j',max_bytes:8000,select:{categories:true}});
    assert.equal(categories.groups.find(group=>group.category_id==='c').page_uuids[0],'JournalEntry.j.JournalEntryPage.early');
    assert.ok(contents.next_cursor);
    await assert.rejects(getJournalContents({journal_id:'j',limit:1,max_bytes:8000,select:{headings:true},cursor:contents.next_cursor}));
    const results=await searchJournals({query:'Ripnugget',limit:10,max_bytes:8000,select:{}});
    assert.ok(results.matches.length);
    assert.ok(results.matches.every(row=>!Object.hasOwn(row,'excerpts')));
    const selected=await searchJournals({query:'Ripnugget',limit:10,max_bytes:8000,select:{excerpts:true}});
    assert.ok(selected.matches.some(row=>row.excerpts.length));
    const page=await readJournalPage({page_uuid:'JournalEntry.j.JournalEntryPage.early',max_chars:20,max_bytes:8000,select:{}});
    assert.equal(page.content,markup.slice(0,20));
    assert.ok(!Object.hasOwn(page,'references'));
    const rest=await readJournalPage({page_uuid:page.page_uuid,max_chars:20,max_bytes:8000,select:{},cursor:page.next_cursor});
    assert.equal(rest.offset,20);
  });
  await t.test("nested navigation includes unfiled entries and marks empty vs collapsed folders", async () => {
    fixture();
    const tree = await getJournalTree();
    assert.equal(tree.tree_complete, true);
    assert.equal(tree.children[0].name, "A");
    assert.equal(tree.children[0].children[0].name, "B");
    assert.equal(tree.children[0].children[0].children[0].journal_id, "j");
    assert.equal(tree.children[1].child_count, 0);
    assert.equal(tree.children[2].journal_id, "root");
    const shallow = await getJournalTree({ max_depth: 0 });
    assert.equal(shallow.complete, true);
    assert.equal(shallow.tree_complete, false);
    assert.deepEqual(shallow.children[0].expand, { folder_id: "a" });
    const expanded = await getJournalTree(shallow.children[0].expand);
    assert.deepEqual(expanded.folder_path.map(f => f.name), ["A"]);
    assert.equal(expanded.children[0].children[0].name, "Notes");
  });

  await t.test("tree pagination never loses immediate children and detects stale scopes", async () => {
    const { a } = fixture();
    const first = await getJournalTree({ limit: 1 });
    const second = await getJournalTree({ limit: 1, cursor: first.next_cursor });
    const third = await getJournalTree({ limit: 1, cursor: second.next_cursor });
    assert.deepEqual([first, second, third].flatMap(r => r.children.map(n => n.name)), ["A", "Empty", "Unfiled"]);
    assert.equal(third.complete, true);
    await assert.rejects(getJournalTree({ folder_id: "a", cursor: first.next_cursor }), /different inputs/);
    a.name = "Renamed";
    await assert.rejects(getJournalTree({ cursor: first.next_cursor }), /changed/);
  });

  await t.test("contents preserve category ordering, heading ancestry, and unreadable media", async () => {
    fixture();
    const result = await getJournalContents({ journal_id: "j" });
    assert.deepEqual(result.pages.map(p => p.page_id), ["early", "media", "late"]);
    assert.equal(result.pages[0].category.name, "Clues");
    assert.equal(result.pages[0].heading_outline[1].parent_anchor, "root");
    assert.deepEqual(result.pages[0].heading_outline[1].ancestor_anchors, ["root"]);
    assert.equal(result.pages[1].readable, false);
    assert.equal(result.groups[0].page_uuids[0], result.pages[0].page_uuid);
    const empty = await getJournalContents({ journal_id: "root" });
    assert.equal(empty.complete, true);
    assert.equal(empty.total, 0);
  });

  await t.test("heading continuation covers a large outline without dropping sections", async () => {
    const { entry } = fixture();
    const p = entry.pages.get("early");
    p.toc = Object.fromEntries(Array.from({ length: 70 }, (_, i) => [`h${i}`, { text: `Heading ${i}`, level: 2, order: i, children: [] }]));
    const contents = await getJournalContents({ journal_id: "j" });
    assert.equal(contents.pages[0].headings_complete, false);
    let result; let cursor = null; const names = [];
    do {
      result = await getJournalContents({ ...contents.pages[0].headings_next_call, cursor });
      names.push(...result.heading_outline.map(h => h.name)); cursor = result.next_cursor;
    } while (cursor);
    assert.equal(names.length, 70);
    assert.equal(names.at(-1), "Heading 69");
  });

  await t.test("empty categories remain discoverable even when their metadata needs pagination", async () => {
    const { root } = fixture();
    root.categories = collection(Array.from({ length: 80 }, (_, i) => ({ id: `c${i}`, name: `Group ${i}`, sort: i })));
    const contents = await getJournalContents({ journal_id: "root" });
    assert.equal(contents.complete, true);
    assert.equal(contents.groups_complete, false);
    assert.equal(contents.groups.length, 20);
    let cursor = null; const ids = [];
    do {
      const r = await getJournalContents({ ...contents.categories_next_call, cursor });
      ids.push(...r.groups.map(c => c.category_id)); cursor = r.next_cursor;
    } while (cursor);
    assert.equal(new Set(ids).size, 80);
    await assert.rejects(getJournalContents({ journal_id: "root", categories_only: true, page_id: "early" }), /cannot be combined/);
  });

  await t.test("source chunks round-trip markup, whitespace, entities, notation, and Unicode", async () => {
    const { entry } = fixture();
    const p = entry.pages.get("early");
    p.text.content = '<p class="custom">\n😀 &amp; @UUID[JournalEntry.other]{Ally} <b> spaced </b></p>'.repeat(300);
    const source = p.text.content;
    let cursor = null; let reassembled = ""; let last;
    do {
      last = await readJournalPage({ page_uuid: p.uuid, max_chars: 77, cursor });
      assert.equal(last.offset, reassembled.length);
      assert.ok(!/[\uD800-\uDBFF]$/.test(last.content));
      reassembled += last.content; cursor = last.next_cursor;
    } while (cursor);
    assert.equal(reassembled, source);
    assert.equal(last.total_chars, source.length);
    assert.equal(last.complete, true);
  });

  await t.test("byte limits, Markdown selection, empty source, and changed content", async () => {
    const { entry } = fixture(); const p = entry.pages.get("early");
    p.text = { content: '"\\\n😀'.repeat(12000), markdown: "# Original\n\n*text*", format: 2 };
    const first = await readJournalPage({ page_uuid: p.uuid, max_chars: 20000 });
    assert.ok(Buffer.byteLength(JSON.stringify(first)) <= 48000);
    assert.equal(first.available_sources[1], "markdown");
    const markdown = await readJournalPage({ page_uuid: p.uuid, source: "markdown" });
    assert.equal(markdown.content, p.text.markdown);
    await assert.rejects(readJournalPage({ page_uuid: p.uuid, source: "markdown", cursor: first.next_cursor }), /different inputs/);
    p.text.content += "changed";
    await assert.rejects(readJournalPage({ page_uuid: p.uuid, cursor: first.next_cursor }), /changed/);
    p.text = { content: "", format: 1 };
    assert.equal((await readJournalPage({ page_uuid: p.uuid })).content, "");
    await assert.rejects(readJournalPage({ page_uuid: p.uuid, source: "markdown" }), /not stored/);
  });

  await t.test("literal search uses labels and derived text, supports subtree scope and pagination", async () => {
    fixture();
    assert.equal(searchableText(markup), "E1. East Room Low 6 Ripnugget & Ally one two");
    const first = await searchJournals({ query: "RIPNUGGET", folder_id: "a", limit: 1 });
    assert.equal(first.total, 2);
    assert.equal(first.matches[0].page_id, "early");
    const second = await searchJournals({ query: "RIPNUGGET", folder_id: "a", limit: 1, cursor: first.next_cursor });
    assert.equal(second.complete, true);
    assert.equal(second.matches[0].text_match_count, 2);
    assert.equal(second.matches[0].excerpts_derived, true);
    assert.equal((await searchJournals({ query: "other" })).total, 0); // UUID target is not narrative text.
    assert.equal((await searchJournals({ query: "hidden" })).total, 0); // script content is not journal prose.
    assert.equal((await searchJournals({ query: "[" })).total, 0); // literal punctuation, never a regex.
    assert.equal((await searchJournals({ query: "Ripnugget", journal_id: "root" })).searched_text_pages, 0);
    await assert.rejects(searchJournals({ query: "x", folder_id: "a", journal_id: "j" }), /not both/);
  });

  await t.test("reference metadata resolves relative pages without changing source or fetching other documents", async () => {
    const { entry } = fixture(); const p = entry.pages.get("early");
    p.text.content = '@UUID[.early#child]{Clue} @UUID[JournalEntry.root]{Notes} @UUID[JournalEntry.deleted]{Missing} @UUID[Compendium.pack.Item.id]{Item}';
    const result = await readJournalPage({ page_uuid: p.uuid });
    assert.equal(result.content, p.text.content);
    assert.equal(result.references[0].page_uuid, p.uuid);
    assert.equal(result.references[0].anchor, "child");
    assert.equal(result.references[1].journal_id, "root");
    assert.equal(result.references[2].resolution, "unresolved");
    assert.equal(result.references[3].resolution, "outside_world_journals");
    p.text.content = '@UUID[JournalEntry.root]{Notes} '.repeat(30);
    const bounded = await readJournalPage({ page_uuid: p.uuid });
    assert.equal(bounded.references.length, 20);
    assert.equal(bounded.references_complete, false);
    assert.equal(bounded.content, p.text.content);
  });

  await t.test("Markdown-only pages remain searchable and source absence is explicit", async () => {
    const { entry } = fixture(); const p = entry.pages.get("early");
    p.text = { markdown: "# UniqueMarkdown @UUID[JournalEntry.hidden]{Visible}", format: 2 };
    const html = await readJournalPage({ page_uuid: p.uuid });
    assert.equal(html.source_present, false);
    assert.equal(html.content, "");
    assert.deepEqual(html.available_sources, ["markdown"]);
    assert.equal((await searchJournals({ query: "uniquemarkdown" })).total, 1);
    assert.equal((await searchJournals({ query: "hidden" })).total, 0);
  });

  await t.test("large directory pages, duplicate names, and HTTP without Web Crypto", async () => {
    const { root } = fixture();
    game.journal.contents = Array.from({ length: 150 }, (_, i) => ({ ...root, id: `j${i}`, name: "Same name", uuid: `JournalEntry.j${i}` }));
    const original = Object.getOwnPropertyDescriptor(globalThis, "crypto");
    Object.defineProperty(globalThis, "crypto", { configurable: true, value: {} });
    try {
      let cursor = null; const ids = [];
      do {
        const result = await getJournalTree({ limit: 10, cursor });
        assert.ok(Buffer.byteLength(JSON.stringify(result)) <= 48000);
        ids.push(...result.children.filter(n => n.kind === "journal").map(n => n.journal_id));
        cursor = result.next_cursor;
      } while (cursor);
      assert.equal(new Set(ids).size, 150);
    } finally { Object.defineProperty(globalThis, "crypto", original); }
  });

  await t.test("distinct errors, readiness, cycles, and normal RPC dispatch", async () => {
    const { a, b } = fixture();
    await assert.rejects(readJournalPage({ page_uuid: "j" }), /full page_uuid/);
    await assert.rejects(readJournalPage({ page_uuid: "Compendium.pack.JournalEntry.x" }), /not compendiums/);
    await assert.rejects(readJournalPage({ page_uuid: "JournalEntry.j.JournalEntryPage.media" }), /Only text/);
    await assert.rejects(readJournalPage({ page_uuid: "JournalEntry.j.JournalEntryPage.deleted" }), /Page not found/);
    await assert.rejects(getJournalTree({ max_depth: -1 }), /integer/);
    const rpc = await handleRpcMessage({ id: "test", method: "getJournalContents", params: { journal_id: "j" } });
    assert.equal(rpc.result.pages[0].name, "First clue");
    game.user.isGM = false;
    assert.equal((await handleRpcMessage({ id: "test", method: "getJournalTree" })).error.type, "GMRequired");
    game.user.isGM = true; game.ready = false;
    await assert.rejects(getJournalTree(), /finish loading/);
    game.ready = true; a.folder = b;
    await assert.rejects(getJournalTree(), /cycle/);
  });
});
