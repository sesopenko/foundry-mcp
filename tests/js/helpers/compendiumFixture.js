/** Read-only compendium mocks: every mutation traps immediately. */
export function fixture() {
  const deny=()=>{throw Error('MUTATION_FORBIDDEN');};
  const collection=values=>({contents:values,size:values.length,get:id=>values.find(v=>v.id===id),values:()=>values.values()});
  let loads=0,indexes=0;
  const pack={collection:'test.rules',title:'Rules',documentName:'JournalEntry',folder:null,testUserPermission:()=>true,
    create:deny,update:deny,delete:deny,configure:deny,importDocument:deny,getUuid:id=>`Compendium.test.rules.JournalEntry.${id}`};
  const entries=Array.from({length:12},(_,i)=>{
    const entry={id:`j${String(i).padStart(2,'0')}`,name:'Duplicate',documentName:'JournalEntry',folder:null,sort:0,compendium:pack,testUserPermission:()=>true};
    entry.uuid=pack.getUuid(entry.id);
    entry.pages=collection(Array.from({length:3},(_,n)=>({id:`p${n}`,name:n===0?'DCs by Level':'DC Adjustments',sort:n,type:'text',title:{level:1,show:true},toc:{},parent:entry,
      uuid:`${entry.uuid}.JournalEntryPage.p${n}`,testUserPermission:()=>true,text:{format:1,content:'<table><tr><th>Level</th><th>DC</th></tr><tr><td>5</td><td>20</td></tr></table>😀 @UUID[.p1]{Adjustments}'.repeat(30)}})));
    entry.categories=collection([]);return entry;
  });
  pack.getIndex=async()=>{indexes++;return collection(entries.map(e=>({_id:e.id,name:e.name})));};
  pack.getDocument=async id=>{loads++;return entries.find(e=>e.id===id);};
  globalThis.game={ready:true,version:'14.369',user:{isGM:true},folders:collection([]),journal:collection([]),packs:new Map([[pack.collection,pack]])};
  globalThis.foundry={utils:{fromUuidSync:()=>null,fromUuid:async(uuid,{relative}={})=>uuid==='.p1'?relative.parent.pages.get('p1'):null}};
  globalThis.DOMParser=class{parseFromString(html){return {body:{nodeType:1,tagName:'BODY',childNodes:[{nodeType:3,textContent:html.replace(/<[^>]+>/g,' ')}]}};}};
  return {pack,entries,counts:()=>({loads,indexes})};
}
