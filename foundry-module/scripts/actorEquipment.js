/**
 * PF2e-specific equipment Item source selector, audited against 8.6.1.
 * Detached Item.toObject(true) source only. Shared physicalFields supplies usage,
 * carried/invested source state and attachment identities. No active benefits,
 * activation execution, inferred frequency or actor statistics are computed.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/equipment/data.ts
 */
const LIMIT=['source_only_no_equipment_benefit_application'];
/** PF2e-specific equipment own source lookup; missing differs from explicit undefined. */
function at(source,path) {
 let value=source;
 for(const key of path.split('/')) {
  if(value===null||typeof value!=='object'||!Object.hasOwn(value,key))return {present:false};
  value=value[key];
 }
 return {present:true,value};
}
/** PF2e-specific equipment source scalar; no defaults, coercion or active-state inference. */
function scalar(source,path,concept,type,nullable=false) {
 const selected=at(source,path);
 if(selected.present&&!(nullable&&selected.value===null)&&typeof selected.value!==type)throw new TypeError(`Equipment source /${path} has an unexpected type.`);
 return {path:'/'+path,...selected,concept,limitations:[...LIMIT]};
}
/** PF2e-specific equipment code array; preserve empty, order and unknown source codes. */
function strings(source,path,concept) {
 const selected=at(source,path);
 if(!selected.present)return [{path:'/'+path,present:false,concept,limitations:[...LIMIT]}];
 if(!Array.isArray(selected.value))throw new TypeError(`Equipment source /${path} must be an array.`);
 if(!selected.value.length)return [{path:'/'+path,present:true,value:[],concept,limitations:[...LIMIT]}];
 return selected.value.map((value,i)=>{
  if(typeof value!=='string')throw new TypeError(`Equipment source /${path}/${i} must be a string.`);
  return {path:`/${path}/${i}`,present:true,value,concept,limitations:[...LIMIT]};
 });
}
/**
 * PF2e-specific EquipmentSystemSource 8.6.1 trait and publication descriptors.
 * Source traits do not assert active magic or erased mundane benefits. Activation
 * text remains in the explicit description section: absence of a structured field
 * cannot establish absence of an ability. No getters, rule elements, apex bonuses,
 * prepared state, attachment source recursion or activation parsing are used.
 */
export function equipmentFields(source) {
 if(source?.type!=='equipment')return null;
 const s=(path,concept,type,nullable=false)=>scalar(source,'system/'+path,'equipment_'+concept,type,nullable);
 const fields=[...strings(source,'system/traits/value','equipment_trait_code'),
  ...strings(source,'system/traits/otherTags','equipment_other_tag_code'),
  s('traits/rarity','rarity_code','string'),s('slug','source_slug','string',true)];
 for(const [key,type]of [['title','string'],['authors','string'],['license','string'],['remaster','boolean']])fields.push(s('publication/'+key,'publication_'+key,type));
 return fields;
}
