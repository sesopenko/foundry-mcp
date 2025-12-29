import { connectFoundryBridge } from "./foundryBridge.js";

console.log("Hello World! This code runs immediately when the file is loaded.");

Hooks.on("init", function () {
  console.log(
    "This code runs once the Foundry VTT software begins its initialization workflow."
  );
});

Hooks.on("ready", function () {
  if (game.user.isGM) {
    // Establish a websocket connection to http://localhost:8000/ws/foundry
    // and listen for websocket commands via the foundryBridge module.
    console.log("GM client ready; initializing Foundry MCP WebSocket bridge.");
    connectFoundryBridge();
  }
});
