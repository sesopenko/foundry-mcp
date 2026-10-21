/**
 * World discovery using public core14.369 game.actors/game.folders collections,
 * Actor.folder, FolderData.folder via toObject(true), UUID and permissions.
 * https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.FolderData.html
 * https://foundryvtt.com/api/v14/classes/foundry.Game.html
 * No sidebar trees, prepared sheet data or document writes are used.
 */
import { fail, validateParams, integer, selector, digest, paginate } from './actorReadUtils.js';
import { ACTOR_TYPES, ready, runtime, named, permitted, requirePermission, documentIdentity } from './actorDocuments.js';

const compare = (a,b) => a<b?-1:a>b?1:0;
const ordered = (a,b) => compare((a.order_name??a.name).toLowerCase(),(b.order_name??b.name).toLowerCase())||compare(a.uuid,b.uuid);

function request(params, keys) {
  validateParams(params,keys);
  integer(params.limit,50,1,100,'limit'); integer(params.max_bytes,48000,8000,48000,'max_bytes');
  ready();
  if (!game.folders) fail('NotReady','World folders are not ready.','Wait for the existing world to finish loading.');
}

/** FolderData.folder is a source ID, independent of UI-prepared hierarchy. */
function directory(folderUuid) {
  const folders=new Map();
  for (const folder of game.folders.values()) {
    if (folder.type!=='Actor') continue;
    const source=folder.toObject(true);
    folders.set(folder.id,{document:folder,id:folder.id,uuid:folder.uuid,...named(folder),order_name:String(folder.name),parent_id:source.folder??null,readable:permitted(folder)});
  }
  let selected=null;
  if (folderUuid!==undefined && folderUuid!==null) {
    selector(folderUuid,'folder_uuid');
    if (!/^Folder\.[^.]+$/.test(folderUuid)) fail('InvalidRequest','folder_uuid must be a canonical world Folder UUID.');
    selected=[...folders.values()].find(folder=>folder.uuid===folderUuid);
    if (!selected) fail('DocumentNotFound','Selected Actor folder does not exist.','Refresh get_actor_tree and use its folder UUID.');
    requirePermission(selected.document);
  }
  const chain = id => {
    const result=[]; const seen=new Set();
    while (id!==null) {
      if (seen.has(id)) fail('ReadFailed','Actor folder containment contains a cycle.','Repair the folder hierarchy in Foundry before retrying.');
      seen.add(id);
      const entry=folders.get(id);
      if (!entry) return {path:result,readable:false};
      result.unshift(entry); id=entry.parent_id;
    }
    return {path:result,readable:result.every(entry=>entry.readable)};
  };
  // Detect disconnected cycles too, rather than silently omit their contents.
  for (const folder of folders.values()) chain(folder.id);
  return {folders,selected,chain};
}

function actorNode(actor,path,depth) {
  return {kind:'actor',identity:documentIdentity(actor,null,null),parent_uuid:path.at(-1)?.uuid??null,depth,
    folder_path:path.map(({id,uuid,name,name_truncated})=>({id,uuid,name,name_truncated})),
    next_call:{tool:'read_actor',arguments:{actor_uuid:actor.uuid}}};
}

async function page(build,params,scope,tree=false) {
  const snapshot=build(); const revision=await digest(snapshot);
  const base={contract_version:1,runtime:snapshot.runtime,revision,scopes:snapshot.scopes,limitations:snapshot.limitations,
    ...(tree?{tree_complete:snapshot.tree_complete}: {})};
  const result=await paginate(snapshot.nodes,base,params,scope);
  if (await digest(build())!==revision) fail('ContentChanged','World Actor discovery changed during the read.','Discard accumulated pages and restart without cursor.');
  const {records,...rest}=result;
  if (tree) rest.tree_complete=snapshot.tree_complete&&result.pagination.complete;
  // Replacing records with nodes saves two bytes, preserving the checked budget.
  return {...rest,nodes:records};
}

/**
 * PF2e-specific discovery admits character/npc/familiar on core14.369/PF2e8.6.1.
 * Subtype is a filter, never a narrative role or derived statistic. Folder and
 * Actor identity are core source relationships; no PF2e calculations occur.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/static/template.json
 */
export async function getActorTree(params={}) {
  request(params,['folder_uuid','depth','limit','max_bytes','cursor']);
  const depth=integer(params.depth,2,1,5,'depth');
  const build=()=>{
    ready();const {folders,selected,chain}=directory(params.folder_uuid);const nodes=[];let incomplete=false;let collapsed=false;
    const actors=[...game.actors.values()].filter(actor=>ACTOR_TYPES.includes(actor.type));
    if (!selected && ([...folders.values()].some(folder=>!chain(folder.id).readable)
        || actors.some(actor=>!chain(actor.folder?.id??null).readable))) incomplete=true;
    const children = (parentId,level) => {
      const childFolders=[...folders.values()].filter(folder=>folder.parent_id===parentId).sort(ordered);
      for (const folder of childFolders) {
        if (!chain(folder.id).readable) {incomplete=true;continue;}
        const hasChildren=[...folders.values()].some(child=>child.parent_id===folder.id)
          ||actors.some(actor=>actor.folder?.id===folder.id);
        const limited=level>=depth&&hasChildren;
        nodes.push({kind:'folder',id:folder.id,uuid:folder.uuid,name:folder.name,name_truncated:folder.name_truncated,
          parent_uuid:parentId===null?null:folders.get(parentId).uuid,depth:level,children_complete:!limited,expand:limited?{folder_uuid:folder.uuid}:null});
        if (limited) collapsed=true;else children(folder.id,level+1);
      }
      const direct=actors.filter(actor=>(actor.folder?.id??null)===parentId).sort(ordered);
      for (const actor of direct) {
        const ancestry=chain(actor.folder?.id??null);
        if (!permitted(actor)||!ancestry.readable) {incomplete=true;continue;}
        nodes.push(actorNode(actor,ancestry.path,level));
      }
    };
    children(selected?.id??null,1);
    return {runtime:runtime(),nodes,tree_complete:!collapsed&&!incomplete,
      scopes:[{id:selected?.uuid??'world',status:incomplete?'incomplete':'searched',reason:incomplete?'Some documents or folder ancestry are unreadable.':null}],limitations:[]};
  };
  return page(build,params,{tool:'get_actor_tree',folder_uuid:params.folder_uuid??null,depth},true);
}

/**
 * PF2e-specific character/npc/familiar name search; no biography, role inference
 * or effective statistics. Schema/version boundary matches getActorTree above.
 */
export async function searchActors(params={}) {
  request(params,['query','types','folder_uuid','recursive','limit','max_bytes','cursor']);
  if (typeof params.query!=='string'||!params.query.trim()||[...params.query.trim()].length>200) fail('InvalidRequest','query must contain 1–200 characters after trim.');
  const query=params.query.trim().toLowerCase();const types=params.types??ACTOR_TYPES;
  if (!Array.isArray(types)||!types.length||types.length>3||new Set(types).size!==types.length||types.some(type=>!ACTOR_TYPES.includes(type))) fail('InvalidRequest','types must be a unique nonempty list of in-scope Actor types.');
  const recursive=params.recursive===undefined?true:params.recursive;
  if (typeof recursive!=='boolean') fail('InvalidRequest','recursive must be a boolean.');
  const build=()=>{
    ready();const {selected,chain}=directory(params.folder_uuid);const nodes=[];let incomplete=false;
    for (const actor of [...game.actors.values()].sort(ordered)) {
      if (!types.includes(actor.type)) continue;
      const ancestry=chain(actor.folder?.id??null);
      if (selected && !(recursive?ancestry.path.some(folder=>folder.id===selected.id):(actor.folder?.id===selected.id))) continue;
      if (!permitted(actor)||!ancestry.readable) {incomplete=true;continue;}
      if (!String(actor.name).toLowerCase().includes(query)) continue;
      nodes.push(actorNode(actor,ancestry.path,ancestry.path.length));
    }
    return {runtime:runtime(),nodes,scopes:[{id:selected?.uuid??'world',status:incomplete?'incomplete':'searched',reason:incomplete?'Some documents or folder ancestry are unreadable.':null}],
      limitations:['Empty results establish only literal name absence in the completed selected scope.']};
  };
  return page(build,params,{tool:'search_actors',query,types,folder_uuid:params.folder_uuid??null,recursive});
}
