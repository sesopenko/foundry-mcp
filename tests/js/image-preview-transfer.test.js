import test from 'node:test';
import assert from 'node:assert/strict';
import {webcrypto} from 'node:crypto';
import {createPreviewTransfers,previewTransfers,getImagePreviewContext} from '../../foundry-module/scripts/imagePreviewTransfer.js';
import {handleRpcMessage,connectFoundryBridge,disconnectFoundryBridge,reconnectFoundryBridge} from '../../foundry-module/scripts/foundryBridge.js';

globalThis.crypto ??= webcrypto;
const code = value => error => error.rpcError?.code === value;
const flush = () => new Promise(resolve => setImmediate(resolve));
const deferred = () => {let resolve;const promise=new Promise(r=>{resolve=r;});return{promise,resolve};};

function fixture(t,{length=100000}={}) {
  globalThis.game={ready:true,version:'14.369',world:{id:'test'},user:{id:'gm',isGM:true}};
  const data=Uint8Array.from({length},(_,i)=>i%251),owner={},timers=new Map();let next=0,time=0;
  const f={owner,data,releases:0,fetches:0,signals:[],reads:[],id:0};
  const source={async begin(input,{signal}) {
    f.fetches++;f.signals.push(signal);await f.onBegin?.();
    return {size_bytes:data.length,context:{image:{source:'data',directory:'assets',src:'assets/a.png'},world_id:'test',user_id:'gm'},
      async read(offset,length){f.reads.push({offset,length});await f.onRead?.();return data.slice(offset,offset+length);},release(){f.releases++;}};
  }};
  f.service=createPreviewTransfers({source,now:()=>time,setTimer:(fn,delay)=>{const id=++next;timers.set(id,{fn,at:time+delay});return id;},
    clearTimer:id=>timers.delete(id),uuid:()=>`00000000-0000-4000-8000-${String(++f.id).padStart(12,'0')}`});
  f.rpc={owner,rpc_id:'rpc-id'};f.begin=args=>f.service.begin({src:'assets/a.png',...args},()=>true,f.rpc);
  f.read=(begin,index,extra={})=>f.service.read({transfer_id:begin.transfer_id,index,offset:index*begin.chunk_bytes,
    length:Math.min(begin.chunk_bytes,begin.size_bytes-index*begin.chunk_bytes),...extra},()=>true,f.rpc);
  f.tick=async ms=>{time+=ms;for(const[id,v]of[...timers])if(v.at<=time){timers.delete(id);v.fn();}await flush();};
  f.timers=timers;t.after(()=>f.service.disconnect(owner));return f;
}

test('negotiated indexed wire contract reconstructs exact multichunk bytes out of order and releases on complete coverage',async t=>{
  const f=fixture(t),begin=await f.begin();
  assert.equal(begin.size_bytes,100000);assert.equal(begin.chunk_bytes,32768);assert.equal(begin.chunk_count,4);assert.equal(begin.max_in_flight,16);
  assert.deepEqual(Object.keys(begin).sort(),['chunk_bytes','chunk_count','image','limitations','max_in_flight','scope_status','size_bytes','transfer_id','user_id','world_id'].sort());
  const output=new Uint8Array(begin.size_bytes);
  for(const index of[3,1,2,0]) {
    const part=await f.read(begin,index);assert.equal(part.transfer_id,begin.transfer_id);assert.equal(part.index,index);
    const raw=Uint8Array.from(atob(part.data_base64),c=>c.charCodeAt(0));assert.equal(raw.length,part.length);output.set(raw,part.offset);
  }
  assert.deepEqual(output,f.data);assert.equal(f.fetches,1);assert.equal(f.releases,1);assert.equal(f.service.busy,false);assert.equal(f.timers.size,0);
  assert.deepEqual(f.service.release({transfer_id:begin.transfer_id},()=>true,f.rpc),{released:false});
});

test('pre-begin identity and caller-known reservation permit cleanup even before begin returns',async t=>{
  const f=fixture(t),context=getImagePreviewContext(),id=crypto.randomUUID();
  assert.deepEqual(context,{world_id:'test',user_id:'gm'});
  await assert.rejects(f.begin({expected_context:{...context,world_id:'wrong'}}),code('ContextChanged'));
  assert.equal(f.fetches,0);
  const gate=deferred();f.onBegin=()=>gate.promise;
  const pending=f.begin({transfer_id:id,expected_context:context});await flush();
  assert.deepEqual(f.service.release({transfer_id:id},()=>true,f.rpc),{released:true});
  assert.ok(f.signals[0].aborted);gate.resolve();await assert.rejects(pending,code('TransferNotFound'));
  assert.equal(f.service.busy,false);assert.equal(f.releases,1);
  game.user.isGM=false;assert.throws(()=>getImagePreviewContext(),code('PermissionDenied'));
});

test('every frame includes exact JSON/base64/id overhead at configurable ceilings',async t=>{
  for(const ceiling of[1024,2048,4096,65536]) {
    const f=fixture(t,{length:40000}),begin=await f.begin({max_frame_bytes:ceiling});
    assert.ok(begin.chunk_bytes<=32768&&begin.chunk_bytes>0);
    for(let index=0;index<begin.chunk_count;index++) {
      f.rpc.rpc_id='x'.repeat(510);
      const result=await f.read(begin,index);
      assert.ok(new TextEncoder().encode(JSON.stringify({id:f.rpc.rpc_id,result})).length<=ceiling);
    }
    assert.equal(f.service.busy,false);
  }
  const f=fixture(t);
  for(const ceiling of[100,1023,1.1,true,16777217])await assert.rejects(f.begin({max_frame_bytes:ceiling}),code('InvalidFrameLimit'));
  assert.equal(f.fetches,0);
  f.rpc.rpc_id='x'.repeat(511);await assert.rejects(f.begin(),code('InvalidFrameLimit'));
});

test('bad indices, offsets, lengths and duplicates release only the identified owner transfer',async t=>{
  for(const extra of[{index:-1},{index:true},{index:0.5},{index:99},{offset:1},{length:1},{length:true}]) {
    const f=fixture(t),begin=await f.begin();await assert.rejects(f.read(begin,0,extra),code('InvalidChunk'));
    assert.equal(f.service.busy,false);assert.equal(f.releases,1);assert.equal(f.timers.size,0);
  }
  const f=fixture(t),begin=await f.begin();await f.read(begin,0);
  await assert.rejects(f.read(begin,0),code('InvalidChunk'));assert.equal(f.service.busy,false);
});

test('malformed fields for an identified owner transfer cannot leave its bytes retained',async t=>{
  const f=fixture(t),begin=await f.begin();
  await assert.rejects(f.read(begin,0,{'https://private.example/?signature=secret':true}),failure=>
    code('InvalidRequest')(failure)&&!JSON.stringify(failure.rpcError).includes('secret'));
  assert.equal(f.service.busy,false);assert.equal(f.releases,1);assert.equal(f.timers.size,0);
});

test('at most16 concurrent reads, no17th allocation, failure cancels in-flight original',async t=>{
  const f=fixture(t,{length:18*32768}),begin=await f.begin(),gate=deferred();f.onRead=()=>gate.promise;
  const pending=Array.from({length:16},(_,i)=>f.read(begin,i).catch(error=>error));await flush();
  await assert.rejects(f.read(begin,16),code('TransferWindowExceeded'));assert.equal(f.reads.length,16);
  assert.equal(f.service.busy,false);assert.ok(f.signals[0].aborted);
  gate.resolve();const replies=await Promise.all(pending);assert.ok(replies.every(error=>error.rpcError));assert.equal(f.releases,1);
});

test('concurrent begin, owner isolation, idempotent release, stale callbacks and old disconnects',async t=>{
  const f=fixture(t),gate=deferred();f.onBegin=()=>gate.promise;
  const pending=f.begin();await flush();await assert.rejects(f.begin(),code('Busy'));
  f.service.disconnect(f.owner);assert.equal(f.service.busy,false);assert.ok(f.signals[0].aborted);
  // A late source-begin completion must release its own lease, never the new slot.
  f.onBegin=null;const fresh=await f.begin();gate.resolve();await assert.rejects(pending,code('ContextChanged'));
  assert.equal(f.releases,1,'late completed lease must be released even after its owner was closed');
  const other={owner:{},rpc_id:'other'};
  assert.deepEqual(f.service.release({transfer_id:fresh.transfer_id},()=>true,other),{released:false});
  await assert.rejects(f.service.read({transfer_id:fresh.transfer_id,index:0,offset:0,length:fresh.chunk_bytes},()=>true,other),code('ContextChanged'));
  assert.equal(f.service.busy,true);f.service.disconnect(other.owner);assert.equal(f.service.busy,true);
  assert.deepEqual(f.service.release({transfer_id:fresh.transfer_id},()=>true,f.rpc),{released:true});
  assert.deepEqual(f.service.release({transfer_id:fresh.transfer_id},()=>true,f.rpc),{released:false});
  const newest=await f.begin();assert.deepEqual(f.service.release({transfer_id:fresh.transfer_id},()=>true,f.rpc),{released:false});
  assert.equal(f.service.busy,true);await f.read(newest,0);
});

test('five-minute deadline, GM/world changes, and stale owner checks across awaits',async t=>{
  const f=fixture(t),begin=await f.begin();await f.tick(300000);assert.equal(f.service.busy,false);assert.ok(f.signals[0].aborted);
  await assert.rejects(f.read(begin,0),code('TransferNotFound'));
  for(const change of[()=>{game.world.id='other';},()=>{game.user={id:'other',isGM:true};},()=>{game.user.isGM=false;}]) {
    const g=fixture(t),value=await g.begin();g.onRead=change;
    await assert.rejects(g.read(value,0),code('ContextChanged'));assert.equal(g.service.busy,false);
  }
});

test('actual bridge dispatch transfers bytes privately with exact socket guard and no new MCP tool',async t=>{
  const owner={},data=Uint8Array.from({length:70000},(_,i)=>i%239);
  globalThis.game={ready:true,version:'14.369',world:{id:'test'},user:{id:'gm',isGM:true}};
  globalThis.location={origin:'https://foundry.example'};
  class Picker {constructor(){this.sources={data:{}};}static async browse(source,target){return{target,dirs:[],files:['assets/a.png']};}}
  globalThis.foundry={applications:{apps:{FilePicker:{implementation:Picker}}},utils:{getRoute:()=>'/'} };
  const oldFetch=globalThis.fetch;
  globalThis.fetch=async url=>({status:200,url,redirected:false,headers:{get:name=>name==='Content-Length'?String(data.length):null},
    body:new Blob([data]).stream()});
  t.after(()=>{previewTransfers.disconnect(owner);globalThis.fetch=oldFetch;});
  const request=(method,params,id=crypto.randomUUID(),guard=()=>true)=>handleRpcMessage({id,method,params},guard,owner);
  const start=await request('beginImagePreviewTransfer',{image:{source:'data',directory:'assets',src:'assets/a.png'}});
  assert.ok(start.result,JSON.stringify(start.error));const begin=start.result,output=new Uint8Array(data.length);
  for(let index=0;index<begin.chunk_count;index++) {
    const reply=await request('readImagePreviewChunk',{transfer_id:begin.transfer_id,index,offset:index*begin.chunk_bytes,
      length:Math.min(begin.chunk_bytes,data.length-index*begin.chunk_bytes)});
    assert.ok(reply.result,JSON.stringify(reply.error));output.set(Buffer.from(reply.result.data_base64,'base64'),reply.result.offset);
    assert.ok(new TextEncoder().encode(JSON.stringify(reply)).length<=65536);
  }
  assert.deepEqual(output,data);assert.equal(previewTransfers.busy,false);
  const denied=await request('beginImagePreviewTransfer',{src:'assets/a.png'},'denied',()=>false);
  assert.equal(denied.error.code,'ContextChanged');
  game.user.isGM=false;const nongm=await request('beginImagePreviewTransfer',{src:'assets/a.png'});assert.equal(nongm.error.code,'PermissionDenied');
});

test('actual socket disconnect aborts private source; stale socket callbacks cannot release replacement state',async t=>{
  const original={WebSocket:globalThis.WebSocket,fetch:globalThis.fetch};
  class Socket {
    static OPEN=1;static CONNECTING=0;
    constructor(){this.readyState=0;this.events=new Map();this.sent=[];}
    addEventListener(event,fn){this.events.set(event,fn);}
    async emit(event,value={}){await this.events.get(event)?.(value);}
    async open(){this.readyState=1;await this.emit('open');}
    send(value){this.sent.push(JSON.parse(value));}
    close(){this.readyState=3;}
    async call(method,params){await this.emit('message',{data:JSON.stringify({id:crypto.randomUUID(),method,params})});return this.sent.at(-1);}
  }
  globalThis.WebSocket=Socket;
  const options={bridgeUrl:'ws://localhost:8000/ws/foundry',developmentExecution:false,productionAuthentication:false};
  globalThis.game={ready:true,version:'14.369',world:{id:'test'},user:{id:'gm',isGM:true},settings:{get:(_,key)=>options[key]}};
  globalThis.location={origin:'https://foundry.example'};
  class Picker {constructor(){this.sources={data:{}};}static async browse(source,target){return{target,dirs:[],files:['assets/a.png']};}}
  globalThis.foundry={applications:{apps:{FilePicker:{implementation:Picker}}},utils:{getRoute:()=>'/'} };
  const signals=[];
  globalThis.fetch=async(url,options)=>{signals.push(options.signal);return{status:200,url,redirected:false,headers:{get:()=>null},body:new Blob([new Uint8Array(70000)]).stream()};};
  t.after(()=>{disconnectFoundryBridge();Object.assign(globalThis,original);});
  const image={source:'data',directory:'assets',src:'assets/a.png'};
  const old=connectFoundryBridge();await old.open();
  const first=await old.call('beginImagePreviewTransfer',{image});assert.ok(first.result);assert.equal(previewTransfers.busy,true);
  const fresh=reconnectFoundryBridge();assert.ok(signals[0].aborted);assert.equal(previewTransfers.busy,false);
  await fresh.open();const second=await fresh.call('beginImagePreviewTransfer',{image});assert.ok(second.result);
  await old.emit('close',{code:1000});
  await old.call('releaseImagePreviewTransfer',{transfer_id:second.result.transfer_id});assert.equal(previewTransfers.busy,true);
  await fresh.call('releaseImagePreviewTransfer',{transfer_id:second.result.transfer_id});assert.equal(previewTransfers.busy,false);
  assert.ok(signals[1].aborted);assert.notEqual(first.result.transfer_id,second.result.transfer_id);
});
