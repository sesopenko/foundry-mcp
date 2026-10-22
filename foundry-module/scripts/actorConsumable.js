/**
 * PF2e-specific ConsumableSystemSource selector, audited against PF2e 8.6.1.
 * Detached Item.toObject(true) source only; physicalFields supplies quantity and
 * usage. No consumption, formula evaluation, casting or actor benefits are applied.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/consumable/data.ts
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/spell/data.ts
 */
import {spellFields,spellDescriptionFields} from './actorSpell.js';
const LIMIT=['source_only_no_consumable_use_or_spell_application'];
/** PF2e-specific own source lookup; missing differs from explicit undefined. */
function at(source,path) {
 let value=source;
 for(const key of path.split('/')) {
  if(value===null||typeof value!=='object'||!Object.hasOwn(value,key))return {present:false};
  value=value[key];
 }
 return {present:true,value};
}
/** PF2e-specific primitive source descriptor without coercion or defaults. */
function scalar(source,path,concept,type,nullable=false) {
 const selected=at(source,path);
 if(selected.present&&!(nullable&&selected.value===null)&&(typeof selected.value!==type||(type==='number'&&!Number.isFinite(selected.value))))throw new TypeError(`Consumable source /${path} has an unexpected type.`);
 return {path:'/'+path,...selected,concept:'consumable_'+concept,limitations:[...LIMIT]};
}
/** PF2e-specific trait arrays retain source order, unknown codes and empty markers. */
function strings(source,path,concept) {
 const selected=at(source,path);
 if(!selected.present)return [{path:'/'+path,present:false,concept:'consumable_'+concept,limitations:[...LIMIT]}];
 if(!Array.isArray(selected.value))throw new TypeError(`Consumable source /${path} must be an array.`);
 if(!selected.value.length)return [{path:'/'+path,present:true,value:[],concept:'consumable_'+concept,limitations:[...LIMIT]}];
 return selected.value.map((value,i)=>{
  if(typeof value!=='string')throw new TypeError(`Consumable source /${path}/${i} must be a string.`);
  return {path:`/${path}/${i}`,present:true,value,concept:'consumable_'+concept,limitations:[...LIMIT]};
 });
}
/** PF2e-specific nullable structured source selection; never emit nested source. */
function structured(source,path,concept,leaves) {
 const selected=at(source,path);
 if(!selected.present||selected.value===null)return [{path:'/'+path,...selected,concept:'consumable_'+concept,limitations:[...LIMIT]}];
 if(typeof selected.value!=='object'||Array.isArray(selected.value))throw new TypeError(`Consumable source /${path} must be an object or null.`);
 return leaves.map(([key,name,type])=>scalar(source,path+'/'+key,name,type));
}
/**
 * PF2e-specific consumable source primitives, including bounded contained-Spell
 * identity and authored base rank only. A contained SpellSource is not an independent
 * document UUID or proof of cast rank. Additional mechanics are selected separately
 * by consumableSpellFields. Healing/damage kind remains exact, never inferred.
 * No rule elements, nested spell mechanics, descriptions or prepared getters read.
 */
export function consumableFields(source) {
 if(source?.type!=='consumable')return null;
 const s=(path,concept,type,nullable=false)=>scalar(source,'system/'+path,concept,type,nullable);
 const fields=[s('category','category_code','string'),s('uses/value','uses_value','number'),s('uses/max','uses_max','number'),s('uses/autoDestroy','uses_auto_destroy','boolean'),
  ...structured(source,'system/damage','damage_healing',[['formula','damage_formula','string'],['type','damage_type_code','string'],['kind','damage_kind_code','string']]),
  ...structured(source,'system/spell','contained_spell',[['_id','contained_spell_id','string'],['name','contained_spell_name','string'],['type','contained_spell_type','string'],['system/level/value','contained_spell_base_rank','number']]),
  ...strings(source,'system/traits/value','trait_code'),...strings(source,'system/traits/otherTags','other_tag_code'),s('traits/rarity','rarity_code','string'),s('slug','source_slug','string',true)];
 const spellType=fields.find(field=>field.path==='/system/spell/type');
 if(spellType?.present&&spellType.value!=='spell')throw new TypeError('Consumable source /system/spell/type must be spell.');
 for(const [key,type]of [['title','string'],['authors','string'],['license','string'],['remaster','boolean']])fields.push(s('publication/'+key,'publication_'+key,type));
 return fields;
}
/**
 * PF2e-specific contained SpellSource boundary for consumable Items, PF2e 8.6.1.
 * Uses own detached source fields only; no UUID, casting entry or prepared getter.
 * The consumable schema permits a null spell template. Missing identity is retained
 * by consumableFields rather than invented here. Schema links are at file boundary.
 */
function containedSpell(source) {
 if(source?.type!=='consumable')return null;
 const selected=at(source,'system/spell');
 if(!selected.present||selected.value===null)return null;
 const value=selected.value;
 if(!value||typeof value!=='object'||Array.isArray(value))throw new TypeError('Consumable source /system/spell must be an object or null.');
 if(Object.hasOwn(value,'type')&&value.type!=='spell')throw new TypeError('Consumable source /system/spell/type must be spell.');
 const system=Object.hasOwn(value,'system')?value.system:{};
 if(!system||typeof system!=='object'||Array.isArray(system))throw new TypeError('Consumable source /system/spell/system must be an object.');
 return {type:'spell',system};
}
/** PF2e-specific contained spell error provenance; preserve the shared selector's
 * validation while naming the actual consumable source path, not a detached root.
 */
function selectContained(spell,selector) {
 try {return selector(spell);}
 catch(error) {
  if(error instanceof TypeError)throw new TypeError(error.message.replace(/^(Spell source )\/system(?=\/| )/,'$1/system/spell/system'));
  throw error;
 }
}
/**
 * PF2e-specific contained consumable spell source fields, PF2e 8.6.1 schema linked
 * above. Reuses the full spell recursive allowlist and guards without casting or
 * applying variants. Paths retain the containing consumable as provenance; these
 * descriptors use pf2e.spell.source.v1. Root base rank is already supplied by the
 * four consumable identity/rank descriptors and is excluded to avoid duplication.
 */
export function consumableSpellFields(source) {
 const spell=containedSpell(source);
 return spell?selectContained(spell,spellFields).filter(field=>field.path!=='/system/level/value').map(field=>({...field,path:'/system/spell'+field.path})):[];
}
/**
 * PF2e-specific exact contained spell prose for explicit consumable description
 * reads, PF2e 8.6.1 schema linked above. Root, fixed-layer and overlay descriptions
 * retain source paths and Unicode unchanged; no HTML enrichment or execution.
 */
export function consumableSpellDescriptionFields(source) {
 const spell=containedSpell(source);
 return spell?selectContained(spell,spellDescriptionFields).map(field=>({...field,path:'/system/spell'+field.path})):[];
}
