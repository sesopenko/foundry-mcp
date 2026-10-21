/**
 * Scoped, read-only compendium discovery using public core14.369 APIs:
 * game.packs, collection/documentName/title/visible, testUserPermission,
 * getIndex({fields}) and getUuid(id). Selected full reads use the existing
 * actorDocuments async resolver, never bulk loading/importing documents here.
 * https://foundryvtt.com/api/v14/classes/foundry.documents.collections.CompendiumCollection.html
 */
import { fail, validateParams, integer, digest, paginate } from './actorReadUtils.js';
import { ACTOR_TYPES, ITEM_TYPES, ready, runtime, permitted, named } from './actorDocuments.js';

const compare=(a,b)=>a<b?-1:a>b?1:0;
const FLAT='Pack directory hierarchy is not verified; folder context is explicitly null.';

function inputs(params,keys) {
  validateParams(params,keys);integer(params.limit,50,1,100,'limit');integer(params.max_bytes,48000,8000,48000,'max_bytes');ready();
  if (!game.packs) fail('NotReady','Compendium packs are not ready.','Wait for the existing world to finish loading.');
  const documentType=params.document_type===undefined?'Actor':params.document_type;
  if (!['Actor','Item'].includes(documentType)) fail('InvalidRequest','document_type must be Actor or Item.');
  return documentType;
}

function queryInput(value,required) {
  if (value==null&&!required) return '';
  if (typeof value!=='string'||!value.trim()||[...value.trim()].length>200) fail('InvalidRequest','query must contain 1–200 characters after trim.');
  return value.trim().toLowerCase();
}

function title(pack) {
  const value=String(pack.title??'');
  return {title:[...value].slice(0,256).join(''),title_truncated:[...value].length>256};
}

async function page(build,params,scope) {
  const snapshot=await build();const revision=await digest(snapshot);
  const base={contract_version:1,runtime:snapshot.runtime,revision,scopes:snapshot.scopes,limitations:snapshot.limitations};
  const result=await paginate(snapshot.nodes,base,params,scope);
  if (await digest(await build())!==revision) fail('ContentChanged','Selected pack indexes, identities or permissions changed.','Discard accumulated pages and restart without cursor.');
  const {records,...rest}=result;return {...rest,nodes:records};
}

/**
 * PF2e-specific discovery boundary: core14.369/PF2e8.6.1, Actor or Item packs.
 * No system field calculations or type inference from pack titles occur.
 */
export async function listActorCompendiums(params={}) {
  const documentType=inputs(params,['document_type','query','limit','max_bytes','cursor']);const query=queryInput(params.query,false);
  const build=()=>{
    ready();const nodes=[];let denied=false;
    for (const pack of [...game.packs.values()].sort((a,b)=>compare(a.collection,b.collection))) {
      if (pack.documentName!==documentType) continue;
      if (!permitted(pack)) {denied=true;continue;}
      if (query&&!`${pack.title}\n${pack.collection}`.toLowerCase().includes(query)) continue;
      nodes.push({kind:'pack',id:pack.collection,...title(pack),document_type:documentType,visible:pack.visible===true,folder:null,parent_uuid:null,
        search_scope:{pack_ids:[pack.collection],document_type:documentType},
        next_call:null,limitations:[`Choose a literal query and call search_compendium_actors with pack_ids=${JSON.stringify([pack.collection])}, document_type=${JSON.stringify(documentType)}.`]});
    }
    return {runtime:runtime(),nodes,scopes:[{id:'packs',status:denied?'incomplete':'searched',reason:denied?'Some packs are unreadable.':null}],limitations:[FLAT]};
  };
  return page(build,params,{tool:'list_actor_compendiums',document_type:documentType,query});
}

/**
 * PF2e-specific supported subtype filtering: character/npc/familiar or the 24
 * audited Item types; missing index type stays incomplete, never guessed.
 * No prepared/effective data and no getDocument/getDocuments/import calls.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/static/template.json
 */
export async function searchCompendiumActors(params={}) {
  const documentType=inputs(params,['pack_ids','query','types','document_type','limit','max_bytes','cursor']);
  const query=queryInput(params.query,true);const allowed=documentType==='Actor'?ACTOR_TYPES:ITEM_TYPES;
  const types=params.types==null?allowed:params.types;
  if (!Array.isArray(types)||!types.length||types.length>allowed.length||new Set(types).size!==types.length||types.some(type=>!allowed.includes(type))) fail('InvalidRequest','types must be a nonempty unique list of in-scope document types.');
  const ids=params.pack_ids;
  if (!Array.isArray(ids)||!ids.length||ids.length>10||new Set(ids).size!==ids.length||ids.some(id=>typeof id!=='string'||!id.trim()||id.length>256)) fail('InvalidRequest','pack_ids must contain 1–10 unique returned pack IDs, each 1–256 characters.');
  const packIds=[...ids].sort(compare);
  const build=async()=>{
    ready();const nodes=[];const scopes=[];const indexSnapshots=[];
    for (const id of packIds) {
      const pack=game.packs.get(id);
      if (!pack) {scopes.push({id,status:'failed',reason:'Pack not found; refresh list_actor_compendiums.'});continue;}
      if (!permitted(pack)) {scopes.push({id,status:'denied',reason:'Pack OBSERVER permission is required.'});continue;}
      if (pack.documentName!==documentType) {scopes.push({id,status:'failed',reason:'Pack document type differs from document_type.'});continue;}
      let index;
      try { index=await pack.getIndex({fields:['name','type']}); }
      catch {scopes.push({id,status:'failed',reason:'Index retrieval failed; retry or inspect the GM browser.'});continue;}
      if (game.packs.get(id)!==pack||pack.collection!==id||pack.documentName!==documentType||!permitted(pack)) fail('ContentChanged','Selected pack identity or permission changed during index retrieval.','Restart without cursor after inspecting pack access.');
      if (!index||typeof index.values!=='function') {scopes.push({id,status:'failed',reason:'Pack returned an invalid index.'});continue;}
      let incomplete=false;const selected=[];
      for (const entry of index.values()) {
        if (!entry||typeof entry._id!=='string'||!entry._id||typeof entry.name!=='string'||typeof entry.type!=='string') {incomplete=true;continue;}
        let uuid;
        try {uuid=pack.getUuid(entry._id);}catch {incomplete=true;continue;}
        if (typeof uuid!=='string'||!uuid.startsWith('Compendium.')||uuid.length>512) {incomplete=true;continue;}
        selected.push({id:entry._id,uuid,name:entry.name,type:entry.type});
      }
      selected.sort((a,b)=>compare(a.name.toLowerCase(),b.name.toLowerCase())||compare(a.uuid,b.uuid));
      indexSnapshots.push({id,...title(pack),entries:selected});
      for (const entry of selected) {
        if (!types.includes(entry.type)||!entry.name.toLowerCase().includes(query)) continue;
        const identity={document_name:documentType,id:entry.id,uuid:entry.uuid,...named(entry),type:entry.type,source_kind:'compendium',folder:null,pack:{id,title:title(pack).title},actor:null,instance:null};
        nodes.push({kind:documentType==='Actor'?'actor':'item',identity,parent_uuid:null,
          next_call:{tool:documentType==='Actor'?'read_actor':'read_item',arguments:{[documentType==='Actor'?'actor_uuid':'item_uuid']:entry.uuid}}});
      }
      scopes.push({id,status:incomplete?'incomplete':'searched',reason:incomplete?'Index entries lack verified ID, name, type or canonical UUID; ambiguous entries were not classified.':null});
    }
    return {runtime:runtime(),nodes,scopes,indexSnapshots,limitations:[FLAT,'Only selected pack indexes were searched. Failed, denied or incomplete scopes cannot establish absence; selected full readers recheck document permissions.']};
  };
  return page(build,params,{tool:'search_compendium_actors',document_type:documentType,pack_ids:packIds,query,types});
}
