/**
 * PF2e-specific treasure Item source selector, audited against 8.6.1.
 * Detached Item.toObject(true) source only. Shared physicalFields supplies quantity,
 * denominations, price-per basis and carried/container source state. No stack value,
 * sale price, denomination conversion or prepared coin value is computed.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/treasure/data.ts
 */
const LIMIT=['source_only_no_treasure_valuation_or_sale'];
/** PF2e-specific treasure own source lookup; missing differs from explicit undefined. */
function at(source,path) {
 let value=source;
 for(const key of path.split('/')) {
  if(value===null||typeof value!=='object'||!Object.hasOwn(value,key))return {present:false};
  value=value[key];
 }
 return {present:true,value};
}
/** PF2e-specific treasure source scalar; no defaults, coercion or active-state inference. */
function scalar(source,path,concept,type,nullable=false) {
 const selected=at(source,path);
 if(selected.present&&!(nullable&&selected.value===null)&&typeof selected.value!==type)throw new TypeError(`Treasure source /${path} has an unexpected type.`);
 return {path:'/'+path,...selected,concept,limitations:[...LIMIT]};
}
/** PF2e-specific treasure code array; preserve empty, order and unknown source codes. */
function strings(source,path,concept) {
 const selected=at(source,path);
 if(!selected.present)return [{path:'/'+path,present:false,concept,limitations:[...LIMIT]}];
 if(!Array.isArray(selected.value))throw new TypeError(`Treasure source /${path} must be an array.`);
 if(!selected.value.length)return [{path:'/'+path,present:true,value:[],concept,limitations:[...LIMIT]}];
 return selected.value.map((value,i)=>{
  if(typeof value!=='string')throw new TypeError(`Treasure source /${path}/${i} must be a string.`);
  return {path:`/${path}/${i}`,present:true,value,concept,limitations:[...LIMIT]};
 });
}
/**
 * PF2e-specific TreasureSystemSource 8.6.1 category, trait and publication selector.
 * Nullable category remains distinct from missing and unknown string codes. Shared
 * physical source supplies quantity and price.per independently, without multiplying
 * them. No stackGroup getter, prepared usage/investment, coin-value getter, sale
 * estimate, description parsing, rule execution or actor totals are used.
 */
export function treasureFields(source) {
 if(source?.type!=='treasure')return null;
 const s=(path,concept,type,nullable=false)=>scalar(source,'system/'+path,'treasure_'+concept,type,nullable);
 const fields=[s('category','category_code','string',true),...strings(source,'system/traits/value','treasure_trait_code'),
  ...strings(source,'system/traits/otherTags','treasure_other_tag_code'),
  s('traits/rarity','rarity_code','string'),s('slug','source_slug','string',true)];
 for(const [key,type]of [['title','string'],['authors','string'],['license','string'],['remaster','boolean']])fields.push(s('publication/'+key,'publication_'+key,type));
 return fields;
}
