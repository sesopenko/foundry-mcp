/** External public Foundry mocks only, shared by private-context boundary tests. */
export function contextWorld(input={}){
  const source=input.scene??{id:'scene',name:'Map',folder:null,width:6800,height:9000,padding:.25,shiftX:0,shiftY:0,grid:{size:200},
    levels:[{id:'floor',name:'Floor',sort:0,textures:{default_placement:true},background:{src:'assets/a.png'},foreground:{src:'assets/a.png'}}],
    notes:[{id:'n01',x:1900,y:2500,text:'Note',levels:[],entryId:null,pageId:null}]};
  const collection=list=>({contents:list,invalidDocumentIds:new Set(),get:id=>list.find(d=>d.id===id)});
  const doc=(kind,s,parent=null)=>({id:s.id,uuid:(parent?parent.uuid+'.':'')+kind+'.'+s.id,parent,type:s.type??'Scene',
    get name(){if(s.allowed===false)throw Error('Denied name');return s.name;},
    testUserPermission:()=>s.allowed!==false,
    toObject(original){if(original!==true||s.allowed===false||kind.startsWith('JournalEntry'))throw Error('Denied/invalid source read');const {id,allowed,levels,notes,...v}=s;
      return structuredClone(kind==='Note'?{...v,levels:s.levels??[]}:v);}});
  const scene=doc('Scene',source);
  const journals=collection((input.journals??[]).map(s=>{
    const entry=doc('JournalEntry',s);entry.pages=collection((s.pages??[]).map(p=>doc('JournalEntryPage',p,entry)));return entry;
  }));
  scene.levels=collection((source.levels??[]).map(s=>doc('Level',s,scene)));
  scene.notes=collection((source.notes??[]).map(s=>{
    const d=doc('Note',s,scene);d.includedInLevel=l=>!s.levels?.length||s.levels.includes(l.id);
    Object.defineProperties(d,{entry:{get:()=>journals.get(s.entryId)},page:{get:()=>d.entry?.pages.get(s.pageId)},label:{get:()=>{
      if(d.entry?.testUserPermission()===false||d.page?.testUserPermission()===false)throw Error('Denied label');
      return s.text||d.page?.name||d.entry?.name||'';
    }}});return d;
  }));
  scene.tiles=collection([]);
  scene.getEmbeddedCollection=kind=>({Level:scene.levels,Tile:scene.tiles,Note:scene.notes})[kind];
  scene.getDimensions=()=>source.rectangle??{sceneX:1800,sceneY:2400,sceneWidth:source.width,sceneHeight:source.height};
  globalThis.game={ready:true,version:input.version??'14.369',user:{id:'gm',isGM:true},world:{id:'test'},system:{id:'other'},
    scenes:collection([scene]),folders:collection([])};
  globalThis.location={origin:'http://localhost:30000'};
  const state={source,scene,files:input.files??['assets/a.png'],listings:0,browse_hook:null};
  class Picker{
    constructor(){this.sources=input.sources??{data:{}};}
    static async browse(source,target){state.listings++;if(state.browse_hook)await state.browse_hook();
      return{target,dirs:[],files:state.files};}
  }
  globalThis.foundry={utils:{getRoute:path=>'/'+path},applications:{apps:{FilePicker:{implementation:Picker}}},documents:{Level:{schema:{getField:()=>({clean:()=>({default_placement:true})})}}}};
  globalThis.canvas=new Proxy({},{get(){throw Error('Canvas state must not be read');}});
  return state;
}
