import { executeJavaScript } from "./exploration.js";
import { getJournalTree, getJournalContents, searchJournals, readJournalPage } from "./journals.js";
/**
 * ES module responsible for handling WebSocket communication with the
 * Python FoundryConnectionManager and dispatching RPC-style requests.
 *
 * Supports the player-name tool and the separately authorized development console.
 */



// Reconnection configuration
const RECONNECT_BASE_DELAY_MS = 1000; // 1 second
const RECONNECT_MAX_DELAY_MS = 30000; // 30 seconds
const RECONNECT_BACKOFF_FACTOR = 2;

let currentSocket = null;
let reconnectAttempts = 0;
let reconnectTimeoutId = null;
let manuallyClosed = false;

/**
 * Map of method names to handler functions.
 * Each handler receives a single `params` object and may return a value
 * or a Promise resolving to a value.
 */
const rpcHandlers = {
  executeJavaScript,
  getJournalTree,
  getJournalContents,
  searchJournals,
  readJournalPage,
  /**
   * Return the current list of active player names.
   *
   * Players are represented by User documents in game.users.
   * game.users is a Collection keyed by user id; each value is a User
   * with a `name` property.
   *
   * Only users with `user.active === true` are included.
   *
   * @param {object} params
   * @returns {string[]}
   */
  async getPlayerNameList(params) {
    console.log("[foundryBridge] getPlayerNameList called with params:", params);

    if (!game || !game.users) {
      console.warn("[foundryBridge] game or game.users is not available");
      return [];
    }

    // game.users is a Collection; iterate its values and extract user.name
    // Only include users that are active.
    const names = [];
    for (const user of game.users.values()) {
      if (
        user &&
        user.active === true &&
        typeof user.name === "string"
      ) {
        names.push(user.name);
      }
    }

    console.log("[foundryBridge] getPlayerNameList returning active names:", names);
    return names;
  },
};

/**
 * Handle a single incoming RPC request message and return the response object.
 *
 * @param {object} message - Parsed JSON message from the WebSocket.
 * @returns {Promise<object>} - Response object to send back over WebSocket.
 */
export async function handleRpcMessage(message) {
  if (!message || typeof message !== "object") return null;
  const { id, method, params } = message;

  if (!id) {
    console.warn("[foundryBridge] Received message without id");
    return null;
  }

  if (!method || typeof method !== "string") {
    console.warn("[foundryBridge] Received message without valid method");
    return {
      id,
      error: {
        message: "Invalid RPC request: missing or invalid 'method'",
      },
    };
  }

  const handler = Object.hasOwn(rpcHandlers, method) ? rpcHandlers[method] : null;
  if (!handler) {
    console.warn("[foundryBridge] No handler for method:", method);
    return {
      id,
      error: {
        message: `Unknown method '${method}'`,
      },
    };
  }

  try {
    const result = await handler(params ?? {});
    return { id, result };
  } catch (err) {
    console.debug("[foundryBridge] RPC failed", method, err?.rpcError?.type || "RpcError");
    return {
      id,
      error: err?.rpcError || { type: "RpcError", message: err?.message || "RPC handler failed" },
    };
  }
}

/**
 * Schedule a reconnection attempt with exponential backoff.
 */
function scheduleReconnect() {
  if (manuallyClosed) {
    console.log("[foundryBridge] Not scheduling reconnect; connection was closed manually.");
    return;
  }

  reconnectAttempts += 1;
  const delay = Math.min(
    RECONNECT_BASE_DELAY_MS * Math.pow(RECONNECT_BACKOFF_FACTOR, reconnectAttempts - 1),
    RECONNECT_MAX_DELAY_MS
  );

  console.warn(
    `[foundryBridge] Scheduling reconnect attempt #${reconnectAttempts} in ${delay}ms`
  );

  if (reconnectTimeoutId !== null) {
    clearTimeout(reconnectTimeoutId);
  }

  reconnectTimeoutId = setTimeout(() => {
    reconnectTimeoutId = null;
    console.log("[foundryBridge] Attempting to re-establish WebSocket connection...");
    openWebSocket();
  }, delay);
}

/**
 * Open a WebSocket connection to the Python server and set up handlers
 * for incoming RPC requests.
 *
 * This function is internal; use connectFoundryBridge() as the public API.
 */
function openWebSocket() {
  // If there's an existing socket, ensure it's closed before opening a new one
  if (currentSocket && [WebSocket.OPEN, WebSocket.CONNECTING].includes(currentSocket.readyState)) {
    console.log("[foundryBridge] Existing WebSocket is open; not opening a new one.");
    return currentSocket;
  }

  const WS_URL = game.settings.get("foundry-mcp", "bridgeUrl");
  const url = new URL(WS_URL);
  const token = game.settings.get("foundry-mcp", "browserToken");
  if (game.settings.get("foundry-mcp", "developmentExecution") &&
      (!token || !["localhost", "127.0.0.1", "[::1]"].includes(url.hostname) || !["ws:", "wss:"].includes(url.protocol))) {
    console.error("[foundryBridge] Development execution requires a local URL and browser credential");
    return null;
  }

  manuallyClosed = false;
  const socket = new WebSocket(WS_URL);
  currentSocket = socket;

  socket.addEventListener("open", () => {
    if (currentSocket !== socket) return;
    if (token) socket.send(JSON.stringify({ token }));
    console.log("[foundryBridge] WebSocket connection established");
    console.log("[foundryBridge] Ready to receive RPC requests from Python server");

    // Reset reconnection state on successful connection
    reconnectAttempts = 0;
    if (reconnectTimeoutId !== null) {
      clearTimeout(reconnectTimeoutId);
      reconnectTimeoutId = null;
    }
  });

  socket.addEventListener("message", async (event) => {
    let message;
    try {
      message = JSON.parse(event.data);
    } catch (e) {
      console.warn("[foundryBridge] Received non-JSON message");
      return;
    }

    if (currentSocket !== socket) return;
    console.debug("[foundryBridge] RPC", message?.id, message?.method);

    const response = await handleRpcMessage(message);
    if (!response) {
      return;
    }

    try {
      const payload = JSON.stringify(response);
      if (currentSocket === socket && socket.readyState === WebSocket.OPEN) socket.send(payload);
    } catch (e) {
      console.error("[foundryBridge] Failed to send RPC response");
    }
  });

  socket.addEventListener("close", (event) => {
    console.warn(
      "[foundryBridge] WebSocket connection closed:",
      event.code,
      event.reason
    );

    if (currentSocket !== socket) return;
    currentSocket = null;

    // Attempt to reconnect unless the close was initiated manually
    if (!manuallyClosed) {
      scheduleReconnect();
    }
  });

  socket.addEventListener("error", (event) => {
    console.error("[foundryBridge] WebSocket error:", event);
    // Let the 'close' event handle reconnection; some browsers fire both.
  });

  return socket;
}

/**
 * Public API: establish (or ensure) a WebSocket connection to the Python server
 * and set up handlers for incoming RPC requests.
 *
 * This function should be called once from the Foundry "ready" hook,
 * and only by the GM client.
 */
export function connectFoundryBridge() {
  console.log("[foundryBridge] Initializing Foundry MCP WebSocket bridge.");
  return openWebSocket();
}

/**
 * Optional helper to explicitly close the WebSocket and stop automatic
 * reconnection attempts. Not currently used, but provided for completeness.
 */
export function disconnectFoundryBridge() {
  manuallyClosed = true;

  if (reconnectTimeoutId !== null) {
    clearTimeout(reconnectTimeoutId);
    reconnectTimeoutId = null;
  }

  if (currentSocket) {
    try {
      currentSocket.close();
    } catch (e) {
      console.error("[foundryBridge] Error while closing WebSocket:", e);
    } finally {
      currentSocket = null;
    }
  }

  console.log("[foundryBridge] Foundry MCP WebSocket bridge disconnected.");
}
