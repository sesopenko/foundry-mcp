/** Read-only Actor/Item extraction foundation; contract: docs/actor-tools.md. */
import { fail, validateParams, integer, selector, selectSections, digest, textFragments, paginate } from './actorReadUtils.js';
import { ACTOR_TYPES, ITEM_TYPES, runtime, ready, named, actorTarget, itemTarget, embeddedIdentity } from './actorDocuments.js';
import { physicalFields, PHYSICAL_TYPES } from './actorPhysical.js';

const ACTOR_SECTIONS = ['identity','source','build','statistics','skills','strikes','abilities','spellcasting','inventory','state','effective'];
const ITEM_SECTIONS = ['identity','source','description','rules','relationships','effective'];
const LIMITS = {default_limit:50,max_records:100,min_bytes:8000,max_bytes:48000,max_text_units:6000,max_cursor_characters:4096,max_selector_characters:512};
const PENDING = 'type_reader_pending';
const VERIFICATION = {deterministic:{status:'passed',evidence:['tests/js/actor-readers.test.js','tests/test_actor_tools.py']},live:{status:'not_run',evidence:[]}};

/** PF2e-specific physical source8.6.1 selection, no prepared/effective values.
 * Schema boundary: actorPhysical.js. Descriptions require their explicit section.
 * Never expose flags, migrations or the whole source object.
 */
function selection(target, sections) {
  const source = target.document.toObject(true);
  if (!source || typeof source!=='object' || Array.isArray(source)) fail('ReadFailed','Document source is not a serialized object.','Inspect the selected document in Foundry.');
  const selected = {};
  let physical=[];
  if (sections.includes('source')) {
    for (const field of ['name','type']) if (Object.hasOwn(source,field)) {
      if (typeof source[field]!=='string') fail('ReadFailed',`Source ${field} has an unexpected type.`,'Inspect the selected document in Foundry.');
      selected[`/${field}`] = source[field];
    }
  }
  if (target.document.documentName==='Item' && PHYSICAL_TYPES.includes(source.type) && sections.includes('source')) {
    try { physical=physicalFields(source).filter(field=>field.concept!=='unidentified_description'); }
    catch (error) {
      const path=String(error?.message??'').match(/\/system\/[A-Za-z0-9_/-]+/)?.[0];
      fail('ReadFailed',`Selected physical source${path?` at ${path}`:''} does not match the verified field schema.`,'Inspect this Item source; malformed fields cannot be interpreted safely.');
    }
  }
  if (sections.includes('description') && source.system?.description && Object.hasOwn(source.system.description,'value')) selected['/system/description/value'] = source.system.description.value;
  if (sections.includes('description') && PHYSICAL_TYPES.includes(source.type)) {
    const data=source.system?.identification?.unidentified?.data?.description;
    if (data&&Object.hasOwn(data,'value')) selected['/system/identification/unidentified/data/description/value']=data.value;
  }
  return { identity: target.identity, selected, physical, runtime: runtime() };
}

/** JSON Pointer source record; values are detached selected document data. */
function record(uuid,path,present,value,section,concept) {
  return {key:`${section}:${path}`,section,kind:'field',raw:[{document_uuid:uuid,path,present,...(present?{value}:{}),basis:'source'}],
    mapped:{concept,value:present?value:null,unit:null},provenance:{contributors:[{document_uuid:uuid,path,basis:'source'}],mapping:'core.selected_source.v1',limitations:[]}};
}

/** Normalize request bounds before resolving any documents. */
function bounds(params, allowed, sectionNames) {
  validateParams(params,allowed);
  integer(params.limit,50,1,100,'limit'); integer(params.max_bytes,48000,8000,48000,'max_bytes');
  if (params.cursor !== undefined && params.cursor !== null && (typeof params.cursor!=='string' || !params.cursor.length || params.cursor.length>4096 || /[^\x00-\x7f]/.test(params.cursor))) fail('InvalidCursor','Use the returned ASCII continuation, unchanged.','Restart without cursor.');
  return sectionNames ? selectSections(params.sections,sectionNames,['identity','source']) : null;
}

/**
 * PF2e-specific capability registry for character/npc/familiar and 24 Item types.
 * Core14.369/PF2e8.6.1 schema scope: only common core metadata and explicit Item
 * system.description.value and shared physical source fields are delivered;
 * type-specific completeness and derived values remain gated.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/base/data/model.ts
 */
export async function getActorTypes(params = {}) {
  validateParams(params,[]); const current = ready(false);
  const supported = current.core_version==='14.369' && current.system_id==='pf2e' && current.system_version==='8.6.1';
  const make = (name, allowed, inScope, sections=false) => ({...(sections?{name}:{type:name,name}),allowed,in_scope:inScope,
    source_supported:supported&&inScope&&(!sections||['identity','source','description'].includes(name)),mapped_supported:false,effective_supported:false,
    limitations:inScope?['Foundation selects core metadata, explicit descriptions and shared physical source fields where applicable; type-specific mappings and effective sections are pending.']:['Type is outside initial Actor/Item scope.'],verification:structuredClone(VERIFICATION)});
  const actorAllowed = globalThis.foundry?.documents?.Actor?.TYPES ?? globalThis.Actor?.TYPES ?? [];
  const itemAllowed = globalThis.foundry?.documents?.Item?.TYPES ?? globalThis.Item?.TYPES ?? [];
  const result = {contract_version:1,runtime:current,availability:{supported,reason:supported?null:'Supported pairing: Foundry14.369/PF2e8.6.1.'},
    actor_types:[...new Set([...ACTOR_TYPES,...actorAllowed])].map(type=>make(type,actorAllowed.includes(type),ACTOR_TYPES.includes(type))),
    item_types:[...new Set([...ITEM_TYPES,...itemAllowed])].map(type=>make(type,itemAllowed.includes(type),ITEM_TYPES.includes(type))),
    actor_sections:ACTOR_SECTIONS.map(name=>make(name,true,true,true)),item_sections:ITEM_SECTIONS.map(name=>make(name,true,true,true)),limits:{...LIMITS},
    limitations:['No complete effective statistics or exhaustive ability list is claimed.']};
  if (new TextEncoder().encode(JSON.stringify(result)).length>48000) fail('ResponseTooLarge','Runtime type declarations exceed the registry response budget.','Inspect custom type declarations with the GM; this registry cannot be returned safely.');
  return result;
}

/**
 * PF2e-specific read boundary: selected Item descriptions and shared physical
 * source schema8.6.1; character/npc/familiar metadata has no effective meaning.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/base/data/model.ts
 */
async function read(target,params,sections,tool) {
  const snapshot = selection(target,sections); const revision = await digest(snapshot);
  const records = [];
  if (sections.includes('source')) {
    for (const field of ['name','type']) records.push(record(target.identity.uuid,`/${field}`,Object.hasOwn(snapshot.selected,`/${field}`),snapshot.selected[`/${field}`],'source',`document_${field}`));
    // PF2e-specific descriptors retain persisted values; no derived usage/Bulk.
    for (const field of snapshot.physical) {
      const entry=record(target.identity.uuid,field.path,field.present,field.value,'source',field.concept);
      entry.provenance.mapping='pf2e.physical.source.v1';entry.provenance.limitations=[...field.limitations];records.push(entry);
    }
  }
  if (sections.includes('description')) {
    for (const path of ['/system/description/value',...(PHYSICAL_TYPES.includes(target.document.type)?['/system/identification/unidentified/data/description/value']:[])]) {
    const present=Object.hasOwn(snapshot.selected,path);
    const value=snapshot.selected[path];
    if (present && typeof value!=='string') fail('ReadFailed','Stored description has an unexpected type.','Inspect the selected Item source in Foundry.');
    if (present) for (const [index,fragment] of textFragments(value).entries()) {
      const entry=record(target.identity.uuid,path,true,fragment.value,'description',path==='/system/description/value'?'description':'unidentified_description');
      entry.kind='text';entry.key+=`:${index}`;entry.mapped.value=null;entry.text={path,...fragment.text};records.push(entry);
    }
    else records.push(record(target.identity.uuid,path,false,null,'description',path==='/system/description/value'?'description':'unidentified_description'));
    }
  }
  const base={contract_version:1,runtime:snapshot.runtime,identity:target.identity,revision,
    sections:sections.map(name=>({name,status:name==='identity'||name==='description'?'complete':name==='source'?'partial':'unsupported',
      reasons:name==='identity'||name==='description'?[]:name==='source'?[PENDING]:['section_not_implemented']})),limitations:['Type-specific system fields and effective mappings are pending their stories.']};
  const result=await paginate(records,base,params,{tool,actor_uuid:params.actor_uuid??null,item_uuid:params.item_uuid??null,token_uuid:params.token_uuid??null,sections});
  // Recheck permission, resolution, identity and selected snapshot after await points.
  const fresh=tool==='read_actor'?await actorTarget(params):await itemTarget(params);
  if (await digest(selection(fresh,sections))!==revision) fail('ContentChanged','Selected data changed during the read.','Discard accumulated pages and restart without cursor.');
  return result;
}

/** PF2e-specific character/npc/familiar admission; only source metadata here. */
export async function readActor(params={}) {
  const sections=bounds(params,['actor_uuid','token_uuid','sections','limit','max_bytes','cursor'],ACTOR_SECTIONS);ready();
  return read(await actorTarget(params),params,sections,'read_actor');
}

/** PF2e-specific 8.6.1 Item admission; common metadata/description source only. */
export async function readItem(params={}) {
  const sections=bounds(params,['item_uuid','token_uuid','sections','limit','max_bytes','cursor'],ITEM_SECTIONS);ready();
  return read(await itemTarget(params),params,sections,'read_item');
}

/**
 * PF2e-specific embedded Item boundary for the 24 in-scope source types on
 * character/npc/familiar Actors. Source relationships beyond canonical parent
 * identity remain pending; do not infer complete actions or acquired benefits.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/static/template.json
 */
export async function listActorItems(params={}) {
  bounds(params,['actor_uuid','token_uuid','types','query','limit','max_bytes','cursor']);ready();
  let types=ITEM_TYPES;
  if (params.types!==undefined && params.types!==null) {
    if (!Array.isArray(params.types)||!params.types.length||params.types.length>ITEM_TYPES.length||new Set(params.types).size!==params.types.length||params.types.some(type=>!ITEM_TYPES.includes(type))) fail('InvalidRequest','types must be a nonempty unique list of in-scope Item types.');
    types=params.types;
  }
  let query='';
  if (params.query!==undefined && params.query!==null) {
    if (typeof params.query!=='string'||!params.query.trim()||[...params.query.trim()].length>200) fail('InvalidRequest','query must contain 1–200 characters after trim.');
    query=params.query.trim().toLowerCase();
  }
  const build=async()=>{
    const owner=await actorTarget(params); const nodes=[];let unsupported_count=0;
    for (const item of owner.document.items.values()) {
      if (!ITEM_TYPES.includes(item.type)) {unsupported_count++;continue;}
      if (!types.includes(item.type)||!String(item.name).toLowerCase().includes(query)) continue;
      const identity=embeddedIdentity(item,owner);
      nodes.push({kind:'item',identity,parent_uuid:owner.document.uuid,relationships:[],next_call:{tool:'read_item',arguments:{item_uuid:identity.uuid,...(owner.token?{token_uuid:owner.token.uuid}:{})}}});
    }
    const compare=(a,b)=>a<b?-1:a>b?1:0;
    nodes.sort((a,b)=>compare(a.identity.type,b.identity.type)||compare(a.identity.name.toLowerCase(),b.identity.name.toLowerCase())||compare(a.identity.uuid,b.identity.uuid));
    return {owner:owner.identity,nodes,unsupported_count,runtime:runtime()};
  };
  const snapshot=await build();const revision=await digest(snapshot);
  const base={contract_version:1,runtime:snapshot.runtime,revision,scopes:[{id:snapshot.owner.uuid,status:'searched',reason:null}],unsupported_count:snapshot.unsupported_count,limitations:['Embedded Items do not enumerate all possible actions.']};
  const result=await paginate(snapshot.nodes,base,params,{tool:'list_actor_items',actor_uuid:params.actor_uuid??null,token_uuid:params.token_uuid??null,types,query});
  if (await digest(await build())!==revision) fail('ContentChanged','Owned Item membership or identity changed.','Restart list_actor_items without cursor.');
  const {records,...rest}=result;return {...rest,nodes:records};
}
