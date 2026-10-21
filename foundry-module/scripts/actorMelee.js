/**
 * PF2e-specific NPC attack Item source selector, audited8.6.1/core14.369.
 * Detached toObject(true) only; authored bonus/damage are not ability modifiers,
 * carried weapon statistics, effective elite/weak values or target calculations.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/melee/data.ts
 * No preparation, rolls, defaults, migration, imports or gameplay execution.
 */
const MODES={strike:'Strike','area-fire':'Area Fire','auto-fire':'Auto Fire'};
/** Standard JSON Pointer escaping; no system semantics or source derivation. */
const escapePointer=key=>key.replaceAll('~','~0').replaceAll('/','~1');

/** PF2e-specific MeleeSystemSource8.6.1 own-field lookup; no prepared values. */
function at(source,keys) {
  let value=source;
  for(const key of keys) {
    if(value===null||typeof value!=='object'||!Object.hasOwn(value,key))return {present:false};
    value=value[key];
  }
  return {present:true,value};
}

/** PF2e-specific MeleeSystemSource8.6.1 scalar source validation, no coercion. */
function field(source,keys,concept,type,nullable=false,limitations=[]) {
  const selected=at(source,keys);const path='/'+keys.map(escapePointer).join('/');
  if(selected.present&&!(nullable&&selected.value===null)&&(typeof selected.value!==type||(type==='number'&&!Number.isFinite(selected.value))))throw new TypeError(`NPC attack source field ${path} has an unexpected type.`);
  return {path,...selected,concept,limitations:[...limitations]};
}

/** PF2e-specific source8.6.1 optional range/area; preserve absent versus null. */
function optional(source,key,concept,children) {
  const selected=at(source,['system',key]);
  if(!selected.present||selected.value===null)return [{path:`/system/${key}`,...selected,concept,limitations:[]}];
  if(typeof selected.value!=='object'||Array.isArray(selected.value))throw new TypeError(`NPC attack source /system/${key} must be an object or null.`);
  return children.map(([name,label,type,nullable,limitations])=>field(source,['system',key,name],label,type,nullable,limitations));
}

/** PF2e-specific source8.6.1 trait/effect arrays; exact indexed strings only. */
function strings(source,keys,concept,limitations=[]) {
  const selected=at(source,keys);const path='/'+keys.map(escapePointer).join('/');
  if(!selected.present)return [{path,present:false,concept,limitations:[...limitations]}];
  if(!Array.isArray(selected.value))throw new TypeError(`NPC attack source ${path} must be an array.`);
  if(!selected.value.length)return [{path,present:true,value:[],concept,limitations:[...limitations]}];
  return selected.value.map((value,index)=>{
    if(typeof value!=='string')throw new TypeError(`NPC attack source ${path}/${index} must be a string.`);
    return {path:`${path}/${index}`,present:true,value,concept,limitations:[...limitations]};
  });
}

/** PF2e-specific MeleeSystemSource8.6.1 additional-effect labels only.
 * Source labels are not document UUIDs; relationship reads never resolve names.
 * Pinned schema: melee/data.ts linked at this module's implementation boundary.
 */
export function meleeEffectFields(source) {
  if(source?.type!=='melee')return null;
  return strings(source,['system','attackEffects','value'],'additional_effect_label',
    ['label_not_document_uuid','effect_definition_requires_separate_read']);
}

/**
 * PF2e-specific `melee` Item source8.6.1: action, bonus.value, area, range,
 * damageRolls keyed components, traits, attackEffects and subjectToMAP, plus
 * shared publication/slug. Schema/types link is in this module's boundary docs.
 * Only action=strike maps to Strike; ranged attacks remain ranged despite type.
 * Null range means no explicit source range; it cannot exclude thrown or other
 * prepared ranged context. Absent range stays unknown. Non-null
 * range emits ranged increment/max leaves, without deriving six increments.
 * Damage formulas/categories/codes are exact source; bleed is not automatically
 * rewritten persistent. Effect labels are not UUIDs. No implicit descriptions,
 * rule elements, material/runes preparation or linkedWeapon flags are read.
 * Empty []/{} markers preserve explicitly empty selected arrays/maps; otherwise
 * descriptors are primitive leaves with JSON-Pointer-escaped original map keys.
 */
export function meleeFields(source) {
  if(source?.type!=='melee')return null;
  const fields=[
    field(source,['system','action'],'attack_action','string'),
    field(source,['system','bonus','value'],'authored_attack_bonus','number',false,['source_bonus_not_ability_modifier_or_effective_attack']),
    field(source,['system','subjectToMAP'],'subject_to_multiple_attack_penalty','boolean',false,['penalty_not_calculated']),
    field(source,['system','slug'],'source_slug','string',true)
  ];
  if(fields[0].present) {
    fields[0].mapped_value=Object.hasOwn(MODES,fields[0].value)?MODES[fields[0].value]:fields[0].value;
    if(!Object.hasOwn(MODES,fields[0].value))fields[0].limitations.push('unknown_attack_action_preserved');
  }
  fields.push(...optional(source,'area','attack_area_source',[
    ['type','area_shape_code','string',false,[]],['value','area_size_feet','number',false,['source_area_not_target_selection']]
  ]));
  const range=optional(source,'range','attack_range_kind',[
    ['increment','ranged_increment_feet','number',true,['ranged_attack_source_context']],
    ['max','ranged_maximum_feet','number',true,['ranged_attack_source_context','maximum_not_derived_from_increment']]
  ]);
  if(range.length===1&&range[0].present&&range[0].value===null) {
    range[0].mapped_value='no_explicit_range';
    range[0].limitations.push('source_null_range_does_not_exclude_trait_derived_ranged_attacks');
  }
  fields.push(...range);
  fields.push(...strings(source,['system','traits','value'],'npc_attack_trait_code',['code_preserved_without_unverified_label_lookup']),
    ...strings(source,['system','traits','otherTags'],'npc_attack_other_tag_code'),
    ...meleeEffectFields(source));
  const damage=at(source,['system','damageRolls']);
  if(!damage.present)fields.push({path:'/system/damageRolls',present:false,concept:'damage_components',limitations:[]});
  else {
    if(damage.value===null||typeof damage.value!=='object'||Array.isArray(damage.value))throw new TypeError('NPC attack source /system/damageRolls must be a record.');
    const keys=Object.keys(damage.value);
    if(!keys.length)fields.push({path:'/system/damageRolls',present:true,value:{},concept:'damage_components',limitations:[]});
    for(const key of keys) {
      const component=damage.value[key];
      if(component===null||typeof component!=='object'||Array.isArray(component))throw new TypeError('NPC attack damage component must be an object.');
      for(const [leaf,concept,nullable]of [['damage','damage_formula',false],['damageType','damage_type_code',false],['category','damage_category_code',true]])fields.push(field(source,['system','damageRolls',key,leaf],concept,'string',nullable,['authored_damage_component_not_calculated_total']));
    }
  }
  for(const [key,type]of [['title','string'],['authors','string'],['license','string'],['remaster','boolean']])fields.push(field(source,['system','publication',key],`publication_${key}`,type));
  return fields;
}
