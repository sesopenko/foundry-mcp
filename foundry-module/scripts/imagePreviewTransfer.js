/** Private indexed source transfer. No MCP registration or Foundry internals.
 * All byte/source authorization comes from imagePreviewFetch's tested lease.
 */
import {previewSourceFetch, PREVIEW_FETCH_LIMITS} from './imagePreviewFetch.js';
import {fail, validateParams} from './actorReadUtils.js';

const bytes = value => new TextEncoder().encode(JSON.stringify(value)).length;
const WINDOW = 16;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
function rejected(code) {fail(code, ({Busy:'Another image transfer is active; release it before beginning another.',
  ContextChanged:'Transfer owner/world/GM changed; begin a fresh transfer.',
  TransferTimeout:'Private transfer exceeded five minutes; begin a fresh transfer.',
  TransferNotFound:'Private transfer is unavailable; begin a fresh transfer.',
  InvalidChunk:'Return negotiated transfer_id/index/offset/length exactly; no duplicate reads.',
  TransferWindowExceeded:'At most16 chunk reads may be in flight; begin a fresh transfer.',
  InvalidFrameLimit:'Use a response ceiling from1024 to16777216 bytes and RPC IDs with serialized length<=512 bytes.',
  ResponseTooLarge:'Private metadata or chunk exceeds the configured frame ceiling; increase the ceiling or select a shorter canonical source.',
  InvalidRequest:'Use only the private transfer protocol fields.'})[code] ?? 'Private transfer failed; begin again.');}

/** One private transfer, bound to an exact socket object plus world/GM.
 * begin(params,isCurrent,{owner,rpc_id}), read(...), release(...) return wire DTOs.
 * disconnect(owner) aborts only that owner's state; old events/releases never
 * clear a newer transfer. Dependencies/clocks are injectable for unit tests.
 */
export function createPreviewTransfers({source = previewSourceFetch, now = () => Date.now(),
  setTimer = (...args) => setTimeout(...args), clearTimer = id => clearTimeout(id),
  uuid = () => crypto.randomUUID()} = {}) {
  let active = null;
  function close(state, reason = 'TransferNotFound') {
    if (!state.closed) {
      state.closed = reason;
      clearTimer(state.timer);
      state.controller.abort();
      state.requested.clear(); state.served.clear();
      if (active === state) active = null;
    }
    // A source implementation may complete after cancellation. Dispose its
    // late lease too, without changing whichever owner now occupies the slot.
    if (state.lease && !state.leaseReleased) {state.leaseReleased = true;state.lease.release();}
  }
  function frame(id) {
    if (typeof id !== 'string' || !id || bytes(id) > 512) rejected('InvalidFrameLimit');
  }
  function guard(state, isCurrent, owner) {
    if (state.closed) rejected(state.closed);
    if (owner !== state.owner) rejected('ContextChanged');
    if (!isCurrent() || !state.isCurrent() || !globalThis.game?.ready || game.world?.id !== state.world || game.user !== state.user || !game.user?.isGM) {
      close(state,'ContextChanged'); rejected('ContextChanged');
    }
    if (now() >= state.deadline) {close(state,'TransferTimeout'); rejected('TransferTimeout');}
  }
  function params(value, keys) {
    // Do not reflect unknown caller keys, which could contain signed sources.
    try {validateParams(value,keys);} catch {rejected('InvalidRequest');}
  }
  function token(value) {if (typeof value !== 'string' || !UUID.test(value)) rejected('InvalidRequest');}
  function command(input,keys,owner,rpcId) {
    const state = active;
    try {params(input,keys);frame(rpcId);token(input.transfer_id);}
    catch (failure) {
      // Malformed commands release only an exactly identified owner transfer;
      // a forged ID or stale owner cannot clear somebody else's original.
      if (state && state.owner === owner && input?.transfer_id === state.id) close(state);
      throw failure;
    }
    return state;
  }
  async function begin(input, isCurrent, {owner, rpc_id}) {
    params(input,['image','src','max_frame_bytes']); frame(rpc_id);
    if (active) {
      if (!active.isCurrent() || now() >= active.deadline || game.world?.id !== active.world || game.user !== active.user) close(active,'ContextChanged');
      else rejected('Busy');
    }
    const ceiling = input.max_frame_bytes ?? 65536;
    if (!Number.isSafeInteger(ceiling) || ceiling < 1024 || ceiling > 16777216) rejected('InvalidFrameLimit');
    const state = {owner,isCurrent,world:globalThis.game?.world?.id,user:globalThis.game?.user,
      controller:new AbortController(),requested:new Set(),served:new Set(),inflight:0,
      id:uuid(),deadline:now()+PREVIEW_FETCH_LIMITS.totalTimeout,ceiling,lease:null};
    active = state;
    state.timer = setTimer(() => close(state,'TransferTimeout'),PREVIEW_FETCH_LIMITS.totalTimeout);
    try {
      const {max_frame_bytes, ...selection} = input;
      state.lease = await source.begin(selection,{isCurrent,signal:state.controller.signal});
      guard(state,isCurrent,owner);
      // Reserve worst-case negotiated indices, offsets, raw length and an RPC
      // ID of512 serialized bytes. Every actual response is checked again.
      const overhead = bytes({id:'x'.repeat(510),result:{transfer_id:state.id,index:134217728,offset:134217728,length:32768,data_base64:''}});
      state.chunkBytes = Math.min(32768,Math.floor((ceiling-overhead)/4)*3);
      if (state.chunkBytes < 1) rejected('InvalidFrameLimit');
      state.count = Math.ceil(state.lease.size_bytes/state.chunkBytes);
      const context = state.lease.context;
      const result = {transfer_id:state.id,size_bytes:state.lease.size_bytes,chunk_bytes:state.chunkBytes,
        chunk_count:state.count,max_in_flight:WINDOW,world_id:context.world_id,user_id:context.user_id,image:context.image,
        scope_status:context.scope_status ?? 'complete',limitations:context.limitations ?? []};
      if (bytes({id:rpc_id,result}) > ceiling) rejected('ResponseTooLarge');
      return result;
    } catch (failure) {
      const reason = state.closed;
      close(state);
      if (reason) rejected(reason);
      throw failure;
    }
  }
  async function read(input,isCurrent,{owner,rpc_id}) {
    const state = command(input,['transfer_id','index','offset','length'],owner,rpc_id);
    if (!state || state.id !== input.transfer_id) rejected('TransferNotFound');
    if (state.owner !== owner) rejected('ContextChanged');
    try {
      guard(state,isCurrent,owner);
      const index = input.index;
      if (!Number.isSafeInteger(index) || index < 0 || index >= state.count || state.requested.has(index)) rejected('InvalidChunk');
      const offset = index*state.chunkBytes, length = Math.min(state.chunkBytes,state.lease.size_bytes-offset);
      if (!Number.isSafeInteger(input.offset) || !Number.isSafeInteger(input.length) || input.offset !== offset || input.length !== length) rejected('InvalidChunk');
      if (state.inflight >= WINDOW) rejected('TransferWindowExceeded');
      state.inflight++;state.requested.add(index);
      const raw = await state.lease.read(offset,length);
      guard(state,isCurrent,owner);
      if (!(raw instanceof Uint8Array) || raw.byteLength !== length) rejected('InvalidChunk');
      let binary = '';for(const value of raw)binary+=String.fromCharCode(value);
      const result = {transfer_id:state.id,index,offset,length,data_base64:btoa(binary)};
      if (bytes({id:rpc_id,result}) > state.ceiling) rejected('ResponseTooLarge');
      state.served.add(index);
      if (state.served.size === state.count) close(state);
      return result;
    } catch (failure) {close(state);throw failure;}
    finally {state.inflight--;}
  }
  function release(input,isCurrent,{owner,rpc_id}) {
    const state = command(input,['transfer_id'],owner,rpc_id);
    if (!state || state.id !== input.transfer_id || state.owner !== owner) return {released:false};
    guard(state,isCurrent,owner); close(state);return {released:true};
  }
  return Object.freeze({begin,read,release,disconnect(owner) {if (active?.owner===owner)close(active,'ContextChanged');},
    get busy() {return active !== null;}});
}

export const previewTransfers = createPreviewTransfers();
export const beginImagePreviewTransfer = (...args) => previewTransfers.begin(...args);
export const readImagePreviewChunk = (...args) => previewTransfers.read(...args);
export const releaseImagePreviewTransfer = (...args) => previewTransfers.release(...args);
