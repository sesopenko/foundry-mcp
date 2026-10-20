import test from "node:test";
import assert from "node:assert/strict";
import { BUILD_INFO } from "../../foundry-module/scripts/buildInfo.js";
import { getModuleBuildInfo, validBuildInfo, reportServerBuild } from "../../foundry-module/scripts/versionStatus.js";
import { handleRpcMessage, connectFoundryBridge, disconnectFoundryBridge } from "../../foundry-module/scripts/foundryBridge.js";
const release = version => ({ version, release_tag: `v${version}`, revision: "a".repeat(40), build_kind: "release" });

test("module RPC returns loaded JavaScript identity and cannot mutate its constant", async () => {
  const response = await handleRpcMessage({ id: "version", method: "getModuleBuildInfo", params: {} });
  assert.deepEqual(response, { id: "version", result: BUILD_INFO });
  response.result.version = "99.0.0";
  assert.deepEqual(getModuleBuildInfo(), BUILD_INFO);
});

test("known releases warn once per identity pair, name both versions and identify the older component", t => {
  const previous = globalThis.ui, warnings = [], info = [];
  globalThis.ui = { notifications: { warn: (...args) => warnings.push(args), info: value => info.push(value) } };
  t.after(() => { globalThis.ui = previous; });
  assert.equal(reportServerBuild(release("2.0.0"), release("2.0.0")), "match");
  assert.equal(warnings.length, 0);
  assert.equal(reportServerBuild(release("2.0.0"), release("1.9.0")), "mismatch");
  assert.match(warnings[0][0], /server v2.0.0; module v1.9.0/);
  assert.match(warnings[0][0], /older Foundry module/);
  assert.deepEqual(warnings[0][1], { permanent: true });
  reportServerBuild(release("2.0.0"), release("1.9.0"));
  assert.equal(warnings.length, 1);
  reportServerBuild(release("2.0.0"), release("3.0.0"));
  assert.match(warnings[1][0], /older MCP server\/container/);
  assert.equal(info.length, 0);
});

test("unreleased, source and invalid identities never claim a tagged match", t => {
  const previous = globalThis.ui, warnings = [], info = [];
  globalThis.ui = { notifications: { warn: value => warnings.push(value), info: value => info.push(value) } };
  t.after(() => { globalThis.ui = previous; });
  for (const build_kind of ["source", "unreleased"]) {
    const source = { ...release("4.0.0"), release_tag: null, build_kind };
    assert.equal(reportServerBuild(release("4.0.0"), source), "unverified");
    assert.match(info.at(-1), new RegExp(`module 4.0.0 \\(${build_kind}\\)`));
  }
  assert.equal(reportServerBuild({ version: "broken" }, release("4.0.0")), "unverified");
  assert.match(info.at(-1), /server unknown \(unknown\)/);
  assert.equal(warnings.length, 0);
  for (const invalid of [null, [], {}, { ...release("4.0.0"), release_tag: "vwrong" }, { ...release("4.0.0"), revision: "short" }]) {
    assert.equal(validBuildInfo(invalid), false);
  }
});

test("server identity is handled in every mode, ignored on stale/unauthenticated sockets, and legacy servers still work", async t => {
  const previous = { game: globalThis.game, WebSocket: globalThis.WebSocket, ui: globalThis.ui };
  const options = { bridgeUrl: "ws://localhost:8000/ws/foundry", productionAuthentication: false, developmentExecution: false, browserToken: "dev", bridgeCredential: "browser" };
  const info = [];
  globalThis.game = { settings: { get(module, key) { return options[key]; } } };
  globalThis.ui = { notifications: { info: text => info.push(text), warn() {}, error() {} } };
  class Socket {
    static OPEN = 1; static CONNECTING = 0;
    constructor() { this.readyState = 0; this.handlers = {}; this.sent = []; }
    addEventListener(name, fn) { this.handlers[name] = fn; }
    send(raw) { this.sent.push(JSON.parse(raw)); }
    async open() { this.readyState = 1; await this.handlers.open(); }
    async message(value) { await this.handlers.message({ data: JSON.stringify(value) }); }
    close() { this.readyState = 3; }
  }
  globalThis.WebSocket = Socket;
  t.after(() => { disconnectFoundryBridge(); Object.assign(globalThis, previous); });
  const old = connectFoundryBridge(); await old.open();
  // No serverInfo (a legacy server) does not block normal RPC dispatch.
  await old.message({ id: "legacy", method: "getModuleBuildInfo" });
  assert.equal(old.sent.at(-1).id, "legacy");
  await old.message({ type: "serverInfo", server_build: release("5.0.0") });
  assert.ok(info.some(text => text.includes("server 5.0.0")));
  disconnectFoundryBridge();
  options.productionAuthentication = true;
  const socket = connectFoundryBridge(); await socket.open();
  const before = info.length;
  await old.message({ type: "serverInfo", server_build: release("6.0.0") });
  await socket.message({ type: "serverInfo", server_build: release("6.0.0") });
  assert.equal(info.length, before);
  await socket.message({ type: "auth", status: "ok", server_build: release("6.0.0") });
  assert.ok(info.some(text => text.includes("server 6.0.0")));
  await socket.message({ id: "after-auth", method: "getModuleBuildInfo" });
  assert.equal(socket.sent.at(-1).id, "after-auth");
  disconnectFoundryBridge();
  options.productionAuthentication = false; options.developmentExecution = true;
  const dev = connectFoundryBridge(); await dev.open();
  assert.deepEqual(dev.sent[0], { token: "dev" });
  await dev.message({ type: "serverInfo", server_build: release("7.0.0") });
  assert.ok(info.some(text => text.includes("server 7.0.0")));
});
