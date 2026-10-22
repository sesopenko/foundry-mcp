/**
 * PF2e-specific ammunition Item source selector, audited against 8.6.1.
 * Detached Item.toObject(true) source only; shared physicalFields supplies baseItem,
 * quantity and physical properties. No consumption, compatibility, effects or rolls.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/ammo/data.ts
 */
const LIMIT=['source_only_no_ammunition_consumption_or_compatibility'];
/** PF2e-specific required ammo source lookup; missing differs from explicit undefined. */
function at(source,path) {
 let value=source;
 for(const key of path.split('/')) {
  if(value===null||typeof value!=='object'||!Object.hasOwn(value,key))return {present:false};
  value=value[key];
 }
 return {present:true,value};
}
/** PF2e-specific ammo source scalar; no defaults, coercion or remaining-use derivation. */
function scalar(source,path,concept,type,nullable=false) {
 const selected=at(source,path);
 if(selected.present&&!(nullable&&selected.value===null)&&(typeof selected.value!==type||(type==='number'&&!Number.isFinite(selected.value))))throw new TypeError(`Ammo source /${path} has an unexpected type.`);
 return {path:'/'+path,...selected,concept,limitations:[...LIMIT]};
}
/** PF2e-specific ammo code array; null, empty, missing and ordered strings stay distinct. */
function strings(source,path,concept,nullable=false) {
 const selected=at(source,path);
 if(!selected.present||nullable&&selected.value===null)return [{path:'/'+path,...selected,concept,limitations:[...LIMIT]}];
 if(!Array.isArray(selected.value))throw new TypeError(`Ammo source /${path} must be an array${nullable?' or null':''}.`);
 if(!selected.value.length)return [{path:'/'+path,present:true,value:[],concept,limitations:[...LIMIT]}];
 return selected.value.map((value,i)=>{
  if(typeof value!=='string')throw new TypeError(`Ammo source /${path}/${i} must be a string.`);
  return {path:`/${path}/${i}`,present:true,value,concept,limitations:[...LIMIT]};
 });
}
/**
 * PF2e-specific AmmoSystemSource 8.6.1 primitive descriptors.
 * craftableAs null requires a selected base category; [] allows any non-magazine
 * category, while strings retain authored category codes. These are schema meanings,
 * never a computed compatibility result. Uses remain exact stored values, separate
 * from quantity. No Item getters, prepared state, flags, rules or descriptions read.
 */
export function ammoFields(source) {
 if(source?.type!=='ammo')return null;
 const s=(path,concept,type,nullable=false)=>scalar(source,'system/'+path,'ammo_'+concept,type,nullable);
 const fields=[s('uses/value','uses_value','number'),s('uses/max','uses_max','number'),s('uses/autoDestroy','auto_destroy','boolean'),
  ...strings(source,'system/craftableAs','ammo_craftable_as_code',true),
  ...strings(source,'system/traits/value','ammo_trait_code'),...strings(source,'system/traits/otherTags','ammo_other_tag_code'),
  s('traits/rarity','rarity_code','string'),s('slug','source_slug','string',true)];
 for(const [key,type]of [['title','string'],['authors','string'],['license','string'],['remaster','boolean']])fields.push(s('publication/'+key,'publication_'+key,type));
 return fields;
}
