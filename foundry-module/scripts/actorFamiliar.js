/**
 * PF2e-specific familiar selected source, audited against PF2e 8.6.1.
 * Immutable schema: https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/familiar/data.ts
 * All helpers process detached source only; no Foundry API calls, preparation,
 * master getter, or derived statistics. See familiar-fields.md for exclusions.
 */
const LIMIT='familiar_source_not_master_derived_statistics';
/** PF2e-specific detached source subtype; accessors are never source fields. */
function sourceType(source){
 if(source===null||typeof source!=='object')return undefined;
 const descriptor=Object.getOwnPropertyDescriptor(source,'type');
 if(!descriptor)return undefined;
 if(!Object.hasOwn(descriptor,'value'))throw new TypeError('Familiar source requires own data properties.');
 return descriptor.value;
}
/** PF2e-specific familiar schema-leaf descriptor; source presence never supplies defaults. */
function field(source,path,concept,kind,nullable=false){
 const keys=path.split('/');let value=source;
 for(const key of keys){
  if(value===null||typeof value!=='object')return {path:`/${path}`,present:false,concept,limitations:[LIMIT]};
  const descriptor=Object.getOwnPropertyDescriptor(value,key);
  if(!descriptor)return {path:`/${path}`,present:false,concept,limitations:[LIMIT]};
  if(!Object.hasOwn(descriptor,'value'))throw new TypeError('Familiar source requires own data properties.');
  value=descriptor.value;
  if(value===undefined)return {path:`/${path}`,present:false,concept,limitations:[LIMIT]};
 }
 const valid=nullable&&value===null||kind==='integer'&&Number.isInteger(value)&&value>=0||kind==='string'&&typeof value==='string'||kind==='nonblank'&&typeof value==='string'&&value.length>0;
 if(!valid)throw new TypeError(`Familiar source /${path} must be ${kind==='integer'?'a nonnegative integer':kind==='nonblank'?'a nonblank string':'a string'}${nullable?' or null':''}.`);
 return {path:`/${path}`,present:true,value,concept,limitations:[LIMIT]};
}
/**
 * PF2e-specific familiar8.6.1 master.id source only: nullable CharacterPF2e
 * ForeignDocumentField, idOnly. The claim targets a world character, never an
 * NPC, UUID, token master or prepared master object. Resolution/permissions are
 * the caller's responsibility. Uses the immutable schema above; no API calls or
 * master-derived fallback. Returns null for other Actor types.
 */
export function familiarMasterField(source){
 if(sourceType(source)!=='familiar')return null;
 return field(source,'system/master/id','recorded_master_character_id','string',true);
}
/**
 * PF2e-specific familiar8.6.1 persisted master.id/master.ability and HP source
 * leaves, using the immutable schema above. Nullable ability stores a code;
 * unknown strings are preserved without interpreted attribute meaning. HP
 * value/temp are declared nonnegative integers; tempSource is optional nonblank
 * owner-local Item ID source, never a verified UUID. No maximum, independent
 * attributes, inherited creature fields or master-derived data is selected.
 * Detached source only; no API calls. Other Actor types return null.
 */
export function familiarFields(source){
 if(sourceType(source)!=='familiar')return null;
 return [familiarMasterField(source),
  field(source,'system/master/ability','recorded_master_attribute_code','string',true),
  field(source,'system/attributes/hp/value','recorded_hit_points','integer'),
  field(source,'system/attributes/hp/temp','recorded_temporary_hit_points','integer'),
  field(source,'system/attributes/hp/tempSource','temporary_hit_point_source_item_id','nonblank')];
}
/**
 * PF2e-specific familiar8.6.1 details.creature.value source prose, using the
 * immutable schema above. Exact string including blank/HTML; no enrichment or
 * interpretation. Explicit description selection and bounded text continuation
 * belong to the shared reader. Detached source only, no API calls or derived
 * fallback. Other Actor types return null.
 */
export function familiarNoteFields(source){
 if(sourceType(source)!=='familiar')return null;
 return [field(source,'system/details/creature/value','familiar_creature_description_source','string')];
}
/**
 * PF2e-specific familiar8.6.1 source master context only, using the pinned
 * schema above. Current-statistics admission/revisions retain ID and recorded
 * ability code separately from transformed values; no modifier is calculated.
 */
export function familiarMasterContextFields(source){
 if(sourceType(source)!=='familiar')return null;
 return [familiarMasterField(source),field(source,'system/master/ability','recorded_master_attribute_code','string',true)];
}
