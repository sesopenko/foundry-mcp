import { getModuleBuildInfo, reportServerBuild } from "./versionStatus.js";
import { executeJavaScript } from "./exploration.js";
import { bridgeUrl } from "./connectionConfig.js";
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
let clearCurrentAuthTimer = null;
let reconnectAttempts = 0;
let reconnectTimeoutId = null;
let manuallyClosed = false;
let connectionStatus = { state: "Disconnected", message: "Bridge has not connected." };
const reported = new Set();

/** Local module status; no Foundry internals or UI DOM are inspected. */
export function getConnectionStatus() { return { ...connectionStatus }; }

function reportStatus(state, message) {
  connectionStatus = { state, message };
  const key = `${state}:${message}`;
  if (reported.has(key)) return;
  reported.add(key);
  const text = `Foundry MCP — ${state}: ${message}`;
  console.info(text);
  const notifications = globalThis.ui?.notifications;
  if (state === "Misconfigured") notifications?.error(text);
  else if (state === "Disconnected") notifications?.warn(text);
  else notifications?.info(text);
}

/**
 * Map of method names to handler functions.
 * Each handler receives a single `params` object and may return a value
 * or a Promise resolving to a value.
 */
const rpcHandlers = {
  getModuleBuildInfo,
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

  let url;
  try {
    url = bridgeUrl(game.settings.get("foundry-mcp", "bridgeUrl"));
  } catch (error) {
    reportStatus("Misconfigured", error.message);
    return null;
  }
  const development = game.settings.get("foundry-mcp", "developmentExecution");
  const token = development ? game.settings.get("foundry-mcp", "browserToken") : "";
  if (development &&
      (!token || !["localhost", "127.0.0.1", "[::1]"].includes(url.hostname) || !["ws:", "wss:"].includes(url.protocol))) {
    reportStatus("Misconfigured", "Development execution requires a loopback URL and browser credential.");
    return null;
  }

  const production = Boolean(game.settings.get("foundry-mcp", "productionAuthentication"));
  const credential = production ? game.settings.get("foundry-mcp", "bridgeCredential") : "";
  if (production && (development || typeof credential !== "string" || !credential ||
      (url.protocol !== "wss:" && !["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)))) {
    reportStatus("Misconfigured", "Production authentication requires a nonempty bridge credential, WSS for remote hosts, and development execution disabled.");
    return null;
  }
  let authenticated = !production;
  let authTimer = null;
  let authenticationTimedOut = false;
  const clearAuthTimer = () => { if (authTimer !== null) clearTimeout(authTimer); authTimer = null; };
  manuallyClosed = false;
  let socket;
  try {
    socket = new WebSocket(url.href);
  } catch {
    reportStatus("Misconfigured", "The browser rejected the WebSocket. Check the URL, TLS certificate, and page transport.");
    return null;
  }
  currentSocket = socket;
  clearCurrentAuthTimer = clearAuthTimer;
  reportStatus("Connecting", "Opening the browser bridge.");

  socket.addEventListener("open", () => {
    if (currentSocket !== socket) return;
    if (token) socket.send(JSON.stringify({ token }));
    if (production) {
      socket.send(JSON.stringify({ type: "auth", token: credential }));
      reportStatus("Authenticating", "Waiting for server authentication acknowledgment.");
      authTimer = setTimeout(() => {
        authTimer = null;
        if (currentSocket !== socket) return;
        manuallyClosed = true;
        authenticationTimedOut = true;
        reportStatus("Misconfigured", "Authentication acknowledgment timed out. Check the server version and bridge credential, then save settings to reconnect.");
        socket.close(1008);
      }, 5000);
    } else {
      connected();
    }
  });

  function connected() {
    reportStatus("Connected", production ? "Browser bridge authenticated." : "WebSocket open; MCP calls can now reach this browser unless the server rejects it.");
    reconnectAttempts = 0;
    if (reconnectTimeoutId !== null) clearTimeout(reconnectTimeoutId);
    reconnectTimeoutId = null;
  }

  socket.addEventListener("message", async (event) => {
    let message;
    try {
      message = JSON.parse(event.data);
    } catch (e) {
      console.warn("[foundryBridge] Received non-JSON message");
      return;
    }

    if (currentSocket !== socket || authenticationTimedOut) return;
    if (!authenticated) {
      if (message?.type === "auth" && message.status === "ok") {
        authenticated = true;
        if (message.server_build !== undefined) reportServerBuild(message.server_build);
        clearAuthTimer();
        connected();
      }
      return;
    }
    if (message?.type === "serverInfo") {
      reportServerBuild(message.server_build);
      return;
    }
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
      event.code
    );

    clearAuthTimer();
    if (currentSocket !== socket) return;
    currentSocket = null;
    clearCurrentAuthTimer = null;
    if (authenticationTimedOut) return;
    if (production && event.code === 1008) {
      manuallyClosed = true;
      reportStatus("Misconfigured", "Server rejected authentication or another GM owns the bridge. Check credentials and competing tabs, then save settings to reconnect.");
      return;
    }
    reportStatus("Disconnected", event.code === 1008
      ? "Server rejected the bridge. Close competing GM tabs or check development credentials."
      : "Connection lost; retrying with backoff. Check the server and configured URL.");

    // Attempt to reconnect unless the close was initiated manually
    if (!manuallyClosed) {
      scheduleReconnect();
    }
  });

  socket.addEventListener("error", (event) => {
    console.error("[foundryBridge] WebSocket transport error; check server reachability and TLS.");
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
  clearCurrentAuthTimer?.();
  clearCurrentAuthTimer = null;

  if (reconnectTimeoutId !== null) {
    clearTimeout(reconnectTimeoutId);
    reconnectTimeoutId = null;
  }

  if (currentSocket) {
    const socket = currentSocket;
    currentSocket = null;
    try {
      socket.close();
    } catch (e) {
      console.error("[foundryBridge] Error while closing WebSocket:", e);
    } finally {
      currentSocket = null;
    }
  }

  reportStatus("Disconnected", "Bridge stopped in this browser.");

  console.log("[foundryBridge] Foundry MCP WebSocket bridge disconnected.");
}

/** Apply settings changes without reloading the game or reviving an old socket. */
export function reconnectFoundryBridge() {
  disconnectFoundryBridge();
  reconnectAttempts = 0;
  return connectFoundryBridge();
}
