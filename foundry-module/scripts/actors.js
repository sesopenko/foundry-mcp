/** Read-only Actor/Item extraction foundation; contract: docs/actor-tools.md. */
import { fail, validateParams, integer, selector, selectSections, digest, textFragments, paginate } from './actorReadUtils.js';
import { ACTOR_TYPES, ITEM_TYPES, runtime, ready, named, permitted, actorTarget, itemTarget, embeddedIdentity } from './actorDocuments.js';
import { physicalFields, PHYSICAL_TYPES } from './actorPhysical.js';
import { weaponFields } from './actorWeapon.js';
import { actionFields, actionReferenceFields } from './actorAction.js';
import { meleeFields, meleeEffectFields } from './actorMelee.js';
import { loreFields } from './actorLore.js';
import { npcFields, npcNoteFields } from './actorNpc.js';
import { effectFields } from './actorEffect.js';
import { conditionFields } from './actorCondition.js';
import { conditionReferenceFields,conditionRelationships } from './actorConditionRelationships.js';
import { effectReferenceFields,effectRelationships } from './actorEffectRelationships.js';

const ACTOR_SECTIONS = ['identity','source','description','build','statistics','skills','strikes','abilities','spellcasting','inventory','state','effective'];
const ITEM_SECTIONS = ['identity','source','description','rules','relationships','effective'];
const LIMITS = {default_limit:50,max_records:100,min_bytes:8000,max_bytes:48000,max_text_units:6000,max_cursor_characters:4096,max_selector_characters:512};
const PENDING = 'type_reader_pending';
const VERIFICATION = {deterministic:{status:'passed',evidence:['tests/js/actor-readers.test.js','tests/test_actor_tools.py']},live:{status:'not_run',evidence:[]}};

/** PF2e-specific physical/action/attack/Lore/NPC source8.6.1 selection, no derived values.
 * Schema boundaries: actorPhysical.js, actorAction.js, actorMelee.js, actorLore.js and actorNpc.js.
 * Descriptions require their explicit section.
 * Never expose flags, migrations or the whole source object.
 */
function selection(target, sections) {
  const source = target.document.toObject(true);
  if (!source || typeof source!=='object' || Array.isArray(source)) fail('ReadFailed','Document source is not a serialized object.','Inspect the selected document in Foundry.');
  const selected = {};
  let physical=[];
  let weapon=[];
  let action=[];
  let melee=[];
  let lore=[];
  let npc=[];
  let effect=[];
  let condition=[];
  let conditionReferences=[];
  let effectReferences=[];
  let npcNotes=[];
  const specialties=[];const deniedLore=[];
  const npcItemSections={};
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
  // PF2e-specific weapon8.6.1 definition/configuration; common source fields
  // remain in actorPhysical.js. No effective Strike or NPC attack is generated.
  if(target.document.documentName==='Item'&&source.type==='weapon'&&sections.includes('source')){
    try{weapon=weaponFields(source);}
    catch(error){
      const path=String(error?.message??'').match(/\/system\/[A-Za-z0-9_~/-]+/)?.[0];
      fail('ReadFailed',`Selected weapon source${path?` at ${path}`:''} does not match the verified schema.`,'Inspect weapon source; carried gear is not a prepared Strike or proof of usability.');
    }
  }
  // PF2e-specific action source8.6.1; source-only selection never hydrates effects.
  if (target.document.documentName==='Item' && source.type==='action' && (sections.includes('source')||sections.includes('relationships'))) {
    try {action=sections.includes('source')?actionFields(source):actionReferenceFields(source);}
    catch (error) {
      const path=String(error?.message??'').match(/\/system\/[A-Za-z0-9_/-]+/)?.[0];
      fail('ReadFailed',`Selected action source${path?` at ${path}`:''} does not match the verified schema.`,'Inspect this action Item source; no prepared defaults are substituted.');
    }
  }
  // PF2e-specific authored NPC attacks: labels are source, not effect UUIDs.
  if (target.document.documentName==='Item' && source.type==='melee' && (sections.includes('source')||sections.includes('relationships'))) {
    try {melee=sections.includes('source')?meleeFields(source):meleeEffectFields(source);}
    catch (error) {
      const path=String(error?.message??'').match(/\/system\/[A-Za-z0-9_~/-]+/)?.[0];
      fail('ReadFailed',`Selected NPC attack source${path?` at ${path}`:''} does not match the verified schema.`,'Inspect this attack Item; authored fields cannot be replaced with carried weapon or prepared values.');
    }
  }
  // PF2e-specific Lore8.6.1: owner comes from the resolved document boundary,
  // not caller input. Rank labels never become an effective skill total.
  if (target.document.documentName==='Item' && source.type==='lore' && sections.includes('source')) {
    try {lore=loreFields(source,target.actor?.type??null);}
    catch (error) {
      const path=String(error?.message??'').match(/\/system\/[A-Za-z0-9_~/-]+/)?.[0];
      fail('ReadFailed',`Selected Lore source${path?` at ${path}`:''} does not match the verified schema.`,'Inspect this Lore Item; missing or malformed values cannot become calculated skill totals.');
    }
  }
  // PF2e-specific effect8.6.1 source; no preparation, formula evaluation or
  // derived expiry. Pinned schema and discriminators live in actorEffect.js.
  if (target.document.documentName==='Item' && source.type==='effect' && sections.includes('source')) {
    try {effect=effectFields(source);}
    catch (error) {
      const path=String(error?.message??'').match(/\/system\/[A-Za-z0-9_~/-]+/)?.[0];
      fail('ReadFailed',`Selected effect source${path?` at ${path}`:''} does not match the verified schema.`,'Inspect the effect source; malformed fields cannot be replaced with derived expiry or evaluated formulas.');
    }
  }
  if(target.document.documentName==='Item'&&source.type==='effect'&&sections.includes('relationships')){
    try{effectReferences=effectReferenceFields(source);}
    catch{fail('ReadFailed','Stored effect context references have an unexpected type.','Inspect the effect source context; no origin or target is inferred.');}
  }
  // PF2e-specific condition8.6.1 persisted source; stored presence/value and
  // override claims are not active/suppressed state. See actorCondition.js.
  if(target.document.documentName==='Item'&&source.type==='condition'&&sections.includes('source')){
    try{condition=conditionFields(source);}
    catch(error){
      const path=String(error?.message??'').match(/\/system\/[A-Za-z0-9_~/-]+/)?.[0];
      fail('ReadFailed',`Selected condition source${path?` at ${path}`:''} does not match the verified schema.`,'Inspect the condition source; no active state, suppression or damage roll is inferred.');
    }
  }
  if(target.document.documentName==='Item'&&source.type==='condition'&&sections.includes('relationships')){
    try{conditionReferences=conditionReferenceFields(source);}
    catch{fail('ReadFailed','Stored condition reference fields do not match the verified schema.','Inspect the condition source; no origin or suppression is inferred.');}
  }
  // PF2e-specific NPC8.6.1 authored stat-block source; no elite/weak math.
  // The pinned schema contract is documented in actorNpc.js.
  if (target.document.documentName==='Actor' && source.type==='npc' && sections.includes('source')) {
    try {npc=npcFields(source);}
    catch (error) {
      const path=String(error?.message??'').match(/\/system\/[A-Za-z0-9_~/-]+/)?.[0];
      fail('ReadFailed',`Selected NPC source${path?` at ${path}`:''} does not match the verified schema.`,'Inspect this NPC source; no prepared statistics or defaults are substituted.');
    }
  }
  // PF2e-specific NPC biography8.6.1 is explicit GM-only description source.
  if (target.document.documentName==='Actor' && source.type==='npc' && sections.includes('description')) {
    try {npcNotes=npcNoteFields(source);}
    catch {fail('ReadFailed','Selected NPC biography has an unexpected type.','Inspect the NPC blurb/public/private source notes; no prepared text is substituted.');}
  }
  // PF2e-specific Lore specialties are actual owned Item references only.
  // Source contract: src/module/item/lore.ts at the actorLore.js pinned revision.
  if (target.document.documentName==='Actor' && sections.includes('skills')) {
    for (const item of target.document.items.values()) {
      if (item.type!=='lore') continue;
      if (!permitted(item)) {deniedLore.push(item.uuid);continue;}
      const identity=embeddedIdentity(item,{document:target.document,token:target.token});
      const itemSource=item.toObject(true);
      if (typeof itemSource?.name!=='string'||itemSource.type!=='lore') fail('ReadFailed','Lore specialty source identity is invalid.','Inspect the owned Lore Item in the selected Actor.');
      specialties.push({identity,name:itemSource.name,type:itemSource.type});
    }
    const compare=(a,b)=>a<b?-1:a>b?1:0;
    specialties.sort((a,b)=>compare(a.name.toLowerCase(),b.name.toLowerCase())||compare(a.identity.uuid,b.identity.uuid));
    deniedLore.sort(compare);
  }
  // PF2e-specific NPC8.6.1 melee/action Items are explicit source references,
  // never prepared Strike arrays, acquired benefits or carried-weapon attacks.
  if (target.document.documentName==='Actor' && source.type==='npc') {
    for (const [section,type] of [['strikes','melee'],['abilities','action']]) {
      if(!sections.includes(section))continue;
      const entries=[],denied=[];
      for(const item of target.document.items.values()) {
        if(item.type!==type)continue;
        if(!permitted(item)){denied.push(item.uuid);continue;}
        const identity=embeddedIdentity(item,{document:target.document,token:target.token});
        const itemSource=item.toObject(true);
        if(typeof itemSource?.name!=='string'||itemSource.type!==type)fail('ReadFailed','NPC owned Item source identity is invalid.','Inspect the selected NPC attack or ability Item.');
        entries.push({identity,name:itemSource.name,type:itemSource.type});
      }
      const compare=(a,b)=>a<b?-1:a>b?1:0;
      entries.sort((a,b)=>compare(a.name.toLowerCase(),b.name.toLowerCase())||compare(a.identity.uuid,b.identity.uuid));denied.sort(compare);
      npcItemSections[section]={entries,denied};
    }
  }
  if (sections.includes('description') && source.system?.description && Object.hasOwn(source.system.description,'value')) selected['/system/description/value'] = source.system.description.value;
  if (sections.includes('description') && PHYSICAL_TYPES.includes(source.type)) {
    const data=source.system?.identification?.unidentified?.data?.description;
    if (data&&Object.hasOwn(data,'value')) selected['/system/identification/unidentified/data/description/value']=data.value;
  }
  return { identity: target.identity, selected, physical, weapon, action, melee, lore, effect, condition, conditionReferences, effectReferences, npc, npcNotes, npcItemSections, specialties, deniedLore, runtime: runtime() };
}

/** PF2e-specific action8.6.1 selfEffect reference, resolved only on explicit
 * relationships requests. Public core14.369 fromUuid(uuid,{relative:Document}):
 * https://foundryvtt.com/api/v14/functions/foundry.utils.fromUuid.html
 * Public Actor.token carries synthetic target context (no UUID construction):
 * https://foundryvtt.com/api/v14/classes/foundry.documents.Actor.html#token
 * Returns identity/status only; no effect preparation, source expansion or use.
 */
async function actionRelationship(target,selected) {
  const reference=selected.action.find(field=>field.path==='/system/selfEffect/uuid');
  const uuid=reference?.present?reference.value:null;
  if (uuid===null||uuid===undefined||uuid==='') return {status:'missing',target_uuid:null,reason:'No stored self-effect reference.',dependency:null};
  if (typeof uuid!=='string'||uuid.length>512||!uuid.trim()) return {status:'unsupported',target_uuid:null,reason:'Stored self-effect reference is not a supported bounded UUID.',dependency:null};
  let effect;
  try {effect=await foundry.utils.fromUuid(uuid,{relative:target.document});}
  catch {return {status:'unverified',target_uuid:null,reason:'Self-effect resolution failed; retry an explicit relationships read.',dependency:null};}
  if (!effect) return {status:'missing',target_uuid:null,reason:'Stored self-effect target was not found.',dependency:null};
  const owner=effect.parent?.documentName==='Actor'?effect.parent:null;
  const pack=effect.compendium??owner?.compendium??null;
  if (!permitted(effect)||(owner&&!permitted(owner))||(pack&&!permitted(pack))) return {status:'denied',target_uuid:null,reason:'Self-effect target or owner/pack is not readable.',dependency:null};
  if (effect.documentName!=='Item'||effect.type!=='effect'||(owner&&!ACTOR_TYPES.includes(owner.type))||typeof effect.uuid!=='string'||!effect.uuid.length||effect.uuid.length>512) return {status:'unsupported',target_uuid:null,reason:'Self-effect target is outside the supported effect Item context.',dependency:null};
  let tokenUuid=null;
  if (effect.uuid.startsWith('Scene.')) {
    const token=owner?.token;
    if (!token?.uuid) return {status:'unverified',target_uuid:null,reason:'Synthetic self-effect target has no available token context.',dependency:null};
    let instance;
    try {instance=await actorTarget({token_uuid:token.uuid});}
    catch (error) {return {status:error?.rpcError?.code==='PermissionDenied'?'denied':'unverified',target_uuid:null,reason:'Synthetic self-effect token context is inaccessible or unavailable.',dependency:null};}
    if (instance.document.uuid!==owner.uuid||![...instance.document.items.values()].some(item=>item.uuid===effect.uuid)) return {status:'unverified',target_uuid:null,reason:'Synthetic self-effect no longer belongs to its current token Actor.',dependency:null};
    tokenUuid=token.uuid;
  }
  return {status:'resolved',target_uuid:effect.uuid,...(tokenUuid?{token_uuid:tokenUuid}:{}),reason:null,dependency:{uuid:effect.uuid,type:effect.type,parent_uuid:owner?.uuid??null,pack_id:pack?.collection??null}};
}

/** PF2e-specific detached source+immediate action relationship snapshot. */
async function snapshot(target,sections) {
  const selected=selection(target,sections);
  if (target.document.type==='action'&&sections.includes('relationships')) selected.relationship=await actionRelationship(target,selected);
  if(target.document.type==='effect'&&sections.includes('relationships'))selected.effectRelationships=await effectRelationships(selected.effectReferences);
  if(target.document.type==='condition'&&sections.includes('relationships'))selected.conditionRelationships=conditionRelationships(target,selected.conditionReferences);
  return selected;
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
 * action and NPC attack Items have selected type mappings and named references;
 * other concrete types and all derived/effective values remain gated.
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
  // PF2e-specific action8.6.1 source milestone; section flags are conditional on
  // this per-type registry, never a promise for every other Item type.
  if (supported) {
    const action=result.item_types.find(entry=>entry.type==='action');
    action.mapped_supported=true;
    action.limitations=['Selected action activation/frequency/traits/publication source and explicit self-effect references; no effective usability or automatic application.'];
    action.verification={deterministic:{status:'passed',evidence:['tests/js/actor-action.test.js','tests/js/actor-action-readers.test.js','tests/test_actor_action.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/action-fields.md','scripts/actor-live-check.py']}};
    const melee=result.item_types.find(entry=>entry.type==='melee');
    melee.mapped_supported=true;
    melee.limitations=['Authored NPC attack modes, bonus/damage/range source and named effect labels; no effective elite/weak/MAP/target math. Null source range does not exclude thrown traits. Live checks cover Strikes; other modes have schema/fixture coverage.'];
    melee.verification={deterministic:{status:'passed',evidence:['tests/js/actor-melee.test.js','tests/js/actor-melee-readers.test.js','tests/test_actor_melee.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/melee-fields.md','scripts/actor-live-check.py']}};
    const weapon=result.item_types.find(entry=>entry.type==='weapon');
    weapon.mapped_supported=true;
    weapon.limitations=['Persisted weapon definition/configuration and shared physical source only. No final Strike or NPC authored attack is generated; carried gear is not proof of usability. Selected ammunition resolution and effective alternate-use calculations remain pending.'];
    weapon.verification={deterministic:{status:'passed',evidence:['tests/js/actor-weapon.test.js','tests/js/actor-weapon-readers.test.js','tests/test_actor_weapon.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/weapon-verification.md','scripts/actor-live-check.py']}};
    const affliction=result.item_types.find(entry=>entry.type==='affliction');
    affliction.source_supported=false;affliction.mapped_supported=false;
    affliction.limitations=['PF2e8.6.1 production disables affliction Item construction. Offline schema selectors exist but runtime reading is unsupported; use original poison/disease/curse descriptions.'];
    affliction.verification={deterministic:{status:'passed',evidence:['tests/js/actor-affliction.test.js','tests/js/actor-affliction-support.test.js']},live:{status:'not_run',evidence:['docs/actor-item-story-map/affliction-verification.md']}};
    const condition=result.item_types.find(entry=>entry.type==='condition');
    condition.mapped_supported=true;
    condition.limitations=['Persisted condition/value, persistent damage, local references and override slugs only. Activity, suppression, effective duration and damage dominance are unsupported. Explicit relationships resolve actual owner-local Item IDs; override slugs remain unverified.'];
    condition.verification={deterministic:{status:'passed',evidence:['tests/js/actor-condition.test.js','tests/js/actor-condition-readers.test.js','tests/js/actor-condition-relationships.test.js','tests/test_actor_condition.py','tests/test_actor_condition_relationships.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/condition-verification.md','scripts/actor-live-check.py']}};
    const effect=result.item_types.find(entry=>entry.type==='effect');
    effect.mapped_supported=true;
    effect.limitations=['Persisted duration/start, badge discriminator and context source only; formulas are not evaluated, source UUID references are unverified until explicit immediate context resolution; expiry/current application remain unsupported.'];
    effect.verification={deterministic:{status:'passed',evidence:['tests/js/actor-effect.test.js','tests/js/actor-effect-readers.test.js','tests/js/actor-effect-relationships.test.js','tests/test_actor_effect.py','tests/test_actor_effect_relationships.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/effect-verification.md','scripts/actor-live-check.py']}};
    const lore=result.item_types.find(entry=>entry.type==='lore');
    lore.mapped_supported=true;
    lore.limitations=['Stored Lore modifier and labelled rank use actual owner type; no character or NPC effective check total. Standalone Items retain neutral stored semantics.'];
    lore.verification={deterministic:{status:'passed',evidence:['tests/js/actor-lore.test.js','tests/js/actor-lore-readers.test.js','tests/test_actor_lore.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/lore-fields.md','scripts/actor-live-check.py']}};
    const skills=result.actor_sections.find(entry=>entry.name==='skills');
    skills.source_supported=true;skills.mapped_supported=true;
    skills.verification=structuredClone(lore.verification);
    skills.limitations=['Lore specialty Item references only; all other Skills and effective totals remain pending.'];
    for (const actor of result.actor_types.filter(entry=>entry.in_scope)) {
      actor.mapped_supported=true;
      actor.limitations=['Only Lore specialty references in skills are mapped so far; full type-specific source/statistics and effective views remain pending.'];
    }
    for(const name of ['strikes','abilities']) {
      const section=result.actor_sections.find(entry=>entry.name===name);
      section.source_supported=true;section.mapped_supported=true;
      section.verification={deterministic:{status:'passed',evidence:['tests/js/actor-npc-readers.test.js','tests/test_actor_npc_references.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/npc-fields.md','scripts/actor-live-check.py']}};
      section.limitations=['NPC actual owned melee/action Item references only; sections remain partial. Other Actor types and effective attack/ability lists remain unsupported.'];
    }
    const description=result.actor_sections.find(entry=>entry.name==='description');
    description.limitations=['NPC biography only: blurb, publicNotes and GM-private privateNotes; explicit selection required. Character/familiar biography remains unsupported.'];
    const npc=result.actor_types.find(entry=>entry.type==='npc');
    npc.limitations=['Authored NPC source statistics and Lore references are delivered. Explicit description exposes separate bounded biography notes; integrated sections and effective/current statistics remain pending; elite/weak math is not applied.'];
    npc.verification={deterministic:{status:'passed',evidence:['tests/js/actor-npc.test.js','tests/js/actor-npc-readers.test.js','tests/test_actor_npc.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/npc-fields.md','scripts/actor-live-check.py']}};
    for (const section of result.item_sections.filter(entry=>['source','relationships'].includes(entry.name))) {
      section.source_supported=true;section.mapped_supported=true;
      section.limitations=['Action, NPC attack and Lore Items have delivered source mappings; relationships currently cover action self-effects and named attack effects. Inspect individual type entries.'];
    }
  }
  if (new TextEncoder().encode(JSON.stringify(result)).length>48000) fail('ResponseTooLarge','Runtime type declarations exceed the registry response budget.','Inspect custom type declarations with the GM; this registry cannot be returned safely.');
  return result;
}

/**
 * PF2e-specific read boundary: selected Item descriptions and shared physical
 * source schema8.6.1; character/npc/familiar metadata has no effective meaning.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/base/data/model.ts
 */
async function read(target,params,sections,tool) {
  const selected = await snapshot(target,sections); const revision = await digest(selected);
  const records = [];
  if (sections.includes('source')) {
    for (const field of ['name','type']) records.push(record(target.identity.uuid,`/${field}`,Object.hasOwn(selected.selected,`/${field}`),selected.selected[`/${field}`],'source',`document_${field}`));
    // PF2e-specific descriptors retain persisted fields. Source mappings never
    // substitute carried gear, prepared statistics, effective usage or Bulk.
    for (const [fields,mapping] of [[selected.physical,'pf2e.physical.source.v1'],[selected.weapon,'pf2e.weapon.source.v1'],[selected.action,'pf2e.action.source.v1'],[selected.melee,'pf2e.melee.source.v1'],[selected.lore,'pf2e.lore.source.v1'],[selected.npc,'pf2e.npc.source.v1'],[selected.effect,'pf2e.effect.source.v1'],[selected.condition,'pf2e.condition.source.v1']]) {
    for (const field of fields) {
      const entry=record(target.identity.uuid,field.path,field.present,field.value,'source',field.concept);
      if (Object.hasOwn(field,'mapped_value')) entry.mapped.value=field.mapped_value;
      entry.provenance.mapping=mapping;entry.provenance.limitations=[...field.limitations];records.push(entry);
    }
    }
  }
  if (target.document.documentName==='Actor'&&sections.includes('skills')) {
    for (const specialty of selected.specialties) {
      const raw=[['/name',specialty.name],['/type',specialty.type]].map(([path,value])=>({document_uuid:specialty.identity.uuid,path,present:true,value,basis:'source'}));
      records.push({key:`skills:lore:${specialty.identity.uuid}`,section:'skills',kind:'relationship',raw,
        mapped:{concept:'lore_specialty',value:{target_uuid:specialty.identity.uuid,status:'resolved',...(target.token?{token_uuid:target.token.uuid}:{})},unit:null},
        provenance:{contributors:raw.map(({document_uuid,path,basis})=>({document_uuid,path,basis})),mapping:'pf2e.lore.specialty.v1',limitations:['Lore Item reference only; read_item returns owner-aware source, not an effective skill total.']}});
    }
    if (selected.deniedLore.length) records.push({key:'skills:lore:denied',section:'skills',kind:'relationship',raw:[],
      mapped:{concept:'lore_specialty',value:{target_uuid:null,status:'denied'},unit:null},
      provenance:{contributors:[],mapping:'pf2e.lore.specialty.v1',limitations:['One or more owned Lore Items are unreadable; have the authorized GM grant document access and retry.']}});
  }
  for(const [section,{entries,denied}] of Object.entries(selected.npcItemSections)) {
    const concept=section==='strikes'?'npc_attack_item':'npc_ability_item';
    for(const item of entries) {
      const raw=[['/name',item.name],['/type',item.type]].map(([path,value])=>({document_uuid:item.identity.uuid,path,present:true,value,basis:'source'}));
      records.push({key:`${section}:item:${item.identity.uuid}`,section,kind:'relationship',raw,
        mapped:{concept,value:{target_uuid:item.identity.uuid,status:'resolved',...(target.token?{token_uuid:target.token.uuid}:{})},unit:null},
        provenance:{contributors:raw.map(({document_uuid,path,basis})=>({document_uuid,path,basis})),mapping:'pf2e.npc.item-reference.v1',limitations:['Actual owned Item reference only; follow target_uuid with read_item and supplied token_uuid. Not a complete effective attack or ability list.']}});
    }
    if(denied.length)records.push({key:`${section}:items:denied`,section,kind:'relationship',raw:[],
      mapped:{concept,value:{target_uuid:null,status:'denied'},unit:null},
      provenance:{contributors:[],mapping:'pf2e.npc.item-reference.v1',limitations:['One or more owned Items are unreadable; have the authorized GM grant access and retry.']}});
  }
  if(selected.conditionRelationships)for(const reference of selected.conditionRelationships){
    const raw=reference.raw.map(({path,present,value})=>({document_uuid:target.identity.uuid,path,present,...(present?{value}:{}),basis:'source'}));
    records.push({key:`relationships:condition:${reference.path}`,section:'relationships',kind:'relationship',raw,
      mapped:{concept:reference.concept,value:reference.result,unit:null},
      provenance:{contributors:raw.map(({document_uuid,path,basis})=>({document_uuid,path,basis})),mapping:'pf2e.condition.reference.v1',limitations:['Stored local reference or override slug only; no active/suppressed state or persistent-damage dominance is inferred. Unresolved targets disclose no resolved metadata.']}});
  }
  if(selected.effectRelationships){
    const raw=selected.effectReferences.map(({path,present,value})=>({document_uuid:target.identity.uuid,path,present,...(present?{value}:{}),basis:'source'}));
    for(const reference of selected.effectRelationships)records.push({key:`relationships:effect:${reference.role}`,section:'relationships',kind:'relationship',raw,
      mapped:{concept:`effect_${reference.role}_reference`,value:reference.result,unit:null},
      provenance:{contributors:raw.map(({document_uuid,path,basis})=>({document_uuid,path,basis})),mapping:'pf2e.effect.context-reference.v1',limitations:['Immediate stored context only; no acquired ability, learned spell, current application or recursive provenance is inferred. Unresolved targets disclose no identity.']}});
  }
  if (target.document.type==='melee'&&sections.includes('relationships')) {
    for (const field of selected.melee.filter(entry=>entry.path.startsWith('/system/attackEffects/value'))) {
      const indexed=field.path.startsWith('/system/attackEffects/value/');
      const entry=record(target.identity.uuid,field.path,field.present,field.value,'relationships','additional_effect');
      entry.kind='relationship';entry.key=`relationships:attackEffects${indexed?`:${field.path.split('/').at(-1)}`:''}`;
      entry.mapped.value={target_uuid:null,status:indexed?'unverified':'missing'};
      entry.provenance.mapping='pf2e.melee.attack_effect.v1';
      entry.provenance.limitations=indexed?['Stored additional-effect label is not a UUID; discover its definition separately.']:['No stored additional-effect labels; source presence distinguishes an absent array from an empty array.'];
      records.push(entry);
    }
  }
  if (selected.relationship) {
    const paths=['/system/selfEffect/uuid','/system/selfEffect/name'];
    const raw=paths.map(path=>{const field=selected.action.find(entry=>entry.path===path);return {document_uuid:target.identity.uuid,path,present:field?.present===true,...(field?.present?{value:field.value}:{}),basis:'source'};});
    records.push({key:'relationships:selfEffect',section:'relationships',kind:'relationship',raw,
      mapped:{concept:'self_effect',value:{target_uuid:selected.relationship.target_uuid,status:selected.relationship.status,...(selected.relationship.token_uuid?{token_uuid:selected.relationship.token_uuid}:{})},unit:null},
      provenance:{contributors:raw.map(({document_uuid,path,basis})=>({document_uuid,path,basis})),mapping:'pf2e.action.self_effect.v1',limitations:selected.relationship.reason?[selected.relationship.reason]:[]}});
  }
  if (sections.includes('description')) {
    const fields=target.document.documentName==='Actor'?selected.npcNotes:
      ['/system/description/value',...(PHYSICAL_TYPES.includes(target.document.type)?['/system/identification/unidentified/data/description/value']:[])].map(path=>({path,present:Object.hasOwn(selected.selected,path),value:selected.selected[path],concept:path==='/system/description/value'?'description':'unidentified_description'}));
    for (const field of fields) {
      const {path,present,value,concept}=field;
      if (present && typeof value!=='string') fail('ReadFailed','Stored description has an unexpected type.','Inspect the selected document source in Foundry.');
      const make=(present,value)=>{
        const entry=record(target.identity.uuid,path,present,value,'description',concept);
        if(target.document.documentName==='Actor') {
          entry.provenance.mapping='pf2e.npc.notes.v1';
          entry.provenance.limitations=['Exact stored NPC biography; public and GM-private notes remain separate source paths. No enrichment is executed.'];
        }
        return entry;
      };
      if (present) for (const [index,fragment] of textFragments(value).entries()) {
        const entry=make(true,fragment.value);
        entry.kind='text';entry.key+=`:${index}`;entry.mapped.value=null;entry.text={path,...fragment.text};records.push(entry);
      }
      else records.push(make(false,null));
    }
  }
  const isAction=target.document.documentName==='Item'&&target.document.type==='action';
  const isMelee=target.document.documentName==='Item'&&target.document.type==='melee';
  const isLore=target.document.documentName==='Item'&&target.document.type==='lore';
  const isWeapon=target.document.documentName==='Item'&&target.document.type==='weapon';
  const isCondition=target.document.documentName==='Item'&&target.document.type==='condition';
  const isEffect=target.document.documentName==='Item'&&target.document.type==='effect';
  const loreSkills=target.document.documentName==='Actor'&&sections.includes('skills');
  const complete=name=>name==='identity'||(name==='description'&&(target.document.documentName==='Item'||target.document.type==='npc'))||((isLore||isWeapon)&&name==='source')||((isEffect||isCondition)&&['source','relationships'].includes(name))||((isAction||isMelee)&&['source','relationships'].includes(name));
  const base={contract_version:1,runtime:selected.runtime,identity:target.identity,revision,
    sections:sections.map(name=>({name,status:complete(name)?'complete':name==='source'||Object.hasOwn(selected.npcItemSections,name)||(loreSkills&&name==='skills')?'partial':'unsupported',
      reasons:complete(name)?[]:Object.hasOwn(selected.npcItemSections,name)?[name==='strikes'?'other_attacks_pending':'other_abilities_pending',...(selected.npcItemSections[name].denied.length?['related_items_denied']:[])]:loreSkills&&name==='skills'?['other_skills_pending',...(selected.deniedLore.length?['related_items_denied']:[])]:name==='source'?[PENDING]:['section_not_implemented']})),limitations:[target.document.documentName==='Actor'&&target.document.type==='npc'?'Authored NPC source fields only; biography requires explicit description; integrated sections remain pending. Elite/weak and effective/current statistics are not calculated.':isWeapon?'Persisted weapon definition and configuration only; carry state is not proof of wielding/usability. No final Strike, NPC authored attack or alternate-use result is calculated.':isCondition?'Stored condition source only; presence and override references do not establish active or suppressed state. Persistent damage formulas are not rolled and dominance is not calculated.':isEffect?'Persisted effect source only; formulas are not evaluated, origins are not acquired spells/abilities. Immediate context relationships require explicit selection; expiry/current application remains unsupported.':isLore?'Selected Lore source uses actual owner type; no effective check total or proficiency bonus is calculated.':isMelee?'Authored NPC attack source and named effect labels only; no effective elite/weak/MAP/target calculation or weapon substitution.':isAction?'Selected action source and immediate self-effect reference only; no current usability or effective benefits are claimed.':loreSkills?'Skills currently includes only actual Lore Item references; other Skills and all effective totals remain pending.':'Type-specific system fields and effective mappings are pending their stories.']};
  const result=await paginate(records,base,params,{tool,actor_uuid:params.actor_uuid??null,item_uuid:params.item_uuid??null,token_uuid:params.token_uuid??null,sections});
  // Recheck permission, resolution, identity and selected snapshot after await points.
  const fresh=tool==='read_actor'?await actorTarget(params):await itemTarget(params);
  if (await digest(await snapshot(fresh,sections))!==revision) fail('ContentChanged','Selected data changed during the read.','Discard accumulated pages and restart without cursor.');
  return result;
}

/** PF2e-specific character/npc/familiar admission; only source metadata here. */
export async function readActor(params={}) {
  const sections=bounds(params,['actor_uuid','token_uuid','sections','limit','max_bytes','cursor'],ACTOR_SECTIONS);ready();
  return read(await actorTarget(params),params,sections,'read_actor');
}

/** PF2e-specific 8.6.1 Item boundary; selected source and explicit relationships,
 * never prepared/effective math. Schema contracts live in imported type helpers. */
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
      if (!ITEM_TYPES.includes(item.type)||item.type==='affliction') {unsupported_count++;continue;}
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
