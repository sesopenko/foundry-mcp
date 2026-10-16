/** Validate a complete browser endpoint without logging its supplied value. */
export function bridgeUrl(value, pageProtocol = globalThis.location?.protocol) {
  let url;
  try {
    if (typeof value !== "string" || !value.trim()) throw new Error();
    url = new URL(value);
  } catch {
    throw new Error("Enter a full ws:// or wss:// URL ending in /ws/foundry.");
  }
  if (!["ws:", "wss:"].includes(url.protocol) || !url.hostname ||
      url.username || url.password || url.hash || url.search || url.pathname !== "/ws/foundry") {
    throw new Error("Use ws:// or wss:// with a host and /ws/foundry; omit credentials, query, and fragment.");
  }
  if (pageProtocol === "https:" && url.protocol === "ws:" &&
      !["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)) {
    throw new Error("This HTTPS Foundry page needs a browser-trusted wss:// bridge endpoint. Ask your operator for its URL.");
  }
  return url;
}
