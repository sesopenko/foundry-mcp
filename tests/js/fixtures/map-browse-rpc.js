// One-shot synthetic external world for Python's actual MCP/JS boundary tests.
import {readFileSync} from 'node:fs';
import {webcrypto} from 'node:crypto';
import {handleRpcMessage} from '../../../foundry-module/scripts/foundryBridge.js';
globalThis.crypto??=webcrypto;
for(const name of ['log','info','warn','debug','error'])console[name]=()=>{};
const input=JSON.parse(readFileSync(0,'utf8'));
const document=(kind,data)=>({id:data.id,uuid:`${kind}.${data.id}`,type:data.type??'Scene',
  testUserPermission(){return data.allowed!==false;},
  toObject(){if(data.allowed===false)throw Error('Denied source read');return{name:data.name,folder:data.folder??null,
    sort:data.sort??0,...(kind==='Folder'?{sorting:data.sorting??'a'}:{})};},
  view(){throw Error('No activation');},activate(){throw Error('No activation');}});
const collection=docs=>({contents:docs,invalidDocumentIds:new Set(),get:id=>docs.find(d=>d.id===id)});
globalThis.game={ready:true,version:'14.369',user:{id:'gm',isGM:true},world:{id:'test'},system:{id:'dnd5e'},
  folders:collection(input.folders.map(d=>document('Folder',d))),scenes:collection(input.scenes.map(d=>document('Scene',d)))};
globalThis.canvas=new Proxy({},{get(){throw Error('No canvas reads');}});
const result=await handleRpcMessage({id:'fixture',method:'browseMaps',params:input.params});
process.stdout.write(JSON.stringify(result));
