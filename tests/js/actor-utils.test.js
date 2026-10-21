import test from "node:test";
import assert from "node:assert/strict";
import { fail, validateParams, integer, selector, selectSections, digest, paginate, textFragments } from "../../foundry-module/scripts/actorReadUtils.js";

const base = () => ({ revision: "r1", runtime: { core_version: "14.369" }, sections: [{ name: "source", status: "complete", reasons: [] }, { name: "effective", status: "unsupported", reasons: ["gate"] }] });
const rows = count => Array.from({ length: count }, (_, i) => ({ key: `r${i}`, section: "source", raw: [{ path: `/r/${i}`, value: "x" }] }));
const code = expected => error => error.rpcError?.code === expected;

test("strict pure validation and structured errors", () => {
  assert.throws(() => fail("Example", "message", "recover"), error => error.rpcError.type === "Example" && error.rpcError.recovery === "recover");
  for (const value of [null, [], new Date(), "x"]) assert.throws(() => validateParams(value, []), code("InvalidRequest"));
  assert.throws(() => validateParams({ unknown: 1 }, []), code("InvalidRequest"));
  assert.deepEqual(validateParams({ limit: 1 }, ["limit"]), { limit: 1 });
  for (const value of [null, true, "1", 0, 101, 1.5]) assert.throws(() => integer(value, 50, 1, 100, "limit"), code("InvalidRequest"));
  assert.equal(integer(undefined, 50, 1, 100, "limit"), 50);
  for (const value of [null, "", " ", "x".repeat(513)]) assert.throws(() => selector(value, "uuid"), code("InvalidRequest"));
  assert.equal(selector("Actor.example", "uuid"), "Actor.example");
  for (const value of [[], ["source", "source"], ["unknown"], null]) assert.throws(() => selectSections(value, ["source"], ["source"]), code("InvalidRequest"));
  assert.deepEqual(selectSections(undefined, ["source"], ["source"]), ["source"]);
});

test("exact Unicode and escaped source reassembly within byte bounds", () => {
  for (const source of ["", '<p title="\\">😀漢字\n&copy;</p>'.repeat(1000), "😀".repeat(4000), "\ud800".repeat(2000)]) {
    const fragments = textFragments(source);
    assert.equal(fragments.map(fragment => fragment.value).join(""), source);
    let position = 0;
    for (const fragment of fragments) {
      assert.equal(fragment.text.start, position);
      assert.equal(fragment.text.end - position, fragment.value.length);
      assert.ok(fragment.value.length <= 6000);
      assert.ok(Buffer.byteLength(JSON.stringify(fragment.value)) <= 1000);
      position = fragment.text.end;
      if (position < source.length) assert.ok(!(source.charCodeAt(position - 1) >= 0xd800 && source.charCodeAt(position - 1) <= 0xdbff && source.charCodeAt(position) >= 0xdc00 && source.charCodeAt(position) <= 0xdfff));
    }
    assert.equal(fragments.at(-1).text.complete, true);
  }
});

test("pagination independently enforces count and UTF8 byte bounds", async () => {
  const data = rows(7); let cursor; const seen = [];
  do {
    const result = await paginate(data, base(), { limit: 2, cursor }, { tool: "read" });
    assert.ok(result.records.length <= 2);
    assert.equal(result.pagination.returned, result.records.length);
    assert.equal(result.sections[0].status, result.pagination.complete ? "complete" : "partial");
    assert.equal(result.sections[1].status, "unsupported");
    seen.push(...result.records.map(record => record.key)); cursor = result.pagination.next_cursor;
  } while (cursor);
  assert.deepEqual(seen, data.map(record => record.key));
  const big = rows(10).map(record => ({ ...record, value: "漢".repeat(700) }));
  const result = await paginate(big, base(), { limit: 100, max_bytes: 8000 }, { tool: "read" });
  assert.ok(result.records.length > 0 && result.records.length < 10);
  assert.ok(Buffer.byteLength(JSON.stringify(result)) <= 8000);
  await assert.rejects(paginate([{ key: "large", raw: [{ path: "/large", value: "x".repeat(50000) }] }], base(), {}, {}), code("ResponseTooLarge"));
  assert.equal((await paginate([], base(), {}, {})).pagination.complete, true);
});

test("cursor rejects changed scope, bounds, revision and invalid position", async () => {
  const data = rows(4); const params = { limit: 1 }; const scope = { tool: "read", sections: ["source"] };
  const first = await paginate(data, base(), params, scope); const cursor = first.pagination.next_cursor;
  assert.equal((await paginate(data, base(), { ...params, cursor }, scope)).records[0].key, "r1");
  await assert.rejects(paginate(data, base(), { limit: 2, cursor }, scope), code("CursorMismatch"));
  await assert.rejects(paginate(data, base(), { ...params, cursor }, { tool: "other" }), code("CursorMismatch"));
  await assert.rejects(paginate(data, { ...base(), revision: "r2" }, { ...params, cursor }, scope), code("ContentChanged"));
  for (const token of ["bad!", "", "😀", "x".repeat(4097), btoa("null")]) await assert.rejects(paginate(data, base(), { ...params, cursor: token }, scope), code("InvalidCursor"));
  const decoded = JSON.parse(atob(cursor)); decoded.position = 5;
  await assert.rejects(paginate(data, base(), { ...params, cursor: btoa(JSON.stringify(decoded)) }, scope), code("InvalidCursor"));
});

test("HTTP change marker fallback is deterministic and content sensitive", async () => {
  const original = Object.getOwnPropertyDescriptor(globalThis, "crypto");
  Object.defineProperty(globalThis, "crypto", { configurable: true, value: {} });
  try {
    const value = await digest({ text: "😀" });
    assert.match(value, /^http-/);
    assert.equal(await digest({ text: "😀" }), value);
    assert.notEqual(await digest({ text: "other" }), value);
  } finally {
    if (original) Object.defineProperty(globalThis, "crypto", original);
    else delete globalThis.crypto;
  }
});
