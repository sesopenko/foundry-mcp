/**
 * ES module responsible for handling WebSocket communication with the
 * Python FoundryConnectionManager and dispatching RPC-style requests.
 *
 * It currently implements a single RPC method:
 *   - getPlayerNameList: returns an array of strings (hard-coded for now)
 */

const WS_URL = "ws://localhost:8000/ws/foundry";

/**
 * Map of method names to handler functions.
 * Each handler receives a single `params` object and may return a value
 * or a Promise resolving to a value.
 */
const rpcHandlers = {
  /**
   * Return a hard-coded list of player names for integration testing.
   *
   * @param {object} params
   * @returns {string[]}
   */
  async getPlayerNameList(params) {
    // params are currently unused, but kept for future expansion
    console.log("[foundryBridge] getPlayerNameList called with params:", params);
    return ["Alice", "Bob", "Charlie"];
  },
};

/**
 * Handle a single incoming RPC request message and return the response object.
 *
 * @param {object} message - Parsed JSON message from the WebSocket.
 * @returns {Promise<object>} - Response object to send back over WebSocket.
 */
async function handleRpcMessage(message) {
  const { id, method, params } = message;

  if (!id) {
    console.warn("[foundryBridge] Received message without id:", message);
    return null;
  }

  if (!method || typeof method !== "string") {
    console.warn("[foundryBridge] Received message without valid method:", message);
    return {
      id,
      error: {
        message: "Invalid RPC request: missing or invalid 'method'",
      },
    };
  }

  const handler = rpcHandlers[method];
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
    console.error("[foundryBridge] Error while handling method", method, err);
    return {
      id,
      error: {
        message: err?.message || `Error while handling method '${method}'`,
      },
    };
  }
}

/**
 * Open a WebSocket connection to the Python server and set up handlers
 * for incoming RPC requests.
 *
 * This function should be called once from the Foundry "ready" hook,
 * and only by the GM client.
 */
export function connectFoundryBridge() {
  console.log("[foundryBridge] Connecting to", WS_URL);

  const socket = new WebSocket(WS_URL);

  socket.addEventListener("open", () => {
    console.log("[foundryBridge] WebSocket connection established");
    console.log("[foundryBridge] Ready to receive RPC requests from Python server");
  });

  socket.addEventListener("message", async (event) => {
    let message;
    try {
      message = JSON.parse(event.data);
    } catch (e) {
      console.warn("[foundryBridge] Received non-JSON message:", event.data);
      return;
    }

    console.log("[foundryBridge] Received RPC message:", message);

    const response = await handleRpcMessage(message);
    if (!response) {
      return;
    }

    try {
      const payload = JSON.stringify(response);
      console.log("[foundryBridge] Sending RPC response:", response);
      socket.send(payload);
    } catch (e) {
      console.error("[foundryBridge] Failed to send response:", e, response);
    }
  });

  socket.addEventListener("close", (event) => {
    console.warn(
      "[foundryBridge] WebSocket connection closed:",
      event.code,
      event.reason
    );
  });

  socket.addEventListener("error", (event) => {
    console.error("[foundryBridge] WebSocket error:", event);
  });

  return socket;
}
