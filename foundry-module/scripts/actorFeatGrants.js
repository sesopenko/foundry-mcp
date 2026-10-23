/**
 * PF2e-specific Item grant source selectors, pinned PF2e 8.6.1/core14.
 * ItemSourceFlagsPF2e, ItemGrantSource and ItemGranterSource schema:
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/base/data/system.ts
 * Detached Item.toObject(true) source only; no prepared defaults or benefit claims.
 */
const SCHEMA='https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/base/data/system.ts';
const LIMIT=['stored_grant_claim_not_active_benefit'];
const MAX_ENTRIES=12000;
/** PF2e-specific 8.6.1 source-key escaping; see module schema URL; no derivation. */
function pointer(keys){return '/'+keys.map(key=>key.replaceAll('~','~0').replaceAll('/','~1')).join('/');}
/** PF2e-specific 8.6.1 own source presence; see module schema URL; optional undefined is absent. */
function selected(source,keys,optional=false){let value=source;for(const key of keys){if(value===null||typeof value!=='object'||!Object.hasOwn(value,key))return {present:false};value=value[key];}return optional&&value===undefined?{present:false}:{present:true,value};}
/** PF2e-specific 8.6.1 descriptor; see module schema URL; preserves source, never effective state. */
function descriptor(keys,value,concept){return {path:pointer(keys),...value,concept,limitations:[...LIMIT]};}
/** PF2e-specific 8.6.1 grant source scalar; see module schema URL; no coercion/defaults. */
function scalar(source,keys,concept,type,optional=false,nullable=false){const value=selected(source,keys,optional);if(value.present&&!(nullable&&value.value===null)&&typeof value.value!==type)throw new TypeError(`Feat grant source ${pointer(keys)} has an unexpected type.`);return descriptor(keys,value,concept);}
/** PF2e-specific 8.6.1 grant record; see module schema URL; validates source containers only. */
function object(value,path){if(!value||typeof value!=='object'||Array.isArray(value))throw new TypeError(`Feat grant source ${path} must be an object.`);}
/**
 * PF2e-specific common Item flags.pf2e.itemGrants/grantedBy source descriptors.
 * Pinned PF2e 8.6.1 ItemSourceFlagsPF2e schema: module SCHEMA URL above.
 * Accepts string Item type codes; returns null without a string source type.
 * Caller gates system ID and supported Item types. Missing and empty
 * maps, nullable grantedBy and missing required IDs stay explicit. Opaque keys
 * are escaped source paths, never selectors. Optional own undefined normalizes
 * absent. onDelete retains unknown string source codes without executing them.
 * No arbitrary flags, rulesSelections, defaults, resolution or effective benefits.
 */
export function itemGrantFields(source){
 if(source===null||typeof source!=='object'||Array.isArray(source)||typeof source.type!=='string')return null;
 const fields=[],mapKeys=['flags','pf2e','itemGrants'],grantedKeys=['flags','pf2e','grantedBy'];
 const grants=selected(source,mapKeys,true);
 if(!grants.present)fields.push(descriptor(mapKeys,grants,'grant_entries'));
 else {
  object(grants.value,pointer(mapKeys));const keys=Object.keys(grants.value);
  if(keys.length>MAX_ENTRIES)throw new TypeError('Feat grant source map exceeds 12000 entries.');
  if(!keys.length)fields.push(descriptor(mapKeys,{present:true,value:{}},'grant_entries'));
  for(const key of keys){const path=[...mapKeys,key];object(grants.value[key],pointer(path));fields.push(scalar(source,[...path,'id'],'grant_item_id','string'),scalar(source,[...path,'onDelete'],'grant_delete_policy','string',true),scalar(source,[...path,'nested'],'grant_nested','boolean',true,true));}
 }
 const granted=selected(source,grantedKeys,true);
 if(!granted.present||granted.value===null)fields.push(descriptor(grantedKeys,granted,'granted_by_source'));
 else {object(granted.value,pointer(grantedKeys));fields.push(scalar(source,[...grantedKeys,'id'],'granted_by_item_id','string'),scalar(source,[...grantedKeys,'onDelete'],'granted_by_delete_policy','string',true));}
 return fields;
}
/**
 * PF2e-specific feat compatibility selector, pinned PF2e 8.6.1 ItemSourceFlagsPF2e
 * at SCHEMA above. Only feat Items are accepted. Retains the existing feat
 * concepts, presence semantics and source-only limitations without changing type.
 */
export function featGrantFields(source){
 if(source?.type!=='feat')return null;
 return itemGrantFields(source).map(field=>({...field,concept:'feat_'+field.concept,limitations:['feat_source_not_effective_benefit']}));
}
