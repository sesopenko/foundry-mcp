import test from "node:test";
import assert from "node:assert/strict";

test("Foundry initializes bridge only when a GM is ready", async () => {
  const hooks = new Map();
  globalThis.Hooks = { once(name, fn) { hooks.set(name, fn); } };
  const sockets = [];
  globalThis.WebSocket = class {
    static OPEN = 1;
    constructor(url) { this.url = url; sockets.push(this); }
    addEventListener() {}
  };
  await import("../../foundry-module/scripts/main.js");
  assert.ok(hooks.has("init"));
  assert.ok(hooks.has("ready"));
  const registered = new Map();
  globalThis.game = { user: { isGM: false }, settings: {
    register(module, key, value) { registered.set(key, value); },
    get(module, key) { return registered.get(key)?.default; },
  } };
  hooks.get("init")();
  assert.equal(registered.get("developmentExecution").default, false);
  assert.equal(registered.get("browserToken").config, false);
  hooks.get("ready")();
  assert.equal(sockets.length, 0);
  globalThis.game.user.isGM = true;
  hooks.get("ready")();
  assert.equal(sockets.length, 1);
});
