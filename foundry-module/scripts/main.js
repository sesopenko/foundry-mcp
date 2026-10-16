import { connectFoundryBridge, reconnectFoundryBridge } from "./foundryBridge.js";

let ready = false;
let settingsTimer;
function connectionChanged() {
  if (!ready || !game.user?.isGM) return;
  clearTimeout(settingsTimer);
  settingsTimer = setTimeout(() => reconnectFoundryBridge(), 0);
}

Hooks.once("init", () => {
  const settings = {
    bridgeUrl: { name: "MCP browser WebSocket URL", hint: "Full ws:// or wss:// URL ending in /ws/foundry, reachable from this GM browser. Saved per browser; changes reconnect automatically.", type: String, default: "ws://localhost:8000/ws/foundry" },
    developmentExecution: { name: "Enable local development JavaScript execution (GM only)", hint: "Leave disabled for gaming. Requires a loopback endpoint, separate server credentials, and a disposable development world.", type: Boolean, default: false },
    browserToken: { name: "Local development browser credential", type: String, default: "", config: false },
  };
  for (const [key, options] of Object.entries(settings)) {
    game.settings.register("foundry-mcp", key, { scope: "client", config: true, ...options, onChange: connectionChanged });
  }
});

Hooks.once("ready", () => {
  ready = true;
  if (game.user.isGM) connectFoundryBridge();
});
