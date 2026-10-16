import test from "node:test";
import assert from "node:assert/strict";
import { bridgeUrl } from "../../foundry-module/scripts/connectionConfig.js";

test("complete endpoints support LAN, TLS, ports, and IPv6", () => {
  for (const url of ["ws://mcp-host.example:8000/ws/foundry", "wss://mcp-host.example/ws/foundry", "ws://[::1]:8000/ws/foundry"]) {
    assert.equal(bridgeUrl(url, "http:").href, url);
  }
});
test("invalid endpoints and HTTPS mixed content have actionable errors", () => {
  for (const value of [null, "", "broken", "/ws/foundry", "https://host/ws/foundry", "ws://host/", "ws://name:credential@host/ws/foundry", "ws://host/ws/foundry#fragment", "ws://host/ws/foundry?token=secret"]) {
    assert.throws(() => bridgeUrl(value, "http:"), /ws:\/\/|wss:\/\//);
  }
  assert.throws(() => bridgeUrl("ws://mcp-host.example/ws/foundry", "https:"), /HTTPS.*wss/);
  assert.equal(bridgeUrl("wss://mcp-host.example/ws/foundry", "https:").protocol, "wss:");
});
