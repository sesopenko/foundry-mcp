/**
 * PF2e-specific feat grant source selector, pinned PF2e 8.6.1/core14.
 * ItemSourceFlagsPF2e, ItemGrantSource and ItemGranterSource schema:
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/base/data/system.ts
 * Detached Item.toObject(true) source only; no prepared defaults or benefit claims.
 */
const SCHEMA='https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/base/data/system.ts';
const LIMIT=['feat_source_not_effective_benefit'];
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
 * PF2e-specific feat flags.pf2e.itemGrants/grantedBy source descriptors.
 * Pinned PF2e 8.6.1 ItemSourceFlagsPF2e schema: module SCHEMA URL above.
 * Returns null for non-feat Items; caller gates system ID. Missing and empty
 * maps, nullable grantedBy and missing required IDs stay explicit. Opaque keys
 * are escaped source paths, never selectors. Optional own undefined normalizes
 * absent. onDelete retains unknown string source codes without executing them.
 * No arbitrary flags, rulesSelections, defaults, resolution or effective benefits.
 */
export function featGrantFields(source){
 if(source?.type!=='feat')return null;
 const fields=[],mapKeys=['flags','pf2e','itemGrants'],grantedKeys=['flags','pf2e','grantedBy'];
 const grants=selected(source,mapKeys,true);
 if(!grants.present)fields.push(descriptor(mapKeys,grants,'feat_grant_entries'));
 else {
  object(grants.value,pointer(mapKeys));const keys=Object.keys(grants.value);
  if(keys.length>MAX_ENTRIES)throw new TypeError('Feat grant source map exceeds 12000 entries.');
  if(!keys.length)fields.push(descriptor(mapKeys,{present:true,value:{}},'feat_grant_entries'));
  for(const key of keys){const path=[...mapKeys,key];object(grants.value[key],pointer(path));fields.push(scalar(source,[...path,'id'],'feat_grant_item_id','string'),scalar(source,[...path,'onDelete'],'feat_grant_delete_policy','string',true),scalar(source,[...path,'nested'],'feat_grant_nested','boolean',true,true));}
 }
 const granted=selected(source,grantedKeys,true);
 if(!granted.present||granted.value===null)fields.push(descriptor(grantedKeys,granted,'feat_granted_by_source'));
 else {object(granted.value,pointer(grantedKeys));fields.push(scalar(source,[...grantedKeys,'id'],'feat_granted_by_item_id','string'),scalar(source,[...grantedKeys,'onDelete'],'feat_granted_by_delete_policy','string',true));}
 return fields;
}
