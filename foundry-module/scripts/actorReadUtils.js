/** Pure read-contract utilities. No Foundry access or game calculations. */
const encoder = new TextEncoder();
const bytes = value => encoder.encode(JSON.stringify(value)).length;

export function fail(code, message, recovery = "Correct the input and retry.") {
  const error = new Error(message);
  error.rpcError = { type: code, code, message, recovery };
  throw error;
}

export function validateParams(params, allowedKeys) {
  if (!params || typeof params !== "object" || Array.isArray(params)
      || ![Object.prototype, null].includes(Object.getPrototypeOf(params))) {
    fail("InvalidRequest", "Parameters must be a plain object.");
  }
  for (const key of Reflect.ownKeys(params)) {
    if (typeof key !== "string" || !allowedKeys.includes(key)) fail("InvalidRequest", `Unknown input: ${String(key)}.`);
  }
  return params;
}

export function integer(value, fallback, min, max, name) {
  if (value === undefined) value = fallback;
  if (!Number.isInteger(value) || value < min || value > max) fail("InvalidRequest", `${name} must be an integer from ${min} to ${max}.`);
  return value;
}

/** Check a bounded selector string; document resolution validates UUID kind. */
export function selector(value, name) {
  if (typeof value !== "string" || !value.trim() || value.length > 512) fail("InvalidRequest", `${name} must be a canonical selector of 1–512 characters.`);
  return value;
}

export function selectSections(value, allowed, defaults) {
  if (value === undefined) value = defaults;
  if (!Array.isArray(value) || !value.length || value.length > allowed.length
      || new Set(value).size !== value.length || value.some(section => !allowed.includes(section))) {
    fail("InvalidRequest", "sections must be a nonempty unique list of supported section names.");
  }
  return [...value];
}

/** Change marker only, never an authorization token. HTTP needs no Web Crypto. */
export async function digest(value) {
  const data = encoder.encode(JSON.stringify(value));
  if (globalThis.crypto?.subtle) {
    const result = await globalThis.crypto.subtle.digest("SHA-256", data);
    return Array.from(new Uint8Array(result), byte => byte.toString(16).padStart(2, "0")).join("");
  }
  let a = 2166136261; let b = 5381;
  for (const byte of data) { a = Math.imul(a ^ byte, 16777619) >>> 0; b = (Math.imul(b, 33) ^ byte) >>> 0; }
  return `http-${data.length}-${a.toString(16)}-${b.toString(16)}`;
}

/** Exact UTF-16 source fragments, bounded by serialized UTF-8 as well as units. */
export function textFragments(text) {
  if (typeof text !== "string") fail("InvalidRequest", "Text source must be a string.");
  const result = [];
  let start = 0;
  do {
    let end = start;
    while (end < text.length) {
      const width = text.codePointAt(end) > 0xffff ? 2 : 1;
      if (end + width - start > 6000 || bytes(text.slice(start, end + width)) > 1000) break;
      end += width;
    }
    result.push({ value: text.slice(start, end), text: { start, end, total: text.length, complete: end === text.length } });
    start = end;
  } while (start < text.length);
  return result;
}

/** Page detached records. Callers recheck snapshot revisions before returning. */
export async function paginate(records, base, params, scope) {
  const limit = integer(params.limit, 50, 1, 100, "limit");
  const maxBytes = integer(params.max_bytes, 48000, 8000, 48000, "max_bytes");
  const binding = await digest({ scope, limit, max_bytes: maxBytes, runtime: base.runtime });
  const token = position => btoa(JSON.stringify({ binding, revision: base.revision, position }));
  let start = 0;
  if (params.cursor !== undefined && params.cursor !== null) {
    let cursor;
    try {
      if (typeof params.cursor !== "string" || !params.cursor.length || params.cursor.length > 4096 || /[^\x00-\x7f]/.test(params.cursor)) throw Error();
      cursor = JSON.parse(atob(params.cursor));
      if (!cursor || typeof cursor !== "object" || Array.isArray(cursor)
          || typeof cursor.binding !== "string" || typeof cursor.revision !== "string"
          || !Number.isInteger(cursor.position) || cursor.position < 0) throw Error();
    } catch { fail("InvalidCursor", "Malformed continuation.", "Restart without cursor."); }
    if (cursor.binding !== binding) fail("CursorMismatch", "Continuation inputs differ.", "Restart without cursor or restore all original inputs.");
    if (cursor.revision !== base.revision) fail("ContentChanged", "Selected data changed.", "Discard accumulated pages and restart without cursor.");
    if (cursor.position > records.length) fail("InvalidCursor", "Continuation position is out of range.", "Restart without cursor.");
    start = cursor.position;
  }
  const make = end => {
    const complete = end === records.length;
    const result = { ...base, records: records.slice(start, end), pagination: { complete, next_cursor: complete ? null : token(end), returned: end - start } };
    if (base.sections) result.sections = base.sections.map(section => {
      const remains = records.slice(end).some(record => record.section === section.name);
      if (!remains || !["complete", "partial"].includes(section.status)) return { ...section, reasons: [...section.reasons] };
      return { ...section, status: "partial", reasons: [...new Set([...section.reasons, "pagination"])] };
    });
    return result;
  };
  let end = start;
  let result = make(end);
  while (end < records.length && end - start < limit) {
    const candidate = make(end + 1);
    if (bytes(candidate) > maxBytes) break;
    result = candidate;
    end++;
  }
  if (bytes(result) > maxBytes || (end === start && start < records.length)) {
    const record = records[start];
    fail("ResponseTooLarge", `Record ${record?.key ?? "metadata"} at ${record?.raw?.[0]?.path ?? "/"} exceeds max_bytes.`, "Select fewer sections or raise max_bytes within 48000.");
  }
  return result;
}
