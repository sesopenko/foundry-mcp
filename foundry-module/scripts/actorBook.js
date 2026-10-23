/**
 * PF2e-specific book Item source selector, audited against 8.6.1.
 * Detached Item.toObject(true) source only. Contents are UUID claims, not owned
 * Items or known/prepared formulas and spells. Capacity use is not computed.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/book/data.ts
 */
const LIMIT=['source_only_no_book_ownership_or_preparation'];
/** PF2e-specific book own source lookup; missing differs from explicit undefined. */
function at(source,path) {
 let value=source;
 for(const key of path.split('/')) {
  if(value===null||typeof value!=='object'||!Object.hasOwn(value,key))return {present:false};
  value=value[key];
 }
 return {present:true,value};
}
/** PF2e-specific book source scalar; no defaults, coercion or active-state inference. */
function scalar(source,path,concept,type,nullable=false) {
 const selected=at(source,path);
 if(selected.present&&!(nullable&&selected.value===null)&&(typeof selected.value!==type||(type==='number'&&!Number.isFinite(selected.value))))throw new TypeError(`Book source /${path} has an unexpected type.`);
 return {path:'/'+path,...selected,concept,limitations:[...LIMIT]};
}
/** PF2e-specific book code array; preserve empty, order and unknown source codes. */
function strings(source,path,concept) {
 const selected=at(source,path);
 if(!selected.present)return [{path:'/'+path,present:false,concept,limitations:[...LIMIT]}];
 if(!Array.isArray(selected.value))throw new TypeError(`Book source /${path} must be an array.`);
 if(!selected.value.length)return [{path:'/'+path,present:true,value:[],concept,limitations:[...LIMIT]}];
 return selected.value.map((value,i)=>{
  if(typeof value!=='string')throw new TypeError(`Book source /${path}/${i} must be a string.`);
  return {path:`/${path}/${i}`,present:true,value,concept,limitations:[...LIMIT]};
 });
}
/**
 * PF2e-specific BookSystemSource, PF2e 8.6.1. Persisted category, capacity
 * and ordered contents UUID claims only; references do not establish ownership,
 * formula knowledge, prepared spells, capacity use or castability. Shared physical
 * fields supply carrying and price source facts. No subitems, prepared collections,
 * document hydration, rule evaluation or description parsing is inspected.
 */
export function bookFields(source) {
 if(source?.type!=='book')return null;
 /** PF2e-specific book scalar descriptor with original source presence. */
 const s=(path,concept,type,nullable=false)=>scalar(source,'system/'+path,'book_'+concept,type,nullable);
 const fields=[s('category','category_code','string'),s('capacity','capacity','number'),
  ...strings(source,'system/contents','book_content_uuid'),
  ...strings(source,'system/traits/value','book_trait_code'),
  ...strings(source,'system/traits/otherTags','book_other_tag_code'),
  s('traits/rarity','rarity_code','string'),s('slug','source_slug','string',true)];
 for(const [key,type]of [['title','string'],['authors','string'],['license','string'],['remaster','boolean']])fields.push(s('publication/'+key,'publication_'+key,type));
 return fields;
}
