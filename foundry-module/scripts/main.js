import { connectFoundryBridge } from "./foundryBridge.js";

Hooks.once("init", () => {
  const settings = {
    bridgeUrl: { name: "MCP WebSocket URL", type: String, default: "ws://localhost:8000/ws/foundry" },
    developmentExecution: { name: "Enable development JavaScript execution (GM only)", type: Boolean, default: false },
    browserToken: { name: "Local development browser credential", type: String, default: "", config: false },
  };
  for (const [key, options] of Object.entries(settings)) {
    game.settings.register("foundry-mcp", key, { scope: "client", config: true, ...options, onChange: () => window.location.reload() });
  }
});

Hooks.once("ready", () => {
  if (game.user.isGM) connectFoundryBridge();
});
