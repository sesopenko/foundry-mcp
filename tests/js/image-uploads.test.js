import test from 'node:test';
import assert from 'node:assert/strict';
import {webcrypto, createHash} from 'node:crypto';
import {File} from 'node:buffer';
import {prepareImageUpload, createImageDirectory, uploadImage} from '../../foundry-module/scripts/imageUploads.js';
import {browseJournalImages} from '../../foundry-module/scripts/journalImages.js';
import {handleRpcMessage} from '../../foundry-module/scripts/foundryBridge.js';

globalThis.crypto ??= webcrypto;
globalThis.File ??= File;
const code = value => error => error.rpcError?.code === value;
const body = Buffer.from('validated-in-python');
function fixture() {
  const state = {dirs: new Set(['','assets']), files: new Map(), uploads: 0, creates: 0, browseHook: null};
  globalThis.game = {ready:true, version:'14.369',world:{id:'test'},user:{id:'gm',isGM:true}};
  class Picker {
    constructor() {this.sources={data:{target:''},public:{target:''}};this.activeSource='data';}
    get canCreateFolder() {return this.activeSource==='data' && !['modules','systems','worlds'].includes(this.sources.data.target) && !state.denied;}
    get canUpload() {return this.canCreateFolder && this.sources.data.target!=='';}
    static async browse(source,target) {
      if(state.browseHook) await state.browseHook();
      if(state.encodedPaths) target=decodeURI(target);
      if(!state.dirs.has(target)) throw Error('Missing private directory');
      const encode=p=>state.encodedPaths?encodeURI(p):p;
      return {target:encode(target), dirs:[...state.dirs].filter(d=>d && d!==target && d.startsWith(target?target+'/':'')).map(encode),files:[...state.files.keys()].filter(f=>f.startsWith(target+'/')).map(encode)};
    }
    static async createDirectory(source,target) {state.creates++;state.dirs.add(state.encodedPaths?decodeURI(target):target);}
    static async upload(source,directory,file) {
      state.uploads++;
      if(state.uploadError) throw Error('Private host error');
      if(state.uploadFalse) return false;
      if(state.encodedPaths) directory=decodeURI(directory);
      state.files.set(directory+'/'+file.name,new Uint8Array(await file.arrayBuffer()));
      return {path:directory+'/'+file.name};
    }
  }
  globalThis.foundry={applications:{apps:{FilePicker:{implementation:Picker}}}};
  globalThis.fetch=async src=>new Response(state.corrupt?Buffer.from('wrong'):state.files.get(state.encodedPaths?decodeURI(src):src),{status:200});
  globalThis.Image=class {
    naturalWidth=16;naturalHeight=12;
    set src(value) {if(value) queueMicrotask(()=>this.onload?.());}
  };
  const request={directory:'assets',filename:'α portrait',overwrite:false,world_id:'test',user_id:'gm',mime_type:'image/png',width:16,height:12,
    size_bytes:body.length,sha256:createHash('sha256').update(body).digest('hex'),content:body.toString('base64')};
  return {state,request};
}

test('User Data root permits folders but not uploads; Core data remains read-only',async()=>{
  const {state}=fixture();
  const root=await browseJournalImages({});
  assert.equal(root.capabilities.can_upload,false);assert.equal(root.capabilities.can_create_directory,true);
  assert.equal(root.entries.find(e=>e.directory==='assets').capabilities.can_upload,true);
  assert.equal((await browseJournalImages({source:'public'})).capabilities.can_create_directory,false);
  state.denied=true;
  assert.equal((await browseJournalImages({directory:'assets'})).capabilities.can_upload,false);
});

test('create one folder with returned navigation and reuse an existing folder',async()=>{
  const {state}=fixture();
  const result=await createImageDirectory({directory:'assets',name:'α portraits'});
  assert.equal(result.status,'created');assert.equal(result.location.directory,'assets/α portraits');
  assert.equal(result.next_call.arguments.directory,result.location.directory);
  assert.equal((await createImageDirectory({directory:'assets',name:'α portraits'})).status,'already_exists');
  assert.equal(state.creates,1);
  await assert.rejects(createImageDirectory({directory:'assets',name:'../escape'}),code('InvalidRequest'));
  await assert.rejects(createImageDirectory({directory:'missing',name:'nested'}),code('BrowseFailed'));
});

test('upload exact bytes, append detected extension, return canonical journal selector',async()=>{
  const {request,state}=fixture();
  const preflight=await prepareImageUpload({directory:'assets'});assert.equal(preflight.world_id,'test');
  const result=await uploadImage(request);
  assert.equal(result.status,'uploaded');assert.equal(result.overwritten,false);
  assert.deepEqual(result.image,{source:'data',directory:'assets',src:'assets/α portrait.png'});
  assert.deepEqual(Buffer.from(state.files.get(result.image.src)),body);
  await assert.rejects(uploadImage(request),code('FileExists'));assert.equal(state.uploads,1);
  const replaced=await uploadImage({...request,overwrite:true});
  assert.equal(replaced.overwritten,true);assert.equal(state.uploads,2);
});

test('failed writes or corrupt stored bytes report unknown outcomes without retry',async()=>{
  const {state,request}=fixture();state.uploadError=true;
  assert.equal((await uploadImage(request)).status,'upload_outcome_unknown');assert.equal(state.uploads,1);
  state.uploadError=false;state.corrupt=true;
  const result=await uploadImage(request);
  assert.equal(result.status,'upload_outcome_unknown');assert.equal(result.error_code,'VerificationFailed');
  assert.equal(state.uploads,2);
});

test('Foundry URI-encoded filenames retain canonical selector and collision protection',async()=>{
  const {state,request}=fixture();state.encodedPaths=true;
  const result=await uploadImage(request);
  assert.equal(result.status,'uploaded');
  assert.equal(result.image.src,'assets/%CE%B1%20portrait.png');
  await assert.rejects(uploadImage(request),code('FileExists'));
  assert.equal(state.uploads,1);
  assert.equal((await uploadImage({...request,overwrite:true})).overwritten,true);
});

test('native upload failure cannot masquerade as successful same-byte overwrite',async()=>{
  const {state,request}=fixture();state.files.set('assets/α portrait.png',body);state.uploadFalse=true;
  assert.equal((await uploadImage({...request,overwrite:true})).status,'upload_outcome_unknown');
});

test('canonical Unicode directories are returned, reused and accepted for uploads',async()=>{
  const {state,request}=fixture();state.encodedPaths=true;
  const child=await createImageDirectory({directory:'assets',name:'α portraits'});
  assert.equal(child.location.directory,'assets/%CE%B1%20portraits');
  assert.equal((await createImageDirectory({directory:'assets',name:'α portraits'})).status,'already_exists');
  assert.equal(state.creates,1);
  const result=await uploadImage({...request,directory:child.location.directory});
  assert.equal(result.status,'uploaded');assert.equal(result.image.src,'assets/%CE%B1%20portraits/%CE%B1%20portrait.png');
});

test('checksum, dimensions, GM and world changes reject before writing',async()=>{
  const {state,request}=fixture();
  await assert.rejects(uploadImage({...request,sha256:'0'.repeat(64)}),code('InvalidRequest'));
  await assert.rejects(uploadImage({...request,width:8193}),code('InvalidRequest'));
  await assert.rejects(uploadImage({...request,world_id:'other'}),code('ContextChanged'));
  game.user.isGM=false;await assert.rejects(uploadImage(request),code('PermissionDenied'));
  game.user.isGM=true;state.browseHook=async()=>{game.world.id='other';};
  await assert.rejects(uploadImage(request),code('ContextChanged'));assert.equal(state.uploads,0);
});

test('socket ownership lost during native browse prevents later upload',async()=>{
  const {state,request}=fixture();let current=true;
  state.browseHook=async()=>{current=false;};
  const result=await handleRpcMessage({id:'upload',method:'uploadImage',params:request},()=>current);
  assert.equal(result.error?.code,'ContextChanged');assert.equal(state.uploads,0);
});

test('concurrent writes are rejected while the native operation is pending',async()=>{
  const {state,request}=fixture();let release;
  state.browseHook=()=>new Promise(resolve=>{release=resolve;});
  const pending=prepareImageUpload({directory:'assets'});
  // Preflight is read-only. Hold a directory mutation separately.
  release();await pending;state.browseHook=null;
  const original=foundry.applications.apps.FilePicker.implementation.createDirectory;
  foundry.applications.apps.FilePicker.implementation.createDirectory=async(...args)=>{await new Promise(resolve=>{release=resolve;});return original(...args);};
  const creating=createImageDirectory({directory:'assets',name:'pending'});
  await new Promise(resolve=>setImmediate(resolve));
  await assert.rejects(uploadImage(request),code('Busy'));release();await creating;
});
