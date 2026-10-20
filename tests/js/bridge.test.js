import test from "node:test";
import assert from "node:assert/strict";
import { connectFoundryBridge, disconnectFoundryBridge, reconnectFoundryBridge, getConnectionStatus } from "../../foundry-module/scripts/foundryBridge.js";

class FakeWebSocket {
  static OPEN = 1;
  static CONNECTING = 0;
  static sockets = [];
  constructor(url) {
    this.url = url;
    this.readyState = 0;
    this.listeners = new Map();
    this.sent = [];
    FakeWebSocket.sockets.push(this);
  }
  addEventListener(event, fn) { this.listeners.set(event, fn); }
  async emit(event, data = {}) { await this.listeners.get(event)?.(data); }
  send(value) { this.sent.push(JSON.parse(value)); }
  close() { this.readyState = 3; return this.emit("close", { code: 1000 }); }
  async open() { this.readyState = FakeWebSocket.OPEN; await this.emit("open"); }
  async request(message) { await this.emit("message", { data: JSON.stringify(message) }); return this.sent.at(-1); }
}

globalThis.WebSocket = FakeWebSocket;
const options = { bridgeUrl: "ws://localhost:8000/ws/foundry", developmentExecution: false, browserToken: "" };
const settings = { get(module, key) { return options[key]; } };
globalThis.game = { settings };

test("bridge behavior", async t => {
  const originalSetTimeout = globalThis.setTimeout;
  const originalClearTimeout = globalThis.clearTimeout;
  const timers = new Map();
  let nextId = 0;
  globalThis.setTimeout = (fn, delay) => { const id = ++nextId; timers.set(id, { fn, delay }); return id; };
  globalThis.clearTimeout = id => timers.delete(id);
  t.after(() => {
    disconnectFoundryBridge();
    globalThis.setTimeout = originalSetTimeout;
    globalThis.clearTimeout = originalClearTimeout;
  });

  await t.test("production authentication gates RPC until acknowledgment and stops on rejection", async () => {
    options.productionAuthentication = true;
    options.bridgeCredential = "t".repeat(32);
    options.bridgeUrl = "wss://bridge.example/ws/foundry";
    let socket = connectFoundryBridge();
    await socket.open();
    assert.equal(getConnectionStatus().state, "Authenticating");
    assert.deepEqual(socket.sent, [{ type: "auth", token: options.bridgeCredential }]);
    await socket.request({ id: "early", method: "getPlayerNameList" });
    assert.equal(socket.sent.length, 1);
    await socket.request({ type: "auth", status: "ok" });
    assert.equal(getConnectionStatus().state, "Connected");
    assert.equal(timers.size, 0);
    await socket.request({ id: "ready", method: "getPlayerNameList" });
    assert.equal(socket.sent.at(-1).id, "ready");
    await socket.emit("close", { code: 1008 });
    assert.equal(getConnectionStatus().state, "Misconfigured");
    assert.equal(timers.size, 0);
    socket = reconnectFoundryBridge();
    await socket.open();
    const timeout = [...timers.values()].find(t => t.delay === 5000);
    timers.clear(); timeout.fn();
    assert.equal(timers.size, 0);
    disconnectFoundryBridge();
    options.bridgeUrl = "ws://remote.example/ws/foundry";
    assert.equal(connectFoundryBridge(), null);
    options.bridgeCredential = "short";
    options.bridgeUrl = "wss://bridge.example/ws/foundry";
    assert.equal(connectFoundryBridge(), null);
    options.productionAuthentication = false;
    options.bridgeCredential = "";
    options.bridgeUrl = "ws://localhost:8000/ws/foundry";
    timers.clear();
  });
  await t.test("connects and reuses an open socket", async () => {
    options.browserToken = "leftover-local-credential";
    options.bridgeCredential = "stored-production-secret";
    const socket = connectFoundryBridge();
    assert.equal(socket.url, "ws://localhost:8000/ws/foundry");
    assert.equal(connectFoundryBridge(), socket);
    await socket.open();
    assert.deepEqual(socket.sent, []); // Never send a development secret in normal LAN mode.
    options.browserToken = "";
    options.bridgeCredential = "";
    assert.equal(connectFoundryBridge(), socket);
  });
  await t.test("player names include only active users with string names", async () => {
    globalThis.game = { settings, users: new Map([
      ["1", { active: true, name: "Alice" }], ["2", { active: false, name: "Bob" }],
      ["3", { active: true, name: 10 }], ["4", { active: true, name: "GM" }],
    ]) };
    const socket = connectFoundryBridge();
    assert.deepEqual(await socket.request({ id: "names", method: "getPlayerNameList", params: {} }), { id: "names", result: ["Alice", "GM"] });
    globalThis.game = { settings };
    assert.deepEqual((await socket.request({ id: "empty", method: "getPlayerNameList" })).result, []);
  });
  await t.test("invalid requests and browser errors produce RPC errors", async () => {
    const socket = connectFoundryBridge();
    const count = socket.sent.length;
    await socket.emit("message", { data: "bad JSON" });
    await socket.request({ method: "getPlayerNameList" });
    assert.equal(socket.sent.length, count);
    for (const message of [{ id: "a" }, { id: "b", method: "unknown" }]) {
      const response = await socket.request(message);
      assert.equal(response.id, message.id);
      assert.equal(typeof response.error.message, "string");
    }
    globalThis.game = { settings, users: { values() { throw new Error("users unavailable"); } } };
    assert.equal((await socket.request({ id: "failure", method: "getPlayerNameList" })).error.message, "users unavailable");
  });
  await t.test("reconnect backs off and resets after success", async () => {
    await connectFoundryBridge().close();
    assert.equal([...timers.values()][0].delay, 1000);
    let timer = [...timers.values()][0]; timers.clear(); timer.fn();
    const reconnect = FakeWebSocket.sockets.at(-1);
    await reconnect.close();
    assert.equal([...timers.values()][0].delay, 2000);
    timer = [...timers.values()][0]; timers.clear(); timer.fn();
    await FakeWebSocket.sockets.at(-1).open();
    await FakeWebSocket.sockets.at(-1).close();
    assert.equal([...timers.values()][0].delay, 1000);
  });
  await t.test("manual disconnect clears reconnect timer", () => {
    disconnectFoundryBridge();
    assert.equal(timers.size, 0);
  });
  await t.test("invalid configuration and constructor failures do not throw or schedule retries", () => {
    options.bridgeUrl = "invalid";
    assert.equal(connectFoundryBridge(), null);
    assert.equal(getConnectionStatus().state, "Misconfigured");
    options.bridgeUrl = "ws://localhost:8000/ws/foundry";
    globalThis.WebSocket = class { constructor() { throw new Error("blocked"); } };
    assert.equal(connectFoundryBridge(), null);
    globalThis.WebSocket = FakeWebSocket;
    assert.equal(timers.size, 0);
  });
  await t.test("settings reconnect cancels timers and stale close events", async () => {
    const old = connectFoundryBridge();
    await old.open();
    options.bridgeUrl = "ws://localhost:8123/ws/foundry";
    const replacement = reconnectFoundryBridge();
    assert.equal(replacement.url, options.bridgeUrl);
    await old.emit("close", { code: 1000 });
    assert.equal(timers.size, 0);
    await replacement.open();
    assert.equal(getConnectionStatus().state, "Connected");
    await replacement.close();
    assert.equal(timers.size, 1);
    options.bridgeUrl = "broken";
    assert.equal(reconnectFoundryBridge(), null);
    assert.equal(timers.size, 0);
    options.bridgeUrl = "ws://localhost:8000/ws/foundry";
  });
  await t.test("development connection rejects remote URLs and sends credential only on open", async () => {
    options.developmentExecution = true;
    options.browserToken = "local-test-credential";
    options.bridgeUrl = "ws://example.com/ws/foundry";
    assert.equal(connectFoundryBridge(), null);
    options.bridgeUrl = "ws://localhost:8000/ws/foundry";
    const socket = connectFoundryBridge();
    assert.equal(socket.sent.length, 0);
    await socket.open();
    assert.deepEqual(socket.sent, [{ token: options.browserToken }]);
    assert.ok(!socket.url.includes(options.browserToken));
    disconnectFoundryBridge();
  });
  await t.test("stale sockets cannot close or dispatch through the new connection", async () => {
    const old = connectFoundryBridge();
    await old.open();
    disconnectFoundryBridge();
    const active = connectFoundryBridge();
    await active.open();
    await old.emit("close", { code: 1000 });
    await old.request({ id: "stale", method: "getPlayerNameList" });
    assert.equal(old.sent.length, 1); // Authentication only.
    assert.equal(connectFoundryBridge(), active);
    assert.equal(timers.size, 0);
    disconnectFoundryBridge();
  });

});
