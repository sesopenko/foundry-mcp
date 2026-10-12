/** Bounded snapshots only; no implicit toObject(), getters, or toJSON(). */
const MAX_BYTES = 60000;
const encoder = new TextEncoder();

export function serializeForRpc(value) {
  const seen = new WeakSet();
  let nodes = 0;
  let stringBytes = 0;
  const text = value => {
    const clipped = value.slice(0, 1000);
    stringBytes += encoder.encode(clipped).length;
    return stringBytes > 20000 ? "[String budget exceeded]" : clipped;
  };
  function visit(value, depth) {
    if (++nodes > 1000) return { $type: "Truncated", reason: "node limit" };
    if (value === null || typeof value === "boolean") return value;
    if (typeof value === "string") return text(value);
    if (typeof value === "number") return Number.isFinite(value) ? value : { $type: "Number", value: String(value) };
    if (typeof value === "undefined") return { $type: "Undefined" };
    if (typeof value === "bigint") return { $type: "BigInt", value: text(String(value)) };
    if (typeof value === "symbol") return { $type: "Symbol", value: text(String(value)) };
    if (typeof value === "function") return { $type: "Function" };
    if (seen.has(value)) return { $type: "Circular" };
    if (depth >= 5) return { $type: "Truncated", reason: "depth limit" };
    seen.add(value);
    try {
      if (value instanceof Map) {
        const entries = [];
        for (const [key, item] of Map.prototype.entries.call(value)) {
          if (entries.length >= 50 || nodes > 1000) break;
          entries.push([visit(key, depth + 1), visit(item, depth + 1)]);
        }
        return { $type: "Map", entries, truncated: entries.length < Object.getOwnPropertyDescriptor(Map.prototype, "size").get.call(value) };
      }
      if (value instanceof Set) {
        const values = [];
        for (const item of Set.prototype.values.call(value)) {
          if (values.length >= 50 || nodes > 1000) break;
          values.push(visit(item, depth + 1));
        }
        return { $type: "Set", values, truncated: values.length < Object.getOwnPropertyDescriptor(Set.prototype, "size").get.call(value) };
      }
      if (Array.isArray(value)) {
        const values = [];
        const length = Object.getOwnPropertyDescriptor(value, "length").value;
        for (let i = 0; i < Math.min(length, 50) && nodes <= 1000; i++) {
          const descriptor = Object.getOwnPropertyDescriptor(value, String(i));
          values.push(!descriptor ? { $type: "Undefined" } : "value" in descriptor ? visit(descriptor.value, depth + 1) : { $type: "Accessor" });
        }
        return { $type: "Array", values, truncated: values.length < length };
      }
      const properties = Object.create(null);
      let count = 0;
      let truncated = false;
      // for-in avoids allocating an unbounded list of property descriptors.
      for (const key in value) {
        if (!Object.hasOwn(value, key)) continue;
        if (count++ >= 50 || nodes > 1000) { truncated = true; break; }
        const descriptor = Object.getOwnPropertyDescriptor(value, key);
        properties[text(key)] = descriptor && "value" in descriptor ? visit(descriptor.value, depth + 1) : { $type: "Accessor" };
      }
      if (value instanceof Error) {
        for (const key of ["message", "stack"]) {
          const descriptor = Object.getOwnPropertyDescriptor(value, key);
          if (descriptor && "value" in descriptor) properties[key] = visit(descriptor.value, depth + 1);
        }
      }
      const proto = Object.getPrototypeOf(value);
      const constructor = proto && Object.getOwnPropertyDescriptor(proto, "constructor");
      const name = constructor && "value" in constructor && Object.getOwnPropertyDescriptor(constructor.value, "name");
      return { $type: value instanceof Error ? "Error" : name && "value" in name ? text(String(name.value)) : "Object", properties, truncated };
    } catch {
      return { $type: "Unserializable" };
    }
  }
  const result = visit(value, 0);
  if (encoder.encode(JSON.stringify(result)).length > MAX_BYTES) return { $type: "Truncated", reason: "response byte limit" };
  return result;
}

function executionError(type, error) {
  // Arbitrary thrown objects can contain getters; never read them directly.
  const read = key => {
    try {
      const descriptor = Object.getOwnPropertyDescriptor(error, key);
      return descriptor && typeof descriptor.value === "string" ? descriptor.value.slice(0, 2000) : undefined;
    } catch { return undefined; }
  };
  const result = new Error(read("message") || (typeof error === "string" ? error.slice(0, 2000) : type));
  result.rpcError = { type, message: result.message, stack: read("stack") };
  return result;
}

export async function executeJavaScript(params) {
  if (!game.user?.isGM || !game.settings.get("foundry-mcp", "developmentExecution") || !game.settings.get("foundry-mcp", "browserToken")) {
    throw executionError("UnauthorizedExecution", "GM development execution is disabled or credentials are missing");
  }
  if (!params || typeof params.code !== "string" || !params.code.trim() || encoder.encode(params.code).length > 32768) {
    throw executionError("InvalidParameters", "Expected nonempty JavaScript source up to 32768 UTF-8 bytes");
  }
  const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
  let execute;
  try { execute = new AsyncFunction(`"use strict";\n${params.code}`); }
  catch (error) { throw executionError("JavaScriptCompilationError", error); }
  let value;
  try { value = await execute(); }
  catch (error) { throw executionError("JavaScriptRuntimeError", error); }
  try { return { value: serializeForRpc(value), foundryVersion: game.version }; }
  catch (error) { throw executionError("SerializationError", error); }
}
