import test from "node:test";
import assert from "node:assert/strict";
import { serializeForRpc, executeJavaScript } from "../../foundry-module/scripts/exploration.js";
import { handleRpcMessage } from "../../foundry-module/scripts/foundryBridge.js";

let enabled = true;
globalThis.game = { version: "13.test", world: { title: "Disposable" }, user: { isGM: true }, settings: {
  get(module, key) { return key === "developmentExecution" ? enabled : "browser-credential"; },
} };

test("async function body executes and RPC carries compilation/runtime errors", async () => {
  const result = await executeJavaScript({ code: "await Promise.resolve(); return {version: game.version, world: game.world.title};" });
  assert.equal(result.value.properties.world, "Disposable");
  assert.equal(result.foundryVersion, "13.test");
  for (const [code, type] of [["return (", "JavaScriptCompilationError"], ["throw new Error('boom')", "JavaScriptRuntimeError"]]) {
    const response = await handleRpcMessage({ id: "1", method: "executeJavaScript", params: { code } });
    assert.equal(response.error.type, type);
    assert.ok(response.error.stack);
  }
  enabled = false;
  await assert.rejects(executeJavaScript({ code: "return 1" }), error => error.rpcError.type === "UnauthorizedExecution");
  enabled = true;
  game.user.isGM = false;
  await assert.rejects(executeJavaScript({ code: "return 1" }), error => error.rpcError.type === "UnauthorizedExecution");
  game.user.isGM = true;
  await assert.rejects(executeJavaScript({ code: "x".repeat(32769) }), error => error.rpcError.type === "InvalidParameters");
  assert.ok((await handleRpcMessage({ id: "1", method: "toString" })).error);
});

test("snapshots preserve types and never invoke accessors or toJSON", () => {
  const object = { bigint: 10n, missing: undefined, fn() {}, map: new Map([["a", 1]]), set: new Set([2]), error: new Error("test") };
  object.self = object;
  Object.defineProperty(object, "getter", { enumerable: true, get() { throw new Error("getter ran"); } });
  object.toJSON = () => { throw new Error("toJSON ran"); };
  const result = serializeForRpc(object).properties;
  assert.equal(result.self.$type, "Circular");
  assert.equal(result.getter.$type, "Accessor");
  assert.equal(result.bigint.value, "10");
  assert.equal(result.missing.$type, "Undefined");
  assert.equal(result.map.$type, "Map");
  assert.equal(result.set.$type, "Set");
  assert.equal(result.fn.$type, "Function");
  assert.equal(result.error.properties.message, "test");
});

test("hostile objects and large output remain bounded", () => {
  const proxy = new Proxy({}, { ownKeys() { throw new Error("trap"); } });
  assert.equal(serializeForRpc(proxy).$type, "Unserializable");
  const wide = Array.from({ length: 500 }, () => Object.fromEntries(Array.from({ length: 100 }, (_, i) => [String(i), "\\\"😀".repeat(5000)])));
  assert.ok(Buffer.byteLength(JSON.stringify(serializeForRpc(wide))) < 65536);
  let deep = {};
  for (let i = 0; i < 100; i++) deep = { deep };
  assert.match(JSON.stringify(serializeForRpc(deep)), /depth limit/);
  const array = [];
  Object.defineProperty(array, "0", { get() { throw new Error("accessor"); } });
  assert.equal(serializeForRpc(array).values[0].$type, "Accessor");
});
