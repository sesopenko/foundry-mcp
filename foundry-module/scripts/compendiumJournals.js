/** Read-only core14 compendium navigation. Public contracts:
 * https://foundryvtt.com/api/v14/classes/foundry.documents.collections.CompendiumCollection.html
 * https://foundryvtt.com/api/v14/classes/foundry.documents.JournalEntry.html
 * https://foundryvtt.com/api/v14/classes/foundry.documents.JournalEntryPage.html
 * Only getIndex/getDocument load data; no import, mutation or server cache.
 */
import {fail, validateParams, integer, selector, digest, paginate} from './actorReadUtils.js';
import {permitted} from './actorDocuments.js';
import {journalContents, journalPage, searchableText, normalizeSearchText, referenceOrigin, resolvePageReference} from './journals.js';

const bytes=value=>new TextEncoder().encode(JSON.stringify(value)).length;
const clip=value=>[...String(value??'')].slice(0,256).join('');
const order=(a,b)=>String(a._id??a.id).localeCompare(String(b._id??b.id));
const limitations=['Only the selected pack/entry is searched; literal matches are not semantic evidence.',
  'Entry loading includes all its embedded pages; Foundry offers no per-page network load bound.',
  'Search continuations bind the index and current batch, not previously exhausted batches. Restart for a new full scan after edits.',
  'Internal pack folders are not represented. No Python cache; Foundry may cache documents.'];

function ready() {
  if(!game?.ready||!game.packs)fail('NotReady','Wait for the existing Foundry world.');
  if(!game.user?.isGM)fail('GMRequired','Connect a GM browser.');
  if(!String(game.version).startsWith('14.'))fail('UnsupportedVersion','Compendium journals require Foundry14.');
}
function bounds(params,keys) {
  validateParams(params,keys);ready();
  integer(params.limit,10,1,100,'limit');integer(params.max_bytes,8000,8000,48000,'max_bytes');
}
function packFor(id,type='JournalEntry') {
  selector(id,'pack_id');const pack=game.packs.get(id);
  if(!pack)fail('PackNotFound','Relist packs with list_compendiums.');
  if(!permitted(pack))fail('PermissionDenied','Pack OBSERVER access is required.');
  if(pack.documentName!==type)fail('UnsupportedDocument','Select a JournalEntry pack from list_compendiums.');
  return pack;
}
const packIdentity=pack=>({id:pack.collection,title:clip(pack.title),title_truncated:[...String(pack.title)].length>256,document_type:pack.documentName});
function recheck(pack,entry=null,page=null) {
  ready();
  if(game.packs.get(pack.collection)!==pack||!permitted(pack)||pack.documentName!=='JournalEntry')fail('ContentChanged','Pack identity/access changed; restart navigation.');
  if(entry&&(!permitted(entry)||entry.compendium!==pack))fail('PermissionDenied','Entry is no longer readable in this pack.');
  if(page&&(!permitted(page)||entry.pages.get(page.id)!==page))fail('PermissionDenied','Page is no longer readable in this entry.');
}
async function load(pack,id) {
  selector(id,'journal_id');const entry=await pack.getDocument(id);recheck(pack);
  if(!entry)fail('JournalNotFound','Refresh search_compendium_journals.');
  recheck(pack,entry);
  if(entry.id!==id||entry.documentName!=='JournalEntry')fail('UnsupportedDocument','Pack returned a different document.');
  return entry;
}
function query(value) {
  if(typeof value!=='string'||!value.trim()||value.length>200)fail('InvalidRequest','query requires 1–200 nonblank characters.');
  return value.trim().toLowerCase();
}

/** Discover named pack capabilities without indexes or documents. Actor/Item
 * follow-ups are PF2e-specific existing readers; journals are system-neutral.
 */
export async function listCompendiums(params={}) {
  bounds(params,['document_type','query','limit','max_bytes','cursor']);
  const type=params.document_type??null,q=params.query==null?'':query(params.query);
  if(type!==null&&!['Actor','Item','JournalEntry'].includes(type))fail('InvalidRequest','document_type must be Actor, Item or JournalEntry.');
  const nodes=[];let denied=0;
  for(const pack of [...game.packs.values()].sort((a,b)=>a.collection.localeCompare(b.collection))) {
    if(!['Actor','Item','JournalEntry'].includes(pack.documentName)||(type&&type!==pack.documentName))continue;
    if(!permitted(pack)){denied++;continue;}
    if(q&&!`${pack.title}\n${pack.collection}`.toLowerCase().includes(q))continue;
    nodes.push({...packIdentity(pack),searchable_fields:pack.documentName==='JournalEntry'?['entry_name','page_name','text']:['name'],
      next_tool:pack.documentName==='JournalEntry'?'search_compendium_journals':'search_compendium_actors',
      folder_id:pack.folder?.id??null,folder_name:pack.folder?clip(pack.folder.name):null});
  }
  const revision=await digest(nodes);
  const result=await paginate(nodes,{foundry_version:game.version,revision,denied_packs:denied},params,{tool:'list_compendiums',type,q});
  return {foundry_version:result.foundry_version,revision,nodes:result.records,pagination:result.pagination,denied_packs:denied};
}

/** Bounded selected-pack scans. Index names need no entry loads; page-title or
 * text scans load at most max_entries complete entries per call (including on
 * continuation). No content from denied pages is inspected or named.
 */
export async function searchCompendiumJournals(params={}) {
  bounds(params,['pack_id','journal_id','query','field','max_entries','limit','max_bytes','cursor','select']);
  const pack=packFor(params.pack_id),q=query(params.query),field=params.field??'page_name';
  if(!['entry_name','page_name','text'].includes(field))fail('InvalidRequest','field must be entry_name, page_name or text.');
  const count=integer(params.max_entries,10,1,10,'max_entries'),limit=integer(params.limit,10,1,100,'limit'),budget=params.max_bytes??8000;
  const select=params.select??{};validateParams(select,['excerpts']);
  if(select.excerpts!==undefined&&typeof select.excerpts!=='boolean')fail('InvalidRequest','select.excerpts must be boolean.');
  const index=await pack.getIndex({fields:['name']});recheck(pack);
  const all=[...index.values()].sort(order);
  if(all.some(e=>typeof e._id!=='string'||typeof e.name!=='string'))fail('InvalidIndex','Index lacks entry IDs/names; inspect pack.');
  const entries=params.journal_id==null?all:all.filter(e=>e._id===params.journal_id);
  if(params.journal_id!=null&&!entries.length)fail('JournalNotFound','Select journal_id from this pack search.');
  const indexRevision=await digest([packIdentity(pack),entries.map(e=>[e._id,e.name])]);
  const binding=await digest({pack_id:pack.collection,journal_id:params.journal_id??null,q,field,count,limit,budget,select});
  let c={entry:0,match:0,revision:null};
  if(params.cursor!=null) {
    try {if(typeof params.cursor!=='string'||params.cursor.length>4096)throw Error();c=JSON.parse(atob(params.cursor));}
    catch{fail('InvalidCursor','Use next_cursor unchanged.');}
    if(c.binding!==binding)fail('CursorMismatch','Restore all original inputs or restart without cursor.');
    if(c.indexRevision!==indexRevision)fail('ContentChanged','Pack index changed; discard prior results and restart.');
    if(!Number.isInteger(c.entry)||c.entry<0||c.entry>entries.length||!Number.isInteger(c.match)||c.match<0)fail('InvalidCursor','Invalid scan position.');
  }
  const window=field==='entry_name'?entries:entries.slice(c.entry,c.entry+count),matches=[],snapshot=[],failures=[],loadedEntries=[];
  const entrySnapshot=entry=>[entry.id,entry.name,entry.pages.contents.map(page=>permitted(page)
    ?[page.id,true,page.name,page.type,page.sort,...(field==='text'?[page.text?.content,page.text?.markdown]:[])]:[page.id,false])];
  let pages=0,unsupported=0,loaded=0;
  for(const row of window) {
    if(field==='entry_name') {
      if(row.name.toLowerCase().includes(q))matches.push({journal_id:row._id,journal_uuid:pack.getUuid(row._id),journal_name:clip(row.name),journal_name_truncated:[...row.name].length>256,page_id:null,page_uuid:null,page_name:null,page_name_truncated:false,matched_field:field});
      continue;
    }
    let entry;
    try {entry=await load(pack,row._id);loaded++;}
    catch(error){failures.push({journal_id:row._id,status:error.rpcError?.type??'ReadFailed'});continue;}
    if(entry.pages.size>10000)fail('WorkLimit','Entry exceeds 10000 pages; choose another entry.');
    loadedEntries.push(entry);
    for(const page of [...entry.pages.contents].sort((a,b)=>(a.sort??0)-(b.sort??0)||order(a,b))) {
      if(!permitted(page)){if(!failures.some(f=>f.journal_id===row._id))failures.push({journal_id:row._id,status:'PermissionDenied'});continue;}
      if(page.type!=='text'){unsupported++;continue;}pages++;
      const value=field==='page_name'?page.name:typeof page.text.content==='string'?searchableText(page.text.content):normalizeSearchText(page.text.markdown??'');
      const at=value.toLowerCase().indexOf(q);
      if(at<0)continue;
      matches.push({journal_id:entry.id,journal_uuid:entry.uuid,journal_name:clip(entry.name),journal_name_truncated:[...entry.name].length>256,page_id:page.id,page_uuid:page.uuid,page_name:clip(page.name),page_name_truncated:[...page.name].length>256,matched_field:field,
        ...(select.excerpts?{excerpt:value.slice(Math.max(0,at-80),at+q.length+160),excerpt_derived:true}:{})});
    }
    snapshot.push(entrySnapshot(entry));recheck(pack,entry);
  }
  const revision=await digest([indexRevision,snapshot,failures]);
  if(c.revision&&c.revision!==revision)fail('ContentChanged','Current scan batch changed; restart without cursor.');
  if(c.match>matches.length)fail('InvalidCursor','Invalid match position.');
  const nextEntry=field==='entry_name'?entries.length:c.entry+window.length;
  const token=(entry,match,rev)=>btoa(JSON.stringify({binding,indexRevision,entry,match,revision:rev}));
  const make=end=>({foundry_version:game.version,pack:packIdentity(pack),revision,matches:matches.slice(c.match,end),
    searched_field:field,scanned_entries:field==='entry_name'?entries.length:loaded,scanned_text_pages:pages,unsupported_pages:unsupported,failures,
    unsearched_entries:entries.length-nextEntry,batch_match_count:matches.length,
    complete:end===matches.length&&nextEntry===entries.length,
    coverage_complete:end===matches.length&&nextEntry===entries.length&&!failures.length&&!unsupported,
    next_cursor:end<matches.length?token(c.entry,end,revision):nextEntry<entries.length?token(nextEntry,0,null):null,
    limitations});
  let end=c.match,result=make(end);
  while(end<matches.length&&end-c.match<limit){const candidate=make(end+1);if(bytes(candidate)>budget)break;result=candidate;end++;}
  if(bytes(result)>budget||(end===c.match&&end<matches.length))fail('ResponseTooLarge','One result exceeds max_bytes; raise budget up to 48000.');
  for(const entry of loadedEntries)recheck(pack,entry);
  if(JSON.stringify(loadedEntries.map(entrySnapshot))!==JSON.stringify(snapshot))fail('ContentChanged','Scanned entries changed during loading; restart without cursor.');
  for(const entry of loadedEntries)recheck(pack,entry);
  recheck(pack);return result;
}

/** Separate pack selector interface reusing the exact world-journal processor. */
export async function getCompendiumJournalContents(params={}) {
  bounds(params,['pack_id','journal_id','page_id','categories_only','limit','max_bytes','cursor','select']);
  const pack=packFor(params.pack_id),entry=await load(pack,params.journal_id);
  if(entry.pages.contents.some(p=>!permitted(p)))fail('PermissionDenied','Not all pages are readable; inspect entry permissions.');
  const result=await journalContents(entry,{...params,select:params.select??{},limit:params.limit??10,max_bytes:params.max_bytes??8000},{pack:packIdentity(pack)});
  recheck(pack,entry);
  if(entry.pages.contents.some(p=>!permitted(p)))fail('PermissionDenied','Page access changed during navigation; restart.');
  return {...result,pack:packIdentity(pack)};
}

/** Exact stored source only, with public pack/document/page permission checks. */
export async function readCompendiumJournalPage(params={}) {
  bounds(params,['pack_id','page_uuid','source','max_chars','max_bytes','cursor','select']);
  const pack=packFor(params.pack_id);
  selector(params.page_uuid,'page_uuid');const prefix=`Compendium.${pack.collection}.JournalEntry.`;
  if(!params.page_uuid.startsWith(prefix))fail('InvalidRequest','Use page_uuid returned for the selected pack, without anchor.');
  const parts=params.page_uuid.slice(prefix.length).split('.');
  if(parts.length!==3||parts[1]!=='JournalEntryPage'||parts.some(p=>!p||p.includes('#')))fail('InvalidRequest','Use a complete compendium page UUID without anchor.');
  const entry=await load(pack,parts[0]),page=entry.pages.get(parts[2]);
  if(!page)fail('PageNotFound','Refresh get_compendium_journal_contents.');recheck(pack,entry,page);
  const result=await journalPage(entry,page,{...params,max_chars:params.max_chars??2000,max_bytes:params.max_bytes??8000,select:params.select??{}},{pack:packIdentity(pack)},
    ref=>({...ref,resolve_next_call:ref.target_truncated?null:{tool:'resolve_compendium_journal_reference',arguments:{pack_id:pack.collection,page_uuid:page.uuid,target:ref.target,source:params.source??'html'}}}));
  recheck(pack,entry,page);return {...result,pack:packIdentity(pack)};
}

/** Lazy public fromUuid resolution relative to the selected source page.
 * PF2e-specific Actor/Item admission delegates existing supported readers;
 * JournalEntry/Page destinations use the separate world/pack journal readers.
 */
export async function resolveCompendiumJournalReference(params={}) {
  validateParams(params,['pack_id','page_uuid','target','source']);ready();
  // Validate the origin through the exact reader's selector and permission path.
  await readCompendiumJournalPage({pack_id:params.pack_id,page_uuid:params.page_uuid,max_chars:1});
  const pack=packFor(params.pack_id),prefix=`Compendium.${pack.collection}.JournalEntry.`;
  const parts=params.page_uuid.slice(prefix.length).split('.'),entry=await load(pack,parts[0]),page=entry.pages.get(parts[2]);
  recheck(pack,entry,page);
  const source=params.source??'html',target=selector(params.target,'target');
  if(!['html','markdown'].includes(source))fail('InvalidRequest','source must be html or markdown.');
  const origin=(uuid,s,t)=>{recheck(pack,entry,page);return referenceOrigin(uuid,s,t,{entry,page});};
  origin(page.uuid,source,target);
  const [uuid,...anchor]=target.split('#');let doc;
  try{doc=await foundry.utils.fromUuid(uuid,{relative:page});}catch{/* Explicit unverified status comes from shared resolver. */}
  origin(page.uuid,source,target);
  if(['JournalEntry','JournalEntryPage'].includes(doc?.documentName)) {
    const destination=doc.documentName==='JournalEntryPage'?doc.parent:doc,destPack=destination.compendium??null;
    const base={foundry_version:game.version,page_uuid:page.uuid,source,target,anchor:anchor.join('#')||null,identity:null,next_call:null};
    if(!permitted(doc)||!permitted(destination)||(destPack&&!permitted(destPack)))return {...base,status:'denied'};
    const args=doc.documentName==='JournalEntryPage'?{page_uuid:doc.uuid}:{journal_id:doc.id};
    const tool=doc.documentName==='JournalEntryPage'?'read_journal_page':'get_journal_contents';
    return {...base,status:'resolved',identity:{document_name:doc.documentName,uuid:doc.uuid,name:clip(doc.name),pack:destPack?packIdentity(destPack):null},
      next_call:{tool:destPack?(doc.documentName==='JournalEntryPage'?'read_compendium_journal_page':'get_compendium_journal_contents'):tool,arguments:{...args,...(destPack?{pack_id:destPack.collection}:{})}}};
  }
  return resolvePageReference({page_uuid:page.uuid,target,source},origin);
}
