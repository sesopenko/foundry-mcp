/**
 * PF2e-specific armor Item source selector, audited against 8.6.1.
 * Detached Item.toObject(true) only; no actor AC, saves, Speed, worn bonuses or
 * prepared rune effects. Shared physicalFields supplies baseItem, material,
 * equipped state and attachments. Armor usage is not stored and is excluded.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/armor/data.ts
 */
const LIMIT=['source_only_no_actor_armor_calculation'];
/** PF2e-specific 8.6.1 own source lookup; missing differs from explicit undefined. */
function at(source,path) {
 let value=source;
 for(const key of path.split('/')) {
  if(value===null||typeof value!=='object'||!Object.hasOwn(value,key))return {present:false};
  value=value[key];
 }
 return {present:true,value};
}
/** PF2e-specific armor source scalar; no defaults, coercion or code rewriting. */
function scalar(source,path,concept,type,nullable=false) {
 const selected=at(source,path);
 if(selected.present&&!(nullable&&selected.value===null)&&(typeof selected.value!==type||(type==='number'&&!Number.isFinite(selected.value))))throw new TypeError(`Armor source /${path} has an unexpected type.`);
 return {path:'/'+path,...selected,concept,limitations:[...LIMIT]};
}
/** PF2e-specific source object boundary retains missing/null/empty distinctly. */
function object(source,path,concept,children,nullable=false) {
 const selected=at(source,path);
 if(!selected.present||nullable&&selected.value===null)return [{path:'/'+path,...selected,concept,limitations:[...LIMIT]}];
 if(selected.value===null||typeof selected.value!=='object'||Array.isArray(selected.value))throw new TypeError(`Armor source /${path} must be an object${nullable?' or null':''}.`);
 if(!Object.keys(selected.value).length)return [{path:'/'+path,present:true,value:{},concept,limitations:[...LIMIT]}];
 return children();
}
/** PF2e-specific source code array; preserve original order and unknown codes. */
function strings(source,path,concept) {
 const selected=at(source,path);
 if(!selected.present)return [{path:'/'+path,present:false,concept,limitations:[...LIMIT]}];
 if(!Array.isArray(selected.value))throw new TypeError(`Armor source /${path} must be an array.`);
 if(!selected.value.length)return [{path:'/'+path,present:true,value:[],concept,limitations:[...LIMIT]}];
 return selected.value.map((value,i)=>{
  if(typeof value!=='string')throw new TypeError(`Armor source /${path}/${i} must be a string.`);
  return {path:`/${path}/${i}`,present:true,value,concept,limitations:[...LIMIT]};
 });
}
/** PF2e-specific ArmorRuneSource 8.6.1 leaves, never prepared runes.effects. */
function runes(source,path) {
 return object(source,path,'armor_runes',()=>[
  scalar(source,path+'/potency','armor_rune_potency','number'),
  scalar(source,path+'/resilient','armor_rune_resilient','number'),
  ...strings(source,path+'/property','armor_property_rune_code')
 ]);
}
/**
 * PF2e-specific ArmorSystemSource 8.6.1 primitive descriptors.
 * Finite source numbers remain exact, without calculating actor defenses or
 * penalties. Missing/null/zero/empty values differ. Specific material/runes are
 * authored baseline data, not extra bonuses. Unknown code strings stay unchanged.
 * No optional undefined fields are selected; required undefined rejects.
 * No flags, descriptions, rules, usage, traits.config or runes.effects read.
 */
export function armorFields(source) {
 if(source?.type!=='armor')return null;
 const s=(path,concept,type,nullable=false)=>scalar(source,'system/'+path,'armor_'+concept,type,nullable);
 const fields=[s('category','category_code','string'),s('group','group_code','string',true),
  s('acBonus','ac_bonus','number'),s('strength','strength_requirement','number',true),
  s('dexCap','dex_cap','number'),s('checkPenalty','check_penalty','number'),
  s('speedPenalty','speed_penalty','number'),s('grade','grade_code','string',true),
  ...runes(source,'system/runes')];
 fields.push(...object(source,'system/specific','armor_specific_baseline',()=>[
  ...object(source,'system/specific/material','armor_specific_material',()=>[
   s('specific/material/type','specific_material_type_code','string',true),
   s('specific/material/grade','specific_material_grade_code','string',true)
  ]),...runes(source,'system/specific/runes')
 ],true));
 fields.push(...strings(source,'system/traits/value','armor_trait_code'),
  ...strings(source,'system/traits/otherTags','armor_other_tag_code'),
  s('traits/rarity','rarity_code','string'),s('slug','source_slug','string',true));
 for(const [key,type]of [['title','string'],['authors','string'],['license','string'],['remaster','boolean']])fields.push(s('publication/'+key,'publication_'+key,type));
 return fields;
}
