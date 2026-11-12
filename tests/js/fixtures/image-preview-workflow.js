// Test-only external Foundry/HTTP environment. Production bridge/handlers run
// unchanged; no production/game documents, network or existing assets are used.
import {webcrypto} from 'node:crypto';
import {createInterface} from 'node:readline';
import {pathToFileURL} from 'node:url';
import {handleRpcMessage} from '../../../foundry-module/scripts/foundryBridge.js';
import {previewTransfers} from '../../../foundry-module/scripts/imagePreviewTransfer.js';

globalThis.crypto ??= webcrypto;
const collection = contents => ({contents,size:contents.length,get:id=>contents.find(d=>d.id===id)});

export function createWorkflowFixture(config) {
  const owner = {},state = {fetches:0,chunks:0,finished:[],fault:null,denied:false};
  const image = {...config.image},prefix = config.prefix ?? '';
  const batches=new Map();let chunkCount=0;
  let data = Uint8Array.from(Buffer.from(config.data_base64,'base64'));
  if(!data.length||data.length>134217728)throw Error('Fixture source bounds');
  const entry = {id:'fixture',uuid:'JournalEntry.fixture',name:'Fixture',folder:null,sort:0,categories:collection([])};
  const page = {id:'page',uuid:'JournalEntry.fixture.JournalEntryPage.page',name:'Fixture page',parent:entry,
    type:'text',text:{content:config.html,format:1},sort:0,title:{level:1,show:true},toc:{}};
  entry.pages=collection([page]);
  globalThis.game={ready:true,version:'14.369',world:{id:'test'},user:{id:'gm',isGM:true},
    folders:collection([]),journal:collection([entry])};
  globalThis.location={origin:'https://foundry.example',href:'https://foundry.example'+prefix+'/game'};
  class Picker {
    constructor(){this.sources={data:{},public:{}};}
    static async browse(source,directory) {
      if(state.denied)throw Error('Denied private fixture');
      return {target:directory,dirs:[],files:source===image.source&&directory===image.directory?[image.src]:[]};
    }
  }
  globalThis.foundry={applications:{apps:{FilePicker:{implementation:Picker}}},utils:{getRoute:path=>prefix+'/'+path}};
  const previousFetch=globalThis.fetch;
  globalThis.fetch=async (url,options)=>{
    if(options.credentials!=='same-origin')throw Error('Wrong credential policy');
    if(url!==new URL(prefix+'/'+image.src,location.origin).href)throw Error('Wrong canonical fixture URL');
    state.fetches++;
    const snapshot=data.slice();
    return {status:200,url,redirected:false,headers:{get:name=>name==='Content-Length'?String(snapshot.length):null},
      body:new Blob([snapshot]).stream()};
  };
  return {
    state,image,page,
    close(){previewTransfers.disconnect(owner);globalThis.fetch=previousFetch;},
    async rpc(frame){
      if(frame.method==='fixture.stats')return{id:frame.id,result:{fetches:state.fetches,chunks:state.chunks,
        finished:state.finished,busy:previewTransfers.busy}};
      if(frame.method==='fixture.change'){
        const changes=frame.params;
        if(changes.data_base64)data=Uint8Array.from(Buffer.from(changes.data_base64,'base64'));
        if(Object.hasOwn(changes,'fault'))state.fault=changes.fault;
        if(Object.hasOwn(changes,'denied'))state.denied=changes.denied;
        if(changes.world)game.world.id=changes.world;
        if(Object.hasOwn(changes,'isGM'))game.user.isGM=changes.isGM;
        if(changes.disconnect)previewTransfers.disconnect(owner);
        return{id:frame.id,result:{changed:true}};
      }
      if(frame.method==='readImagePreviewChunk'){
        if(state.fault==='missing')return null;
        // Complete real handlers in deliberately non-index order.
        await new Promise(resolve=>setTimeout(resolve,(3-frame.params.index%3)*3));
      }
      const reply=await handleRpcMessage(frame,()=>true,owner);
      if(frame.method==='beginImagePreviewTransfer'&&reply.result)chunkCount=reply.result.chunk_count;
      if(frame.method==='readImagePreviewChunk'&&reply.result){
        state.chunks++;
        if(state.fault==='short')reply.result.data_base64=Buffer.from(reply.result.data_base64,'base64').subarray(1).toString('base64');
        if(config.reverse_replies){
          // Model a network that releases each admitted window in reverse
          // index order. No scheduler-timing assumption establishes the oracle.
          return await new Promise(resolve=>{
            const window=Math.floor(frame.params.index/16),batch=batches.get(window)??[];
            batch.push({reply,resolve});batches.set(window,batch);
            if(batch.length===Math.min(16,chunkCount-window*16)){
              batches.delete(window);
              for(const item of batch.sort((a,b)=>b.reply.result.index-a.reply.result.index)){
                state.finished.push(item.reply.result.index);item.resolve(item.reply);
              }
            }
          });
        }
        state.finished.push(reply.result.index);
      }
      return reply;
    },
  };
}

if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
  // Keep production diagnostic console output separate from the private wire.
  for(const name of ['log','info','warn','error'])console[name]=()=>{};
  let fixture;
  const input=createInterface({input:process.stdin,crlfDelay:Infinity});
  input.on('line',async line=>{
    const frame=JSON.parse(line);
    let reply;
    try{
      if(frame.method==='fixture.init'){
        fixture=createWorkflowFixture(frame.params);
        reply={id:frame.id,result:{ready:true}};
      }else reply=await fixture.rpc(frame);
    }catch{reply={id:frame.id,error:{code:'FixtureFailure',message:'Test fixture failed'}};}
    if(reply)process.stdout.write(JSON.stringify(reply)+'\n');
  });
  input.on('close',()=>{fixture?.close();process.exit(0);});
}
