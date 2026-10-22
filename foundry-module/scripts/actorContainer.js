/**
 * PF2e-specific container Item source selector, audited against 8.6.1.
 * Detached Item.toObject(true) source only. Shared physicalFields supplies bulk.value, usage, containerId and carried
 * source state. No current contents Bulk, ignored-Bulk application or totals
 * are computed.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/container/data.ts
 */
const LIMIT=['source_only_no_container_bulk_calculation'];
/** PF2e-specific container own source lookup; missing differs from explicit undefined. */
function at(source,path) {
 let value=source;
 for(const key of path.split('/')) {
  if(value===null||typeof value!=='object'||!Object.hasOwn(value,key))return {present:false};
  value=value[key];
 }
 return {present:true,value};
}
/** PF2e-specific container source scalar; no defaults, coercion or active-state inference. */
function scalar(source,path,concept,type,nullable=false) {
 const selected=at(source,path);
 if(selected.present&&!(nullable&&selected.value===null)&&(typeof selected.value!==type||(type==='number'&&!Number.isFinite(selected.value))))throw new TypeError(`Container source /${path} has an unexpected type.`);
 return {path:'/'+path,...selected,concept,limitations:[...LIMIT]};
}
/** PF2e-specific container code array; preserve empty, order and unknown source codes. */
function strings(source,path,concept) {
 const selected=at(source,path);
 if(!selected.present)return [{path:'/'+path,present:false,concept,limitations:[...LIMIT]}];
 if(!Array.isArray(selected.value))throw new TypeError(`Container source /${path} must be an array.`);
 if(!selected.value.length)return [{path:'/'+path,present:true,value:[],concept,limitations:[...LIMIT]}];
 return selected.value.map((value,i)=>{
  if(typeof value!=='string')throw new TypeError(`Container source /${path}/${i} must be a string.`);
  return {path:`/${path}/${i}`,present:true,value,concept,limitations:[...LIMIT]};
 });
}
/**
 * PF2e-specific ContainerSystemSource (backpack Items), PF2e 8.6.1.
 * Persisted capacity is not current contents Bulk. ignored is an authored rule
 * parameter, never an unconditional subtraction. heldOrStowed is a stored Bulk
 * configuration, not the item's effective current Bulk. Shared physical source
 * fields remain separate. No getters, nested contents, collapsed sheet state,
 * prepared Bulk, rule evaluation or description parsing are inspected.
 */
export function containerFields(source) {
 if(source?.type!=='backpack')return null;
 const s=(path,concept,type,nullable=false)=>scalar(source,'system/'+path,'container_'+concept,type,nullable);
 const fields=[s('stowing','stowing','boolean'),
  ...['heldOrStowed','capacity','ignored'].map((key)=>s('bulk/'+key,{heldOrStowed:'bulk_held_or_stowed',capacity:'bulk_capacity',ignored:'bulk_ignored'}[key],'number')),
  ...strings(source,'system/traits/value','container_trait_code'),
  ...strings(source,'system/traits/otherTags','container_other_tag_code'),
  s('traits/rarity','rarity_code','string'),s('slug','source_slug','string',true)];
 for(const [key,type]of [['title','string'],['authors','string'],['license','string'],['remaster','boolean']])fields.push(s('publication/'+key,'publication_'+key,type));
 return fields;
}
