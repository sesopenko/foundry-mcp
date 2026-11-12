/** Private immutable preview originals. Standard fetch/Blob/AbortController APIs;
 * Foundry public membership/identity calls remain in resolvePreviewSource.
 * No RPC/MCP registration, filesystem access or game-system semantics here.
 */
import {resolvePreviewSource} from './journalImages.js';
import {fail} from './actorReadUtils.js';

export const PREVIEW_FETCH_LIMITS = Object.freeze({maxBytes: 128 * 1024 * 1024,
  readTimeout: 15000, totalTimeout: 300000, maxReadBytes: 32768});
const messages = Object.freeze({
  Busy: 'Another private image source is active; release it before starting another.',
  NotReady: 'Connect the existing ready GM world.',
  PermissionDenied: 'Image byte reading requires the connected GM.',
  ContextChanged: 'World, GM or socket changed; start a fresh image request.',
  TransferReleased: 'Private original was released; start a fresh image request.',
  TransferCancelled: 'Private original was cancelled; start a fresh image request.',
  TransferTimeout: 'Five-minute private transfer deadline exceeded; start a fresh image request.',
  ImageReadTimeout: 'Source read stalled; select an available image and retry.',
  ImageTooLarge: 'Original exceeds the128 MiB compressed limit; select a smaller source.',
  ImageUnavailable: 'Selected image could not be read without redirects; browse a readable configured source.',
  IncompleteTransfer: 'Source bytes do not match their declared length; start a fresh image request.',
  InvalidChunk: 'Use contained integer offset/length, at most32768 bytes per read.',
});

function error(code) {fail(code, messages[code] ?? messages.ImageUnavailable);}

/** Factory for one private original slot; injectable clocks/bounds are for tests.
 * begin(input,{isCurrent,signal}) resolves/fetches once and returns a frozen lease
 * {context,size_bytes,deadline,read(offset,length),release()}. read returns a copy,
 * never the stored original. release is idempotent and cannot clear a newer slot.
 * Keep the owner signal active until transfer completion; abort it on disconnect.
 * The five-minute deadline includes resolution, fetch and retained-lease time.
 */
export function createPreviewFetchService({resolve = resolvePreviewSource, fetchImpl = (...args) => fetch(...args),
  now = () => Date.now(), setTimer = setTimeout, clearTimer = clearTimeout,
  limits = PREVIEW_FETCH_LIMITS} = {}) {
  let active = null;

  async function begin(input, {isCurrent = () => true, signal} = {}) {
    if (active) error('Busy');
    if (!globalThis.game?.ready || !game.world?.id) error('NotReady');
    if (!game.user?.isGM) error('PermissionDenied');
    const state = {world: game.world.id, user: game.user, controller: new AbortController(),
      deadline: now() + limits.totalTimeout, reason: null, buffers: [], blob: null, reader: null};
    active = state;
    let totalTimer;

    function disposeReader(cancel) {
      const reader = state.reader;
      state.reader = null;
      if (!reader) return;
      // AbortController terminates the real fetch. Also cancel injected/readable
      // streams; never wait indefinitely for a misbehaving source's cancellation.
      if (cancel) {
        try {Promise.resolve(reader.cancel()).catch(() => {});} catch { /* already closed */ }
      }
      try {reader.releaseLock();} catch { /* a cancelled pending read can still own the lock */ }
    }
    function close(reason = 'TransferReleased') {
      if (state.reason) return;
      state.reason = reason;
      clearTimer(totalTimer);
      signal?.removeEventListener('abort', cancelled);
      state.buffers = []; state.blob = null;
      state.controller.abort();
      disposeReader(true);
      if (active === state) active = null;
    }
    function cancelled() {close('TransferCancelled');}
    function guard() {
      if (state.reason) error(state.reason);
      if (!globalThis.game?.ready || game.world?.id !== state.world || game.user !== state.user || !game.user?.isGM || !isCurrent()) {
        close('ContextChanged'); error('ContextChanged');
      }
      if (now() >= state.deadline) {close('TransferTimeout'); error('TransferTimeout');}
    }
    async function bounded(operation) {
      guard();
      let timer, aborted;
      try {
        const interrupted = new Promise((_, reject) => {
          aborted = () => {try {error(state.reason ?? 'TransferCancelled');} catch (value) {reject(value);}};
          state.controller.signal.addEventListener('abort', aborted, {once: true});
          timer = setTimer(() => close('ImageReadTimeout'), limits.readTimeout);
        });
        const result = await Promise.race([Promise.resolve().then(operation), interrupted]);
        guard(); return result;
      } finally {
        clearTimer(timer);
        state.controller.signal.removeEventListener('abort', aborted);
      }
    }
    signal?.addEventListener('abort', cancelled, {once: true});
    totalTimer = setTimer(() => close('TransferTimeout'), limits.totalTimeout);
    if (signal?.aborted) cancelled();
    try {
      const selection = await bounded(() => resolve(input, isCurrent));
      guard();
      const response = await bounded(() => fetchImpl(selection.fetch_url, {
        credentials: selection.credentials, mode: selection.image.source === 's3' ? 'cors' : 'same-origin',
        redirect: 'error', cache: 'no-store', signal: state.controller.signal,
      }));
      if (response.status !== 200 || response.redirected || response.url !== selection.fetch_url || !response.body?.getReader) error('ImageUnavailable');
      const declared = response.headers.get('Content-Length');
      // Browser fetch exposes decompressed body bytes. For HTTP gzip/br/etc the
      // declared length describes the wire representation, not these file bytes.
      const identityEncoding = !response.headers.get('Content-Encoding') || response.headers.get('Content-Encoding').toLowerCase() === 'identity';
      let expected = null;
      if (declared !== null) {
        if (!/^\d+$/.test(declared) || !Number.isSafeInteger(Number(declared))) error('ImageUnavailable');
        expected = Number(declared);
        if (expected > limits.maxBytes) error('ImageTooLarge');
      }
      state.reader = response.body.getReader();
      let length = 0;
      while (true) {
        const part = await bounded(() => state.reader.read());
        if (part.done) break;
        if (!(part.value instanceof Uint8Array)) error('ImageUnavailable');
        length += part.value.byteLength;
        if (length > limits.maxBytes) error('ImageTooLarge');
        // Own a snapshot, even if a stream reuses its input buffer afterwards.
        state.buffers.push(part.value.slice());
      }
      disposeReader(false);
      if (!length || (identityEncoding && expected !== null && length !== expected)) error('IncompleteTransfer');
      state.blob = new Blob(state.buffers);
      state.buffers = [];
      const context = Object.freeze({...selection, image: Object.freeze({...selection.image}),
        ...(selection.limitations ? {limitations: Object.freeze([...selection.limitations])} : {})});
      return Object.freeze({context, size_bytes: length, deadline: state.deadline,
        async read(offset, count) {
          try {
            guard();
            if (!Number.isSafeInteger(offset) || !Number.isSafeInteger(count) || offset < 0 || count < 1 || count > limits.maxReadBytes || offset + count > length) error('InvalidChunk');
            return new Uint8Array(await bounded(() => state.blob.slice(offset, offset + count).arrayBuffer()));
          } catch (failure) {
            close(failure.rpcError?.code ?? 'ImageUnavailable');
            if (failure.rpcError && Object.hasOwn(messages, failure.rpcError.code)) throw failure;
            error('ImageUnavailable');
          }
        }, release: () => close(),
      });
    } catch (failure) {
      close(failure.rpcError?.code ?? 'ImageUnavailable');
      // Resolver errors already have fixed categories/messages; no native fetch
      // error, credential-bearing URL or arbitrary stack crosses this boundary.
      if (failure.rpcError && (Object.hasOwn(messages, failure.rpcError.code) ||
          ['InvalidRequest','UnsupportedVersion','UnsupportedCapability','UnsupportedSource','SourceTooLarge','ImageNotFound','AmbiguousSource','BrowseFailed','DirectoryTooLarge','ReadFailed'].includes(failure.rpcError.code))) throw failure;
      error('ImageUnavailable');
    }
  }
  return Object.freeze({begin, get busy() {return active !== null;}});
}

export const previewSourceFetch = createPreviewFetchService();
