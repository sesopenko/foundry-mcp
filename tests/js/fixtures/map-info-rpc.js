// Actual production RPC dispatch; only external public Foundry documents mocked.
import {readFileSync} from 'node:fs';
import {webcrypto} from 'node:crypto';
import {handleRpcMessage} from '../../../foundry-module/scripts/foundryBridge.js';
globalThis.crypto??=webcrypto;
for(const name of ['log','info','warn','error','debug'])console[name]=()=>{};
const input=JSON.parse(readFileSync(0,'utf8'));
const collection=list=>({contents:list,invalidDocumentIds:new Set(),get:id=>list.find(d=>d.id===id)});
function document(kind,s,parent=null){
  const doc={id:s.id,uuid:(parent?parent.uuid+'.':'')+kind+'.'+s.id,parent,type:s.type??'Scene',
    get name(){if(s.allowed===false)throw Error('Denied name read');return s.name;},
    testUserPermission(){return s.allowed!==false;},
    toObject(){if(s.allowed===false)throw Error('Denied serialization');const {id,allowed,...source}=s;return structuredClone(source);},
    activate(){throw Error('No activation');},view(){throw Error('No view');}};
  return doc;
}
const journals=collection((input.journals??[]).map(s=>{
  const doc=document('JournalEntry',s);doc.pages=collection((s.pages??[]).map(p=>document('JournalEntryPage',p,doc)));return doc;
}));
const scenes=input.scenes.map(s=>{
  const doc=document('Scene',s);
  doc.levels=collection((s.levels??[]).map(l=>document('Level',l,doc)));
  doc.tiles=collection((s.tiles??[]).map(t=>document('Tile',t,doc)));
  doc.notes=collection((s.notes??[]).map(n=>document('Note',n,doc)));
  for(let i=0;i<doc.notes.contents.length;i++){
    const note=doc.notes.contents[i],source=s.notes[i];
    note.includedInLevel=level=>!source.levels?.length||source.levels.includes(level.id);
    Object.defineProperty(note,'entry',{get:()=>journals.get(source.entryId)});
    Object.defineProperty(note,'page',{get:()=>note.entry?.pages.get(source.pageId)});
    Object.defineProperty(note,'label',{get:()=>{
      if(note.entry?.testUserPermission()===false||note.page?.testUserPermission()===false)throw Error('Denied fallback label read');
      return source.text||note.page?.name||note.entry?.name||'';
    }});
  }
  doc.getEmbeddedCollection=kind=>({Level:doc.levels,Tile:doc.tiles,Note:doc.notes})[kind];
  doc.getDimensions=()=>s.scene_rect??{sceneX:1620,sceneY:2160,sceneWidth:5940,sceneHeight:7920};
  return doc;
});
globalThis.game={ready:true,version:'14.369',user:{id:'gm',isGM:true},world:{id:'test'},system:{id:'other'},
  scenes:collection(scenes),folders:collection((input.folders??[]).map(f=>document('Folder',f)))};
globalThis.canvas=new Proxy({},{get(){throw Error('No canvas');}});
process.stdout.write(JSON.stringify(await handleRpcMessage({id:'fixture',method:'getMapInfo',params:input.params})));
