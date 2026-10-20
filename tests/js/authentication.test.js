import test from "node:test";
import assert from "node:assert/strict";
import { connectFoundryBridge, disconnectFoundryBridge, reconnectFoundryBridge, getConnectionStatus } from "../../foundry-module/scripts/foundryBridge.js";

function harness(t) {
  const originals = { WebSocket: globalThis.WebSocket, game: globalThis.game, ui: globalThis.ui,
    setTimeout: globalThis.setTimeout, clearTimeout: globalThis.clearTimeout };
  const timers = new Map();
  let nextTimer = 0;
  globalThis.setTimeout = (fn, delay) => { const id = ++nextTimer; timers.set(id, { fn, delay }); return id; };
  globalThis.clearTimeout = id => timers.delete(id);
  class Socket {
    static OPEN = 1;
    static CONNECTING = 0;
    static sockets = [];
    constructor(url) { this.url = url; this.readyState = 0; this.sent = []; this.listeners = new Map(); Socket.sockets.push(this); }
    addEventListener(event, handler) { this.listeners.set(event, handler); }
    async emit(event, data = {}) { await this.listeners.get(event)?.(data); }
    async open() { this.readyState = 1; await this.emit("open"); }
    async message(value) { await this.emit("message", { data: JSON.stringify(value) }); }
    send(raw) { this.sent.push(JSON.parse(raw)); }
    // Browser close events arrive asynchronously. Tests deliberately deliver them later.
    close(code = 1000) { this.readyState = 3; this.closeCode = code; }
  }
  globalThis.WebSocket = Socket;
  const settings = { bridgeUrl: "wss://auth.example/ws/foundry", productionAuthentication: true,
    bridgeCredential: "browser-only-secret-sentinel-0123456789", developmentExecution: false,
    browserToken: "development-only-secret-sentinel-0123456789" };
  globalThis.game = { settings: { get(namespace, key) { return settings[key]; } }, users: new Map() };
  t.after(() => { disconnectFoundryBridge(); Object.assign(globalThis, originals); });
  const timer = delay => {
    const entry = [...timers].find(([, value]) => value.delay === delay);
    assert.ok(entry, `Expected ${delay}ms timer`);
    return entry;
  };
  const fire = delay => { const [id, value] = timer(delay); timers.delete(id); value.fn(); };
  return { settings, Socket, timers, timer, fire };
}

test("stale authentication acknowledgments, queued timeouts and close events cannot affect a replacement", async t => {
  const h = harness(t);
  const old = connectFoundryBridge();
  await old.open();
  const queuedTimeout = h.timer(5000)[1].fn;
  const active = reconnectFoundryBridge();
  await active.open();
  assert.equal(h.timers.size, 1, "Replace must cancel the old authentication deadline immediately");
  await old.message({ type: "auth", status: "ok" });
  assert.equal(getConnectionStatus().state, "Authenticating");
  queuedTimeout();
  await old.emit("close", { code: 1008 });
  assert.equal(getConnectionStatus().state, "Authenticating");
  assert.equal(h.timers.size, 1);
  await active.message({ type: "auth", status: "ok" });
  assert.equal(getConnectionStatus().state, "Connected");
  await old.message({ id: "stale", method: "getPlayerNameList" });
  assert.equal(old.sent.length, 1);
  assert.equal(connectFoundryBridge(), active);
  assert.equal(h.timers.size, 0);
});

test("production network failures back off until acknowledgment; rejection stops retries until settings change", async t => {
  const h = harness(t);
  let socket = connectFoundryBridge();
  await socket.open();
  await socket.emit("close", { code: 1006 });
  assert.equal(h.timers.size, 1);
  h.fire(1000);
  socket = h.Socket.sockets.at(-1);
  await socket.open();
  await socket.emit("close", { code: 1006 });
  h.fire(2000); // Opening the transport alone must not reset backoff.
  socket = h.Socket.sockets.at(-1);
  await socket.open();
  await socket.message({ type: "auth", status: "ok" });
  await socket.emit("close", { code: 1006 });
  h.fire(1000); // Successful authentication resets backoff.
  socket = h.Socket.sockets.at(-1);
  await socket.open();
  await socket.emit("close", { code: 1008 });
  assert.equal(getConnectionStatus().state, "Misconfigured");
  assert.equal(h.timers.size, 0);
  h.settings.bridgeCredential = "rotated-browser-secret-sentinel-0123456789";
  const replacement = reconnectFoundryBridge();
  await replacement.open();
  assert.deepEqual(replacement.sent, [{ type: "auth", token: h.settings.bridgeCredential }]);
  await replacement.message({ type: "auth", status: "ok" });
  assert.equal(getConnectionStatus().state, "Connected");
});

test("authentication timeout and manual disconnect cancel retries and ignore late acknowledgment", async t => {
  const h = harness(t);
  const socket = connectFoundryBridge();
  await socket.open();
  await socket.message({ type: "auth", status: "failed" });
  assert.equal(getConnectionStatus().state, "Authenticating");
  h.fire(5000);
  assert.equal(socket.closeCode, 1008);
  assert.equal(getConnectionStatus().state, "Misconfigured");
  await socket.message({ type: "auth", status: "ok" });
  assert.equal(getConnectionStatus().state, "Misconfigured", "Late acknowledgment cannot resurrect a timed-out socket");
  await socket.emit("close", { code: 1008 });
  assert.equal(h.timers.size, 0);
  const replacement = reconnectFoundryBridge();
  await replacement.open();
  disconnectFoundryBridge();
  assert.equal(h.timers.size, 0, "Manual disconnect must cancel its authentication deadline immediately");
  await replacement.message({ type: "auth", status: "ok" });
  assert.equal(getConnectionStatus().state, "Disconnected");
});

test("credentials stay out of URLs, logs and notifications on success, rejection and invalid configuration", async t => {
  const h = harness(t);
  const diagnostics = [];
  const methods = ["info", "warn", "error", "debug", "log"];
  const original = Object.fromEntries(methods.map(name => [name, console[name]]));
  for (const name of methods) console[name] = (...args) => diagnostics.push(args.map(String).join(" "));
  globalThis.ui = { notifications: Object.fromEntries(["info", "warn", "error"].map(name => [name, text => diagnostics.push(text)])) };
  t.after(() => Object.assign(console, original));
  const socket = connectFoundryBridge();
  assert.equal(socket.url, h.settings.bridgeUrl);
  assert.deepEqual(socket.sent, []);
  await socket.open();
  assert.deepEqual(socket.sent, [{ type: "auth", token: h.settings.bridgeCredential }]);
  await socket.message({ type: "auth", status: "ok" });
  await socket.emit("error", { message: h.settings.bridgeCredential });
  await socket.emit("close", { code: 1008, reason: h.settings.bridgeCredential });
  h.settings.bridgeUrl = `wss://user:${h.settings.bridgeCredential}@auth.example/ws/foundry`;
  assert.equal(reconnectFoundryBridge(), null);
  assert.ok(diagnostics.length > 0);
  for (const value of [h.settings.bridgeCredential, h.settings.browserToken]) {
    assert.ok(!diagnostics.join("\n").includes(value));
    assert.ok(!socket.url.includes(value));
  }
});

test("short, Unicode and matching production/development credentials are accepted", async t => {
  const h = harness(t);
  for (const credential of ["x", "é", "pass word$"]) {
    h.settings.bridgeCredential = credential;
    h.settings.browserToken = credential;
    const socket = reconnectFoundryBridge();
    await socket.open();
    assert.deepEqual(socket.sent, [{ type: "auth", token: credential }]);
    await socket.message({ type: "auth", status: "ok" });
    assert.equal(getConnectionStatus().state, "Connected");
  }
});
