/** Independent request correlation over the existing authenticated GM socket. */
let socket = null;
const pending = new Map();
let counter = 0;
export function gmOnly() {
  if (!globalThis.game?.user?.isGM) throw new Error("PDF Library is GM-only.");
}
export function setPdfSocket(value) {
  if (socket === value) return;
  socket = value;
  for (const { reject, timer } of pending.values()) {
    clearTimeout(timer); reject(new Error("Bridge disconnected; incomplete uploads must be retried."));
  }
  pending.clear();
}
export function handlePdfMessage(value) {
  if (!value?.type?.startsWith("pdf.")) return false;
  const entry = pending.get(value.request_id);
  if (entry) {
    clearTimeout(entry.timer); pending.delete(value.request_id);
    if (value.type === "pdf.upload.error") entry.reject(new Error(value.message || "PDF operation rejected."));
    else entry.resolve(value);
  }
  return true;
}
export function pdfRequest(type, fields = {}) {
  gmOnly();
  if (!socket || socket.readyState !== 1) return Promise.reject(new Error("Connect an authenticated GM bridge first."));
  if (pending.size >= 8) return Promise.reject(new Error("Too many PDF requests; retry shortly."));
  const owner = socket;
  const request_id = `pdf-${++counter}`;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { pending.delete(request_id); reject(new Error("PDF request timed out; retry the transfer.")); }, 15000);
    pending.set(request_id, { resolve, reject, timer });
    try { owner.send(JSON.stringify({ ...fields, type, request_id, protocol: 1 })); }
    catch { clearTimeout(timer); pending.delete(request_id); reject(new Error("Bridge send failed.")); }
  });
}
