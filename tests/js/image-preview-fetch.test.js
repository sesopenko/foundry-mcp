import test from 'node:test';
import assert from 'node:assert/strict';
import {createPreviewFetchService, PREVIEW_FETCH_LIMITS} from '../../foundry-module/scripts/imagePreviewFetch.js';

const code = value => error => error.rpcError?.code === value;
const deferred = () => {let resolve, reject; const promise = new Promise((a,b) => {resolve=a; reject=b;}); return {promise,resolve,reject};};
const flush = () => new Promise(resolve => setImmediate(resolve));

function clock() {
  let time = 0, next = 0;
  const timers = new Map();
  return {now: () => time, setTimer(fn, ms) {const id=++next; timers.set(id,{fn,at:time+ms}); return id;},
    clearTimer(id) {timers.delete(id);}, get pending() {return timers.size;},
    async tick(ms) {time+=ms; for(const [id,value] of [...timers])if(value.at<=time){timers.delete(id);value.fn();} await flush();}};
}

function fixture(t, options={}) {
  globalThis.game = {ready:true,version:'14.369',world:{id:'test'},user:{id:'gm',isGM:true}};
  const timing=clock();
  const f={parts:[new Uint8Array([1,2,3]),new Uint8Array([4,5])],calls:[],cancelled:0,released:0,reads:0,declared:'5',
    selection:{image:{source:'data',directory:'assets',src:'assets/a.png'},fetch_url:'https://foundry.example/assets/a.png',credentials:'same-origin',world_id:'test',user_id:'gm'}};
  const resolve=async args => {f.resolveArgs=args; return f.selection;};
  const reader={async read(){f.reads++; await f.onRead?.(); return f.parts.length?{done:false,value:f.parts.shift()}:{done:true};},
    cancel(){f.cancelled++;return Promise.resolve();},releaseLock(){f.released++;}};
  const fetchImpl=async(...args)=>{f.calls.push(args); await f.onFetch?.(); return {status:200,url:f.selection.fetch_url,redirected:false,
    headers:{get:key=>key==='Content-Length'?f.declared:key==='Content-Encoding'?(f.encoding??null):null},body:{getReader:()=>reader},...f.response};};
  f.service=createPreviewFetchService({resolve,fetchImpl,...timing,limits:{...PREVIEW_FETCH_LIMITS,maxBytes:8},...options});
  f.timing=timing;
  f.begin = async (...args) => {const lease=await f.service.begin(...args); t.after(()=>lease.release());return lease;};
  return f;
}

test('streamed immutable snapshot, contained copy reads and exact local credential policy', async t => {
  const f=fixture(t), input={src:'assets/a.png'}, lease=await f.begin(input);
  assert.equal(lease.size_bytes,5);assert.equal(f.service.busy,true);assert.deepEqual(f.resolveArgs,input);
  assert.equal(lease.context.world_id,'test');assert.ok(Object.isFrozen(lease.context.image));
  assert.equal(f.calls.length,1);
  const [url,opts]=f.calls[0];assert.equal(url,f.selection.fetch_url);
  assert.deepEqual({credentials:opts.credentials,mode:opts.mode,redirect:opts.redirect,cache:opts.cache},
    {credentials:'same-origin',mode:'same-origin',redirect:'error',cache:'no-store'});
  assert.ok(opts.signal instanceof AbortSignal);
  const bytes=await lease.read(1,3);assert.deepEqual([...bytes],[2,3,4]);bytes[0]=99;
  assert.deepEqual([...(await lease.read(1,3))],[2,3,4]);assert.equal(f.released,1);
  lease.release();assert.equal(f.service.busy,false);assert.equal(f.timing.pending,0);
  await assert.rejects(lease.read(0,1),code('TransferReleased'));
});

test('stream buffer reuse cannot mutate the pinned original', async t => {
  const f=fixture(t), shared=f.parts[0];
  f.onRead=()=>{if(f.reads===2)shared.fill(9);};
  const lease=await f.begin({src:'assets/a.png'});
  assert.deepEqual([...(await lease.read(0,5))],[1,2,3,4,5]);
});

test('S3 uses exact picker-selected signed object with CORS and no Foundry credentials', async t => {
  const f=fixture(t);f.selection={...f.selection,image:{source:'s3',bucket:'test-bucket',directory:'assets',src:'https://s3.example/assets/a.png?signature=secret'},
    fetch_url:'https://s3.example/assets/a.png?signature=secret',credentials:'omit'};
  const lease=await f.begin({src:f.selection.fetch_url});
  assert.equal(f.calls[0][0],f.selection.fetch_url);assert.equal(f.calls[0][1].credentials,'omit');assert.equal(f.calls[0][1].mode,'cors');
  assert.equal(lease.size_bytes,5);
});

test('absent length works, excessive declared/streamed size and dishonest length reject with cleanup', async t => {
  const absent=fixture(t);absent.declared=null;assert.equal((await absent.begin({src:'assets/a.png'})).size_bytes,5);
  for (const [declared,parts,expected] of [['9',null,'ImageTooLarge'],[null,[new Uint8Array(9)],'ImageTooLarge'],
    ['2',null,'IncompleteTransfer'],['6',null,'IncompleteTransfer'],['0',[],'IncompleteTransfer'],['bad',null,'ImageUnavailable']]) {
    const f=fixture(t);f.declared=declared;if(parts)f.parts=parts;
    await assert.rejects(f.begin({src:'assets/a.png'}),code(expected));
    assert.equal(f.service.busy,false);assert.equal(f.timing.pending,0);assert.ok(f.calls[0][1].signal.aborted);
    if(f.reads)assert.ok(f.released>=1);
  }
});

test('HTTP decoded body counts do not confuse encoded wire Content-Length with original file bytes', async t => {
  const f=fixture(t);f.encoding='gzip';f.declared='3';
  const lease=await f.begin({src:'assets/a.png'});
  assert.equal(lease.size_bytes,5);
  assert.deepEqual([...(await lease.read(0,5))],[1,2,3,4,5]);
});

test('any redirect, non200, missing stream and foreign final URL are rejected without reading bytes', async t => {
  for (const response of [{redirected:true},{url:'https://offsource.example/a.png'},{status:403},{body:null}]) {
    const f=fixture(t);f.response=response;
    await assert.rejects(f.begin({src:'assets/a.png'}),code('ImageUnavailable'));
    assert.equal(f.reads,0);assert.equal(f.service.busy,false);assert.equal(f.timing.pending,0);
  }
});

test('one admission slot spans resolution, fetch and retained bytes; stale release never clears a new owner', async t => {
  const gate=deferred();const f=fixture(t);f.onFetch=()=>gate.promise;
  const pending=f.begin({src:'assets/a.png'});await flush();
  await assert.rejects(f.begin({src:'another.png'}),code('Busy'));assert.equal(f.calls.length,1);
  gate.resolve();const first=await pending;
  await assert.rejects(f.begin({src:'another.png'}),code('Busy'));
  first.release();f.parts=[new Uint8Array([7,8])];f.declared='2';
  const second=await f.begin({src:'assets/a.png'});first.release();assert.equal(f.service.busy,true);
  assert.deepEqual([...(await second.read(0,2))],[7,8]);
});

test('non-GM/unready and changed socket/world/GM reject across awaited fetch/read', async t => {
  for (const change of [()=>{game.ready=false;},()=>{game.user.isGM=false;}]) {
    const f=fixture(t);change();await assert.rejects(f.begin({src:'assets/a.png'}),error=>['NotReady','PermissionDenied'].includes(error.rpcError?.code));
    assert.equal(f.calls.length,0);assert.equal(f.service.busy,false);
  }
  for (const stage of ['onRead','onFetch'])for(const change of [()=>{game.world.id='other';},()=>{game.user={id:'other',isGM:true};},()=>{game.user.isGM=false;}]) {
    const f=fixture(t);f[stage]=change;await assert.rejects(f.begin({src:'assets/a.png'}),code('ContextChanged'));
    assert.equal(f.service.busy,false);assert.equal(f.timing.pending,0);
  }
  const f=fixture(t);let current=true;f.onRead=()=>{current=false;};
  await assert.rejects(f.begin({src:'assets/a.png'},{isCurrent:()=>current}),code('ContextChanged'));
  assert.equal(f.service.busy,false);
});

test('owner abort interrupts resolution, fetch, stream and retained lease; drops timers and buffers', async t => {
  for (const stage of ['resolve','onFetch','onRead','retained']) {
    const gate=deferred(), owner=new AbortController();
    const f=fixture(t,stage==='resolve'?{resolve:()=>gate.promise}:{});
    if(stage==='onFetch'||stage==='onRead')f[stage]=()=>gate.promise;
    const pending=f.begin({src:'assets/a.png'},{signal:owner.signal});
    // Observe rejection immediately, avoiding artificial unhandled rejections.
    const outcome=pending.then(value=>value,error=>error);
    await flush();
    if(stage==='retained') {
      const lease=await pending;owner.abort();await assert.rejects(lease.read(0,1),code('TransferCancelled'));
    } else {
      owner.abort();assert.ok(code('TransferCancelled')(await outcome));
    }
    assert.equal(f.service.busy,false);assert.equal(f.timing.pending,0);
    gate.resolve();await flush();assert.equal(f.service.busy,false);
  }
});

test('15-second stalled read timeout and total5-minute lifetime enforced including idle lease', async t => {
  for (const stage of ['onFetch','onRead']) {
    const f=fixture(t);f[stage]=()=>new Promise(()=>{});
    const outcome=f.begin({src:'assets/a.png'}).then(value=>value,error=>error);await flush();
    await f.timing.tick(14999);assert.equal(f.service.busy,true);
    await f.timing.tick(1);assert.ok(code('ImageReadTimeout')(await outcome));assert.equal(f.service.busy,false);assert.equal(f.timing.pending,0);
  }
  const f=fixture(t), lease=await f.begin({src:'assets/a.png'});
  await f.timing.tick(299999);assert.deepEqual([...(await lease.read(0,1))],[1]);
  await f.timing.tick(1);await assert.rejects(lease.read(0,1),code('TransferTimeout'));
  assert.equal(f.service.busy,false);assert.equal(f.timing.pending,0);
});

test('invalid read bounds release the original, and native error messages never leak', async t => {
  for (const [offset,count] of [[true,1],[0,1.5],[-1,1],[0,0],[0,32769],[4,2]]) {
    const f=fixture(t), lease=await f.begin({src:'assets/a.png'});
    await assert.rejects(lease.read(offset,count),code('InvalidChunk'));assert.equal(f.service.busy,false);
  }
  const f=fixture(t);f.onFetch=()=>{throw Error('secret https://s3.example/a.png?signature=private');};
  await assert.rejects(f.begin({src:'assets/a.png'}),failure=>code('ImageUnavailable')(failure)&&!JSON.stringify(failure.rpcError).includes('secret')&&!JSON.stringify(failure.rpcError).includes('signature'));
  assert.equal(f.service.busy,false);assert.equal(f.timing.pending,0);
});
