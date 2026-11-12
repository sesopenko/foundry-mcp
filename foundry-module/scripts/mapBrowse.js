/** Core Foundry14 world Scene/Folder navigation; no PF2e, canvas or UI tree.
 * Public contracts: docs/plans/image-viewing/map-browsing.md. Source fields
 * come from documented toObject(true), not private source/prepared internals.
 */
const encoder=new TextEncoder();
const ID=/^[A-Za-z0-9_-]{1,128}$/;
const FOLDER=/^Folder\.[A-Za-z0-9_-]{1,128}$/;
const KEYS=['folder_uuid','name_contains','limit','max_bytes','cursor','caller_key'];

function fail(code,message){const error=new Error(message);error.rpcError={code,type:code,message};throw error;}
function invalid(){fail('InvalidRequest','Use the published browse_maps fields, bounds and exact Folder UUID.');}
function bytes(value){return encoder.encode(JSON.stringify(value)).length;}
function named(name){return{name:Array.from(name).slice(0,256).join(''),name_truncated:Array.from(name).length>256};}
function context(isCurrent){
  if(!isCurrent())fail('ContextChanged','GM connection changed; reconnect and restart browse_maps.');
  if(!globalThis.game?.ready||!game.scenes||!game.folders)fail('NotReady','Wait for the intended world to become ready.');
  if(!Array.isArray(game.scenes.contents)||!Array.isArray(game.folders.contents)||typeof game.folders.get!=='function')
    fail('UnsupportedCapability','Required public world collections are unavailable.');
  if(!(game.scenes.invalidDocumentIds instanceof Set)||!(game.folders.invalidDocumentIds instanceof Set))
    fail('UnsupportedCapability','Public invalid-document availability metadata is unavailable.');
  if(!game.user?.isGM)fail('PermissionDenied','Map browsing requires the connected ready GM.');
  if(!String(game.version).startsWith('14.'))fail('UnsupportedVersion','Map browsing requires matching module/server on Foundry14.');
  if(typeof game.world?.id!=='string'||typeof game.user.id!=='string')fail('NotReady','World and GM identity are unavailable.');
  return[game.world.id,game.user.id];
}
function snapshot(){
  const read=(doc,kind)=>{
    if(typeof doc.testUserPermission!=='function'||typeof doc.toObject!=='function')fail('UnsupportedCapability','Required public document APIs are unavailable.');
    if(typeof doc.id!=='string'||!ID.test(doc.id)||doc.uuid!==`${kind==='folder'?'Folder':'Scene'}.${doc.id}`)
      fail('MapDataUnavailable','Invalid map document identity; repair world data.');
    if(doc.testUserPermission(game.user,'OBSERVER')!==true)return{id:doc.id,uuid:doc.uuid,kind,allowed:false};
    const source=doc.toObject(true);
    const parent=source.folder??null,sort=source.sort??null;
    if(typeof source.name!=='string'||(parent!==null&&(typeof parent!=='string'||!ID.test(parent)))
        ||(sort!==null&&!Number.isSafeInteger(sort)))fail('MapDataUnavailable','Invalid public map metadata; repair world data.');
    if(kind==='folder'&&!['a','m'].includes(source.sorting))fail('MapDataUnavailable','Unsupported folder sorting mode; use alphabetical or manual sorting.');
    return{id:doc.id,uuid:doc.uuid,kind,allowed:true,parent,name:source.name,sort,
      ...(kind==='folder'?{sorting:source.sorting}:{})};
  };
  const folders=game.folders.contents.filter(f=>f.type==='Scene').map(d=>read(d,'folder'));
  const scenes=game.scenes.contents.map(d=>read(d,'map'));
  if(new Set(folders.map(d=>d.id)).size!==folders.length||new Set(scenes.map(d=>d.id)).size!==scenes.length)
    fail('MapDataUnavailable','Duplicate map document identities; repair world data.');
  const invalid=[...game.folders.invalidDocumentIds].map(id=>'Folder.'+id)
    .concat([...game.scenes.invalidDocumentIds].map(id=>'Scene.'+id)).sort();
  return{folders,scenes,invalid};
}
function hierarchy(data){
  const folders=new Map(data.folders.map(f=>[f.id,f]));
  const done=new Set();
  for(const item of data.folders){
    let current=item;const active=new Set();
    while(current?.allowed&&!done.has(current.id)){
      if(active.has(current.id))fail('InvalidHierarchy','Scene-folder containment has a cycle; repair folders in Foundry.');
      active.add(current.id);
      if(current.parent===null)break;
      const parent=folders.get(current.parent);
      if(!parent)fail('InvalidHierarchy','Scene-folder parent is missing or has the wrong type; repair folders in Foundry.');
      current=parent;
    }
    for(const id of active)done.add(id);
  }
  for(const scene of data.scenes)if(scene.allowed&&scene.parent!==null&&!folders.has(scene.parent))
    fail('InvalidHierarchy','Scene parent folder is missing or has the wrong type; repair folders in Foundry.');
  const ancestry=id=>{
    const result=[];
    while(id!==null){
      const folder=folders.get(id);
      if(!folder?.allowed)return null;
      result.unshift({folder_uuid:folder.uuid,...named(folder.name)});
      id=folder.parent;
    }
    return result;
  };
  return{folders,ancestry};
}
async function hash(value){
  const data=encoder.encode(JSON.stringify(value));
  if(globalThis.crypto?.subtle){
    const digest=await crypto.subtle.digest('SHA-256',data);
    return Array.from(new Uint8Array(digest),v=>v.toString(16).padStart(2,'0')).join('');
  }
  // Change markers, not authorization tokens. Permissions are checked per call.
  let a=2166136261,b=5381;
  for(const value of data){a=Math.imul(a^value,16777619)>>>0;b=(Math.imul(b,33)^value)>>>0;}
  return`http-${data.length}-${a.toString(16)}-${b.toString(16)}`;
}
function encodeCursor(scope,revision,offset){return btoa(JSON.stringify({scope,revision,offset}));}
function startAt(cursor,scope,revision,total){
  if(cursor===null)return 0;
  let value;
  try{value=JSON.parse(atob(cursor));}catch{fail('InvalidCursor','Return next_cursor unchanged with the same folder/filter, or restart without cursor.');}
  if(!value||Object.keys(value).sort().join(',')!=='offset,revision,scope'||value.scope!==scope
      ||!Number.isSafeInteger(value.offset)||value.offset<0)
    fail('InvalidCursor','Cursor belongs to different inputs/caller/world; restart browse_maps.');
  if(value.revision!==revision)fail('ContentChanged','Map metadata or permissions changed; discard prior pages and restart without cursor.');
  if(value.offset>total)fail('InvalidCursor','Cursor offset is outside this unchanged stream; restart browse_maps.');
  return value.offset;
}

// Shared core-map primitives; selected-map readers own their narrower snapshots.
export {context as mapContext,hash as mapHash,named as mapNamed,bytes as mapBytes,
  encodeCursor as mapCursor,startAt as mapOffset};

/** Browse one authorized immediate-child stream. Caller key is server-injected. */
export async function browseMaps(params={},isCurrent=()=>true){
  if(!params||typeof params!=='object'||Array.isArray(params)||Object.keys(params).some(k=>!KEYS.includes(k)))invalid();
  const {folder_uuid=null,name_contains='',limit=10,max_bytes=8000,cursor=null,caller_key}=params;
  if((folder_uuid!==null&&(typeof folder_uuid!=='string'||!FOLDER.test(folder_uuid)))||typeof name_contains!=='string'
      ||Array.from(name_contains).length>256||!Number.isInteger(limit)||limit<1||limit>100
      ||!Number.isInteger(max_bytes)||max_bytes<1024||max_bytes>48000
      ||(cursor!==null&&(typeof cursor!=='string'||!cursor.length||cursor.length>4096))
      ||typeof caller_key!=='string'||!/^[0-9a-f]{64}$/.test(caller_key))invalid();
  const owner=context(isCurrent);
  if(folder_uuid!==null){
    const selected=game.folders.get(folder_uuid.slice(7));
    if(!selected)fail('FolderNotFound','Folder is missing; restart browse_maps at root.');
    if(selected.type!=='Scene')fail('InvalidFolder','Choose a Scene folder UUID returned by browse_maps.');
    if(selected.testUserPermission(game.user,'OBSERVER')!==true)fail('PermissionDenied','Selected folder is unavailable; restart at a readable parent.');
  }
  const data=snapshot(),tree=hierarchy(data),selected=folder_uuid===null?null:tree.folders.get(folder_uuid.slice(7));
  if(folder_uuid!==null&&!selected)fail('ContentChanged','Selected folder changed; restart browse_maps at root.');
  const ancestors=tree.ancestry(selected?.parent??null);
  const childrenAncestry=tree.ancestry(selected?.id??null);
  if(ancestors===null||childrenAncestry===null)fail('PermissionDenied','Selected folder ancestry is unavailable; restart at a readable parent.');
  const collator=new Intl.Collator(),locale=collator.resolvedOptions().locale,mode=selected?.sorting??'a';
  const query=[owner,caller_key,folder_uuid,name_contains];
  const scope=await hash(query),revision=await hash([owner,locale,data]);
  if(JSON.stringify(context(isCurrent))!==JSON.stringify(owner)||JSON.stringify(snapshot())!==JSON.stringify(data))
    fail('ContentChanged','World, metadata or permissions changed; restart browse_maps.');
  const immediate=[...data.folders,...data.scenes].filter(d=>d.allowed&&d.parent===(selected?.id??null));
  const unreadable=data.invalid.length>0||data.folders.some(d=>!d.allowed)||data.scenes.some(d=>!d.allowed)
    ||immediate.some(d=>tree.ancestry(d.parent)===null);
  const compare=(a,b)=>(a.kind===b.kind?0:a.kind==='folder'?-1:1)
    ||(mode==='a'?collator.compare(a.name,b.name):(a.sort??0)-(b.sort??0))||(a.uuid<b.uuid?-1:a.uuid>b.uuid?1:0);
  const nodes=immediate.filter(d=>tree.ancestry(d.parent)!==null&&d.name.toLowerCase().includes(name_contains.toLowerCase()))
    .sort(compare).map(d=>({kind:d.kind,...(d.kind==='folder'?{folder_uuid:d.uuid,sorting:d.sorting}:{scene_uuid:d.uuid,image_status:'not_checked'}),
      parent_uuid:folder_uuid,...named(d.name),ancestry:childrenAncestry,sort:d.sort,
      next_call:d.kind==='folder'?{tool:'browse_maps',arguments:{folder_uuid:d.uuid}}:{tool:'get_map_info',arguments:{scene_uuid:d.uuid}}}));
  const offset=startAt(cursor,scope,revision,nodes.length);
  const base={location:{folder_uuid,name:selected?named(selected.name).name:'World Scenes',
    name_truncated:selected?named(selected.name).name_truncated:false,ancestry:ancestors,sorting:mode,locale},
    revision,entries:[],total:nodes.length,complete:offset===nodes.length,next_cursor:offset===nodes.length?null:encodeCursor(scope,revision,offset),
    scope_status:unreadable?'partial':'complete',limitations:[
      'World Scenes only; this stream covers immediate children, not recursive or compendium search.',
      'Image availability is not checked; use get_map_info assets. A file preview is not a composed Scene.',
      ...(unreadable?['Some world Scene/folder metadata is unavailable; complete pages do not establish exhaustive availability.']:[])]};
  if(bytes(base)>max_bytes)fail('ResponseTooLarge','Folder identity exceeds max_bytes; increase to48000 or choose a shallower folder.');
  let result=base,end=offset;
  while(end<nodes.length&&end-offset<limit){
    const next=end+1,complete=next===nodes.length;
    const candidate={...base,entries:[...result.entries,nodes[end]],complete,next_cursor:complete?null:encodeCursor(scope,revision,next)};
    if(bytes(candidate)>max_bytes)break;
    result=candidate;end=next;
  }
  if(end===offset&&offset<nodes.length)fail('ResponseTooLarge','One complete map identity cannot fit; increase max_bytes up to48000.');
  return result;
}
