/**
 * PF2e-specific character/NPC/familiar stored condition/effect integration on
 * Foundry14.369/PF2e8.6.1. Reuses public Actor.items, Item.parent/toObject(true)
 * and audited identity/relationship helpers, plus public Item.toObject(false):
 * https://foundryvtt.com/api/v14/classes/foundry.documents.Item.html#toobject
 * Only the detached EffectSystemData.expired boolean is selected as current.
 * Schema contracts:
 * https://github.com/foundryvtt/pf2e/tree/28d9d156f252d084371d994dc359509b49eadf18/src/module/item
 * condition/data.ts, effect/data.ts, abstract-effect/data.ts. No active/expired
 * getters, prepared application, duration arithmetic, rolls, writes or target
 * source hydration. Persisted presence never establishes effective application.
 */
import {embeddedIdentity,permitted} from './actorDocuments.js';
import {conditionFields} from './actorCondition.js';
import {effectFields} from './actorEffect.js';
import {conditionReferenceFields,conditionRelationships} from './actorConditionRelationships.js';
import {effectReferenceFields,effectRelationships} from './actorEffectRelationships.js';

const STORED=['stored_state_not_effective_application'];
const CONDITION_REFERENCE_LIMIT=['Stored local reference or override slug only; no active/suppressed state or persistent-damage dominance is inferred. Unresolved targets disclose no resolved metadata.'];
const EFFECT_REFERENCE_LIMIT=['Immediate stored context only; no acquired ability, learned spell, current application or recursive provenance is inferred. Unresolved targets disclose no identity.'];

/** PF2e-specific own serialized identity field; never invoke selected getters. */
function own(source,key){
 if(source===null||typeof source!=='object')return undefined;
 const descriptor=Object.getOwnPropertyDescriptor(source,key);
 if(!descriptor)return undefined;
 if(!Object.hasOwn(descriptor,'value'))throw new TypeError('State source requires detached own data properties.');
 return descriptor.value;
}
/** PF2e-specific selected stored evidence with actual document provenance. */
function raw(uuid,field){return {document_uuid:uuid,path:field.path,present:field.present,...(field.present?{value:field.value}:{}),basis:'source'};}
/**
 * PF2e-specific EffectSystemData8.6.1 serialized expired flag, not application.
 * Reads only own data from public Item.toObject(false); no source fallback,
 * activity/remainingDuration getter or expiry calculation. Missing is unknown.
 * Pinned schema: src/module/item/effect/data.ts at the revision linked above.
 */
function effectExpiry(item){
 const system=own(item.toObject(false),'system'),value=own(system,'expired');
 const present=system!==null&&typeof system==='object'&&Object.hasOwn(system,'expired');
 if(present&&typeof value!=='boolean')throw new TypeError('Serialized effect expiry must be boolean.');
 return {document_uuid:item.uuid,path:'/system/expired',present,...(present?{value}:{}),basis:'transformed'};
}
/** PF2e-specific state DTO, never an effective application assertion. */
function record(key,kind,concept,evidence,value,mapping,limitations){return {key,section:'state',kind,raw:evidence,mapped:{concept,value,unit:null},provenance:{contributors:evidence.map(({document_uuid,path,basis})=>({document_uuid,path,basis})),mapping,limitations:[...limitations]}};}

/**
 * PF2e-specific bounded Actor stored-state snapshot. target is the authorized
 * Actor target from actorDocuments.js. Extracts each readable owned condition or
 * effect once; duplicate names retain distinct actual identities. Affliction
 * reading is explicitly unsupported regardless of actual inventory. Denied
 * scoped Items expose only one aggregate marker, never source or target names.
 * Preflights 12000 owned Items, 24000 selected records and 200 nonempty external
 * effect context claims before any relationship resolution. Local conditions
 * and immediate effect context reuse existing permission-aware readers; targets'
 * source is never expanded. Caller retains this detached result in revisions.
 * Selects each readable effect's serialized expiry with transformed provenance;
 * false does not establish activity. Missing adds current_effect_expiry_unavailable.
 * Returns {records,reasons}; application is always unknown and reasons always
 * include effective_application_not_evaluated and affliction_reading_unsupported.
 */
export async function actorStateSnapshot(target){
 const actor=target.document;
 if(actor.documentName!=='Actor'||!['character','npc','familiar'].includes(actor.type))throw new TypeError('Stored state requires a supported Actor.');
 const items=[...actor.items.values()];if(items.length>12000)throw new TypeError('Stored state exceeds 12000 owned Items.');
 const snapshots=[],reasons=new Set(['effective_application_not_evaluated','affliction_reading_unsupported']);let denied=false,count=1,claims=0;
 for(const item of items){
  if(!['condition','effect'].includes(item.type))continue;
  if(!permitted(item)){denied=true;continue;}
  if(item.documentName!=='Item'||item.parent!==actor)throw new TypeError('Stored state Item must belong to the selected Actor.');
  const source=item.toObject(true),type=own(source,'type'),name=own(source,'name');
  if(type!==item.type||typeof name!=='string')throw new TypeError('Stored state Item source identity is invalid.');
  const identity=embeddedIdentity(item,{document:actor,token:target.token});
  const fields=type==='condition'?conditionFields(source):effectFields(source),references=type==='condition'?conditionReferenceFields(source):effectReferenceFields(source);
  count+=1+fields.length+(type==='condition'?references.filter(field=>!field.path.endsWith('/type')).length:6);
  if(count>24000)throw new TypeError('Stored state exceeds 24000 selected records.');
  if(type==='effect'){claims+=references.filter(field=>field.present&&typeof field.value==='string'&&field.value!=='').length;if(claims>200)throw new TypeError('Stored state exceeds 200 external context claims.');}
  const expiry=type==='effect'?effectExpiry(item):null;
  if(expiry&&!expiry.present)reasons.add('current_effect_expiry_unavailable');
  snapshots.push({item,identity,sourceName:name,type,fields,references,expiry});
 }
 if(denied&&++count>24000)throw new TypeError('Stored state exceeds 24000 selected records.');
 const records=[];
 for(const snapshot of snapshots){
  const {item,identity,sourceName,type,fields,references,expiry}=snapshot,uuid=identity.uuid;
  const evidence=[raw(uuid,{path:'/name',present:true,value:sourceName}),raw(uuid,{path:'/type',present:true,value:type})];
  const name=[...sourceName];
  records.push(record(`state:item:${uuid}`,'relationship','state_item',evidence,{status:'resolved',target_uuid:uuid,document_name:'Item',type,name:name.slice(0,256).join(''),name_truncated:name.length>256,...(target.token?{token_uuid:target.token.uuid}:{}),application:'unknown'},'pf2e.actor.state-source.v1',STORED));
  for(const field of fields)records.push(record(`state:source:${uuid}:${field.path}`,'field',field.concept,[raw(uuid,field)],Object.hasOwn(field,'mapped_value')?field.mapped_value:field.present?field.value:null,`pf2e.${type}.source.v1`,field.limitations));
  if(type==='condition'){
   for(const reference of conditionRelationships({document:item,actor,token:target.token},references)){
    const claim=reference.raw[0];if(claim?.present&&typeof claim.value==='string'&&claim.value!==''&&reference.result.status!=='resolved')reasons.add('unresolved_state_references');
    records.push(record(`state:condition:${uuid}:${reference.path}`,'relationship',reference.concept,reference.raw.map(field=>raw(uuid,field)),reference.result,'pf2e.condition.reference.v1',CONDITION_REFERENCE_LIMIT));
   }
  }else{
   records.push(record(`state:current:${uuid}:/system/expired`,'field','current_effect_expired',[expiry],expiry.present?expiry.value:null,'pf2e.effect.current.v1',['serialized_effect_expiry_not_application']));
   const evidence=references.map(field=>raw(uuid,field));
   for(const reference of await effectRelationships(references)){
    if(reference.present&&typeof reference.value==='string'&&reference.value!==''&&reference.result.status!=='resolved')reasons.add('unresolved_state_references');
    records.push(record(`state:effect:${uuid}:${reference.role}`,'relationship',`effect_${reference.role}_reference`,evidence,reference.result,'pf2e.effect.context-reference.v1',EFFECT_REFERENCE_LIMIT));
   }
  }
 }
 records.push(record('state:capability:affliction','field','state_affliction_support',[],{status:'unsupported',reason:'pf2e_8_6_1_affliction_disabled'},'pf2e.actor.state-capability.v1',['no_effective_state_inference']));
 if(denied){reasons.add('state_items_denied');records.push(record('state:denied','relationship','state_item',[],{status:'denied',target_uuid:null},'pf2e.actor.state-source.v1',STORED));}
 return {records,reasons:[...reasons].sort()};
}
