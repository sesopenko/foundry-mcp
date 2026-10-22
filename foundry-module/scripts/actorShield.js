/**
 * PF2e-specific shield Item source selector, audited against 8.6.1.
 * Detached Item.toObject(true) only; no actor AC, Speed, raised state or
 * prepared rune effects. Shared physicalFields supplies baseItem, material,
 * equipped state and attachments. Shield usage is not stored and is excluded.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/shield/data.ts
 */
const LIMIT=['source_only_no_actor_shield_calculation'];
/** PF2e-specific 8.6.1 own source lookup; missing differs from explicit undefined. */
function at(source,path) {
 let value=source;
 for(const key of path.split('/')) {
  if(value===null||typeof value!=='object'||!Object.hasOwn(value,key))return {present:false};
  value=value[key];
 }
 return {present:true,value};
}
/** PF2e-specific shield source scalar; no defaults, coercion or code rewriting. */
function scalar(source,path,concept,type,nullable=false) {
 const selected=at(source,path);
 if(selected.present&&!(nullable&&selected.value===null)&&(typeof selected.value!==type||(type==='number'&&!Number.isFinite(selected.value))))throw new TypeError(`Shield source /${path} has an unexpected type.`);
 return {path:'/'+path,...selected,concept,limitations:[...LIMIT]};
}
/** PF2e-specific source object boundary retains missing/null/empty distinctly. */
function object(source,path,concept,children,nullable=false) {
 const selected=at(source,path);
 if(!selected.present||nullable&&selected.value===null)return [{path:'/'+path,...selected,concept,limitations:[...LIMIT]}];
 if(selected.value===null||typeof selected.value!=='object'||Array.isArray(selected.value))throw new TypeError(`Shield source /${path} must be an object${nullable?' or null':''}.`);
 if(!Object.keys(selected.value).length)return [{path:'/'+path,present:true,value:{},concept,limitations:[...LIMIT]}];
 return children();
}
/** PF2e-specific source code array; preserve original order and unknown codes. */
function strings(source,path,concept) {
 const selected=at(source,path);
 if(!selected.present)return [{path:'/'+path,present:false,concept,limitations:[...LIMIT]}];
 if(!Array.isArray(selected.value))throw new TypeError(`Shield source /${path} must be an array.`);
 if(!selected.value.length)return [{path:'/'+path,present:true,value:[],concept,limitations:[...LIMIT]}];
 return selected.value.map((value,i)=>{
  if(typeof value!=='string')throw new TypeError(`Shield source /${path}/${i} must be a string.`);
  return {path:`/${path}/${i}`,present:true,value,concept,limitations:[...LIMIT]};
 });
}
/** PF2e-specific shield reinforcing rune source, without prepared reinforcement. */
function runes(source,path) {
 return object(source,path,'shield_runes',()=>[
  scalar(source,path+'/reinforcing','shield_rune_reinforcing','number')
 ]);
}
/** PF2e-specific integrated weapon source rune leaves, excluding prepared effects. */
function weaponRunes(source,path) {
 return object(source,path,'shield_integrated_weapon_runes',()=>[
  scalar(source,path+'/potency','shield_integrated_weapon_rune_potency','number'),
  scalar(source,path+'/striking','shield_integrated_weapon_rune_striking','number'),
  ...strings(source,path+'/property','shield_integrated_weapon_property_rune_code')
 ]);
}
/**
 * PF2e-specific ShieldSystemSource 8.6.1 primitive descriptors.
 * Source AC bonus, speed penalty and rune ranks remain authored values. No
 * raising, broken state, Shield Block, class reinforcement or attack computation.
 * Current integrated weapon source and specific baseline stay distinct. Missing,
 * null, zero and empty differ; unknown codes retain exact strings. Required
 * undefined rejects. No prepared usage, damageType, versatile.options or effects.
 */
export function shieldFields(source) {
 if(source?.type!=='shield')return null;
 const s=(path,concept,type,nullable=false)=>scalar(source,'system/'+path,'shield_'+concept,type,nullable);
 const fields=[s('acBonus','ac_bonus','number'),s('speedPenalty','speed_penalty','number'),
  s('grade','grade_code','string',true),...runes(source,'system/runes')];
 fields.push(...object(source,'system/specific','shield_specific_baseline',()=>[
  ...object(source,'system/specific/material','shield_specific_material',()=>[
   s('specific/material/type','specific_material_type_code','string',true),
   s('specific/material/grade','specific_material_grade_code','string',true)
  ]),...runes(source,'system/specific/runes'),
  ...object(source,'system/specific/integrated','shield_specific_integrated_weapon',()=>[
   ...weaponRunes(source,'system/specific/integrated/runes')
  ],true)
 ],true));
 fields.push(...object(source,'system/traits/integrated','shield_integrated_weapon',()=>[
  ...weaponRunes(source,'system/traits/integrated/runes'),
  ...object(source,'system/traits/integrated/versatile','shield_integrated_weapon_versatile',()=>[
   s('traits/integrated/versatile/selected','integrated_weapon_versatile_selected_damage_code','string')
  ],true)
 ],true));
 fields.push(...strings(source,'system/traits/value','shield_trait_code'),
  ...strings(source,'system/traits/otherTags','shield_other_tag_code'),
  s('traits/rarity','rarity_code','string'),s('slug','source_slug','string',true));
 for(const [key,type]of [['title','string'],['authors','string'],['license','string'],['remaster','boolean']])fields.push(s('publication/'+key,'publication_'+key,type));
 return fields;
}
