/**
 * PF2e-specific weapon Item source selector, audited against 8.6.1.
 * Detached Item.toObject(true) only; no effective Strike, rune effects, ammunition
 * hydration, formula execution, attack totals or prepared trait interpretation.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/weapon/data.ts
 * Shared physicalFields supplies baseItem, material, usage.value, held hands,
 * quantity and attachments. This selector supplies traits, slug and publication.
 */
const LIMIT=['source_only_no_effective_strike_calculation'];
/** PF2e-specific 8.6.1 own source lookup; optional undefined alone means absent. */
function at(source,path,optional=false) {
 let value=source;
 for(const key of path.split('/')) {
  if(value===null||typeof value!=='object'||!Object.hasOwn(value,key))return {present:false};
  value=value[key];
 }
 return optional&&value===undefined?{present:false}:{present:true,value};
}
/** PF2e-specific weapon source scalar; no defaults, coercion or code rewriting. */
function scalar(source,path,concept,type,nullable=false,optional=false) {
 const selected=at(source,path,optional);
 if(selected.present&&!(nullable&&selected.value===null)&&(typeof selected.value!==type||(type==='number'&&!Number.isFinite(selected.value))))throw new TypeError(`Weapon source /${path} has an unexpected type.`);
 return {path:'/'+path,...selected,concept,limitations:[...LIMIT]};
}
/** PF2e-specific source object boundary retains missing/null/empty distinctly. */
function object(source,path,concept,children,nullable=false,optional=false) {
 const selected=at(source,path,optional);
 if(!selected.present||nullable&&selected.value===null)return [{path:'/'+path,...selected,concept,limitations:[...LIMIT]}];
 if(selected.value===null||typeof selected.value!=='object'||Array.isArray(selected.value))throw new TypeError(`Weapon source /${path} must be an object${nullable?' or null':''}.`);
 if(!Object.keys(selected.value).length)return [{path:'/'+path,present:true,value:{},concept,limitations:[...LIMIT]}];
 return children();
}
/** PF2e-specific source code array; preserve original order and unknown codes. */
function strings(source,path,concept,optional=false) {
 const selected=at(source,path,optional);
 if(!selected.present)return [{path:'/'+path,present:false,concept,limitations:[...LIMIT]}];
 if(!Array.isArray(selected.value))throw new TypeError(`Weapon source /${path} must be an array.`);
 if(!selected.value.length)return [{path:'/'+path,present:true,value:[],concept,limitations:[...LIMIT]}];
 return selected.value.map((value,i)=>{
  if(typeof value!=='string')throw new TypeError(`Weapon source /${path}/${i} must be a string.`);
  return {path:`/${path}/${i}`,present:true,value,concept,limitations:[...LIMIT]};
 });
}
/** PF2e-specific 8.6.1 weapon source rune leaves, never prepared runes.effects. */
function runes(source,path) {
 return object(source,path,'weapon_runes',()=>[
  scalar(source,path+'/potency','weapon_rune_potency','number'),
  scalar(source,path+'/striking','weapon_rune_striking','number'),
  ...strings(source,path+'/property','weapon_property_rune_code')
 ]);
}
/**
 * PF2e-specific WeaponSystemSource 8.6.1 primitive descriptors.
 * Codes remain exact strings; finite source numbers are retained without deriving
 * ranges, dice, reload cost, damage or potency bonuses. selectedAmmoId is only an
 * authored local identifier, never proof of an existing/readable ammunition Item.
 * Optional undefined applies only to schema-optional fields; missing, nullable and
 * empty object/array markers remain distinct. No flags/descriptions/rules read.
 */
export function weaponFields(source) {
 if(source?.type!=='weapon')return null;
 const s=(path,concept,type,nullable=false,optional=false)=>scalar(source,'system/'+path,'weapon_'+concept,type,nullable,optional);
 const fields=[
  s('category','category_code','string'),s('group','group_code','string',true),
  s('damage/dice','damage_dice','number'),s('damage/die','damage_die_code','string',true),
  s('damage/damageType','damage_type_code','string'),s('damage/modifier','damage_modifier','number'),
  s('range','range_feet','number',true),s('maxRange','max_range_feet','number',true,true),
  s('reload/value','reload_code','string',true),s('expend','expend','number',true,true),
  s('selectedAmmoId','selected_ammo_local_id','string',true),
  s('bonus/value','bonus','number'),s('splashDamage/value','splash_damage','number'),
  s('attribute','attribute_code','string',true,true),s('grade','grade_code','string',true),
  s('graspingAppendage','grasping_appendage','boolean',false,true),
  s('usage/canBeAmmo','can_be_ammo','boolean',false,true)
 ];
 fields.push(...object(source,'system/damage/persistent','weapon_persistent_damage',()=>[
  s('damage/persistent/number','persistent_damage_number','number'),
  s('damage/persistent/faces','persistent_damage_faces','number',true),
  s('damage/persistent/type','persistent_damage_type_code','string')
 ],true));
 fields.push(...object(source,'system/ammo','weapon_ammunition',()=>[
  s('ammo/builtIn','ammo_built_in','boolean'),s('ammo/baseType','ammo_base_type_code','string',true),s('ammo/capacity','ammo_capacity','number',true)
 ],true),...runes(source,'system/runes'));
 fields.push(...object(source,'system/meleeUsage','weapon_melee_usage',()=>[
  s('meleeUsage/damage/type','melee_damage_type_code','string'),s('meleeUsage/damage/die','melee_damage_die_code','string'),
  s('meleeUsage/group','melee_group_code','string'),...strings(source,'system/meleeUsage/traits','weapon_melee_trait_code',true),
  ...object(source,'system/meleeUsage/traitToggles','weapon_melee_trait_toggles',()=>[
   s('meleeUsage/traitToggles/modular','melee_modular_selected','number',true),s('meleeUsage/traitToggles/versatile','melee_versatile_selected_code','string',true)
  ],false,true)
 ],false,true));
 fields.push(...object(source,'system/traits/toggles','weapon_trait_toggles',()=>[
  ...object(source,'system/traits/toggles/doubleBarrel','weapon_double_barrel_toggle',()=>[s('traits/toggles/doubleBarrel/selected','double_barrel_selected','boolean')],false,true),
  ...object(source,'system/traits/toggles/modular','weapon_modular_toggle',()=>[s('traits/toggles/modular/selected','modular_selected','number',true)],true,true),
  ...object(source,'system/traits/toggles/versatile','weapon_versatile_toggle',()=>[s('traits/toggles/versatile/selected','versatile_selected_code','string',true)],false,true)
 ],false,true));
 fields.push(...object(source,'system/specific','weapon_specific_baseline',()=>[
  ...object(source,'system/specific/material','weapon_specific_material',()=>[
   s('specific/material/type','specific_material_type_code','string',true),s('specific/material/grade','specific_material_grade_code','string',true)
  ]),...runes(source,'system/specific/runes')
 ],true));
 fields.push(...strings(source,'system/traits/value','weapon_trait_code'),
  ...strings(source,'system/traits/otherTags','weapon_other_tag_code'),
  s('traits/rarity','rarity_code','string'),s('slug','source_slug','string',true));
 for(const [key,type]of [['title','string'],['authors','string'],['license','string'],['remaster','boolean']])fields.push(s('publication/'+key,'publication_'+key,type));
 return fields;
}
