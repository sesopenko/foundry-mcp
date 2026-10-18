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
    assert.equal(typeof response.error.message, "string");
    assert.ok(response.error.message.length > 0 && response.error.message.length <= 2000);
    // Native stacks are accessors on newer V8 versions and are deliberately skipped.
    if (response.error.stack !== undefined) {
      assert.equal(typeof response.error.stack, "string");
      assert.ok(response.error.stack.length <= 2000);
    }
    if (type === "JavaScriptRuntimeError") assert.equal(response.error.message, "boom");
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

test("RPC preserves and bounds explicit error data fields on every engine", async () => {
  const response = await handleRpcMessage({ id: "bounded", method: "executeJavaScript", params: {
    code: 'throw {message: "m".repeat(3000), stack: "s".repeat(3000)};',
  } });
  // Use a wire round trip so omitted fields and exact transported values are tested.
  assert.deepEqual(JSON.parse(JSON.stringify(response)), {
    id: "bounded",
    error: { type: "JavaScriptRuntimeError", message: "m".repeat(2000), stack: "s".repeat(2000) },
  });
});

test("RPC error handling skips hostile message/stack getters and absent stacks", async t => {
  let getterReads = 0;
  globalThis.__explorationThrownError = Object.defineProperties({}, {
    message: { get() { getterReads++; throw new Error("message getter ran"); } },
    stack: { get() { getterReads++; throw new Error("stack getter ran"); } },
  });
  t.after(() => { delete globalThis.__explorationThrownError; });
  const accessor = await handleRpcMessage({ id: "accessor", method: "executeJavaScript", params: {
    code: 'throw globalThis.__explorationThrownError;',
  } });
  assert.equal(getterReads, 0);
  assert.deepEqual(JSON.parse(JSON.stringify(accessor)), {
    id: "accessor", error: { type: "JavaScriptRuntimeError", message: "JavaScriptRuntimeError" },
  });
  const missing = await handleRpcMessage({ id: "missing-stack", method: "executeJavaScript", params: {
    code: 'throw "plain failure";',
  } });
  assert.deepEqual(JSON.parse(JSON.stringify(missing)), {
    id: "missing-stack", error: { type: "JavaScriptRuntimeError", message: "plain failure" },
  });
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
