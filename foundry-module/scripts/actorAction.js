/**
 * PF2e-specific action Item source selection, audited PF2e8.6.1/core14.369.
 * Input is detached toObject(true), never prepared actionCost/frequency getters.
 * Source contract: AbilitySystemData.defineSchema/AbilitySystemSource:
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/ability/data.ts
 * Shared publication/slug fields: ../base/data/model.ts at the same revision.
 * No action execution, source mutation, effect resolution or effective maths.
 */
const REVISION='https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/';
const ACTIVATION={action:'action_or_activity',reaction:'reaction',free:'free_action',passive:'passive_ability'};
// PF2e-specific AbilitySystemData8.6.1 defines these optional fields with
// initial:undefined. Own undefined is absent serialized source, not a default.
const OPTIONAL_UNDEFINED=new Set(['/system/deathNote','/system/frequency','/system/frequency/value','/system/selfEffect']);

/** PF2e-specific selected AbilitySystemSource8.6.1 path lookup, source only. */
function valueAt(source,path) {
  let value=source;
  for(const key of path.split('/').filter(Boolean)) {
    if(value===null||typeof value!=='object'||!Object.hasOwn(value,key))return {present:false};
    value=value[key];
  }
  return value===undefined&&OPTIONAL_UNDEFINED.has(path)?{present:false}:{present:true,value};
}

/** PF2e-specific primitive AbilitySystemSource8.6.1 validation, no defaults. */
function field(source,path,concept,type,nullable=false,limitations=[]) {
  const selected=valueAt(source,path);
  if(selected.present&&!(nullable&&selected.value===null)
      &&(typeof selected.value!==type||(type==='number'&&!Number.isFinite(selected.value))))throw new TypeError(`Action source field ${path} has an unexpected type.`);
  return {path,...selected,concept,limitations:[...limitations]};
}

/** PF2e-specific stored trait arrays in AbilitySystemSource8.6.1, no derivation. */
function arrayFields(source,path,concept) {
  const selected=valueAt(source,path);
  if(!selected.present)return [{path,present:false,concept,limitations:[]}];
  if(!Array.isArray(selected.value))throw new TypeError(`Action source field ${path} must be an array.`);
  if(!selected.value.length)return [{path,present:true,value:[],concept,limitations:[]}];
  return selected.value.map((value,index)=>{
    if(typeof value!=='string')throw new TypeError(`Action source field ${path}/${index} must be a string.`);
    return {path:`${path}/${index}`,present:true,value,concept,limitations:['code_preserved_without_unverified_label_lookup']};
  });
}

/** PF2e-specific optional frequency/selfEffect source8.6.1, never prepared state. */
function optionalObject(source,path,concept,children) {
  const selected=valueAt(source,path);
  if(!selected.present||selected.value===null)return [{path,...selected,concept,limitations:['source_presence_not_effective_availability']}];
  if(typeof selected.value!=='object'||Array.isArray(selected.value))throw new TypeError(`Action source field ${path} must be an object or null.`);
  return children.map(([key,label,type,limitations])=>field(source,`${path}/${key}`,label,type,false,limitations??[]));
}

/** PF2e-specific AbilitySystemSource8.6.1 selfEffect-only source selection.
 * Keeps explicit relationship reads independent of unrequested action fields.
 * Reference schema: ability/data.ts at REVISION; no hydration or defaults.
 */
export function actionReferenceFields(source) {
  if(source?.type!=='action')return null;
  return optionalObject(source,'/system/selfEffect','self_effect_source',[
    ['uuid','self_effect_uuid','string',['unverified_reference_not_applied_or_hydrated']],
    ['name','self_effect_name','string',['stored_reference_name_not_verified_target_name']]
  ]);
}

/**
 * PF2e-specific `action` fields: activation discriminator/count, category,
 * deathNote, frequency, selfEffect, trait arrays, publication and slug, per
 * AbilitySystemSource8.6.1 and ItemSystemSchema8.6.1 (REVISION above).
 * Source values remain exact; frequency.value is never initialized from max.
 * Null counts never imply free actions. Familiar category is an ability category,
 * not proof of a familiar/master relationship or active selected benefit.
 * Optional mapped_value translates only known activation codes; unknown codes
 * are preserved. Action/activity distinction and trigger/requirements need prose.
 * Other source fields, toggles, rules and descriptions are not implicitly read.
 * Returns null for non-action types, otherwise primitive descriptor records;
 * [] is used only to represent an explicitly empty selected source array.
 * Schema URL: {@link REVISION}src/module/item/ability/data.ts
 */
export function actionFields(source) {
  if(source?.type!=='action')return null;
  const fields=[
    field(source,'/system/actionType/value','activation_kind','string',false,['trigger_requirements_and_activity_details_require_description']),
    field(source,'/system/actions/value','action_count','number',true,['count_does_not_determine_activation_kind']),
    field(source,'/system/category','ability_category_code','string',true),
    field(source,'/system/deathNote','death_note_source_flag','boolean',false,['source_flag_not_frequency_or_death_state']),
    field(source,'/system/slug','source_slug','string',true)
  ];
  const activation=fields[0];
  if(activation.present) {
    activation.mapped_value=Object.hasOwn(ACTIVATION,activation.value)?ACTIVATION[activation.value]:activation.value;
    if(!Object.hasOwn(ACTIVATION,activation.value))activation.limitations.push('unknown_activation_code_preserved');
  }
  fields.push(...arrayFields(source,'/system/traits/value','ability_trait_code'),...arrayFields(source,'/system/traits/otherTags','ability_other_tag_code'));
  fields.push(...optionalObject(source,'/system/frequency','frequency_source',[
    ['value','recorded_frequency_remaining','number',['source_only_not_initialized_or_castability']],
    ['max','frequency_maximum','number',['source_only_not_current_availability']],
    ['per','frequency_interval_code','string',['interval_code_preserved']]
  ]));
  fields.push(...actionReferenceFields(source));
  for(const [key,type]of [['title','string'],['authors','string'],['license','string'],['remaster','boolean']])fields.push(field(source,`/system/publication/${key}`,`publication_${key}`,type));
  return fields;
}
