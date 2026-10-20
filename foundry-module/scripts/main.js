import { registerPDFManager } from "./pdfManager.js";
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
    bridgeUrl: { name: "MCP browser WebSocket URL", hint: "Full ws:// or wss:// URL ending in /ws/foundry, reachable from this GM browser. Saved with this world; changes reconnect automatically.", type: String, default: "ws://localhost:8000/ws/foundry" },
    productionAuthentication: { name: "Authenticate production bridge", hint: "Enable when the MCP server requires production authentication. Remote connections require WSS.", type: Boolean, default: false },
    bridgeCredential: { name: "Production browser bridge credential", hint: "Shared world setting, not a GM-only secret store. Must match the server bridge token; never enter the MCP password here.", type: String, default: "" },
    pdfUploadToken: { name: "PDF upload password", hint: "Must match the server PDF upload token. Shared world setting, readable by players; anyone who obtains it can authorize PDF uploads and library management. Never enter the MCP password here.", type: String, default: "" },
    developmentExecution: { name: "Enable local development JavaScript execution (GM only)", hint: "Leave disabled for gaming. Requires a loopback endpoint, separate server credentials, and a existing development test world.", type: Boolean, default: false },
    browserToken: { name: "Local development browser credential", type: String, default: "", config: false },
  };
  for (const [key, options] of Object.entries(settings)) {
    game.settings.register("foundry-mcp", key, { scope: "world", config: true, ...options, onChange: connectionChanged });
  }
});

Hooks.once("ready", () => {
  ready = true;
  if (game.user.isGM) {
    registerPDFManager();
    connectFoundryBridge();
  }
});
