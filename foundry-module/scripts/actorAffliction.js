/**
 * PF2e-specific persisted affliction Item selector; tested PF2e8.6.1/core14.369.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/affliction/data.ts
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/abstract-effect/data.ts
 * Detached toObject(true) source only. No prepared stage clamp, expiry, clocks,
 * rolls, damage evaluation, condition application, UUID resolution or writes.
 */
const LIMIT=['persisted_source_not_effective_affliction_state'];
const TIME=['rounds','minutes','hours','days'];
const OPTIONAL=/^(onset|context|context\/origin\/(token|item|spellcasting|spellcasting\/tradition)|context\/target(?:\/token)?|context\/roll\/degreeOfSuccess|stages\/\d+\/(damage\/\d+\/category|conditions\/\d+\/(value|linked)))$/;
/** PF2e-specific own-source selection, preserving only schema-optional undefined as missing. */
function at(source,suffix) {
 let value=source;
 for(const key of ['system',...suffix.split('/')]) {
  if(value===null||typeof value!=='object'||!Object.hasOwn(value,key))return {present:false};
  value=value[key];
 }
 return value===undefined&&OPTIONAL.test(suffix)?{present:false}:{present:true,value};
}
/**
 * PF2e-specific primitive affliction leaves and exact empty/null/missing markers.
 * status.stage is a stored one-based ordinal; mapped stage_index is zero-based
 * only when an integer ordinal indexes an actually supplied source stage array.
 * Source progress and onset flags never establish current effective application.
 */
export function afflictionFields(source) {
 if(source?.type!=='affliction')return null;
 const fields=[];
 const marker=(suffix,selected,concept)=>{const row={path:'/system/'+suffix,...selected,concept,limitations:[...LIMIT]};fields.push(row);return row;};
 const add=(suffix,concept,type,nullable=false,choices=null)=>{
  const selected=at(source,suffix);
  if(selected.present&&!(nullable&&selected.value===null)&&
   (typeof selected.value!==type||(type==='number'&&!Number.isFinite(selected.value))||(choices&&!choices.includes(selected.value))))throw new TypeError(`Affliction source /system/${suffix} has an unexpected type or value; verify PF2e8.6.1 schema.`);
  return marker(suffix,selected,concept);
 };
 const container=(suffix,concept)=>{
  const selected=at(source,suffix);
  if(!selected.present||selected.value===null){marker(suffix,selected,concept);return false;}
  if(typeof selected.value!=='object'||Array.isArray(selected.value))throw new TypeError(`Affliction source /system/${suffix} must be an object or null.`);
  return true;
 };
 const array=(suffix,concept,visit)=>{
  const selected=at(source,suffix);
  if(!selected.present){marker(suffix,selected,concept);return;}
  if(!Array.isArray(selected.value))throw new TypeError(`Affliction source /system/${suffix} must be an array.`);
  if(!selected.value.length)marker(suffix,{present:true,value:[]},concept);
  selected.value.forEach((value,index)=>{
   if(visit){if(value===null||typeof value!=='object'||Array.isArray(value))throw new TypeError(`Affliction source /system/${suffix}/${index} must be an object.`);visit(`${suffix}/${index}`);}
   else add(`${suffix}/${index}`,concept,'string');
  });
 };
 add('level/value','affliction_level','number');
 if(fields[0].present&&!Number.isInteger(fields[0].value))throw new TypeError('Affliction source level must be an integer.');
 add('save/type','affliction_save_type','string',false,['fortitude','reflex','will']);add('save/value','affliction_save_dc','number');
 add('status/onset','affliction_source_onset','boolean');
 const stage=add('status/stage','affliction_source_stage','number');
 add('status/progress','affliction_source_progress','number');
 if(container('onset','affliction_onset')){add('onset/value','affliction_onset_value','number');add('onset/unit','affliction_onset_unit','string',false,TIME);}
 array('stages','affliction_stages',path=>{
  array(`${path}/damage`,'affliction_stage_damage',p=>{add(`${p}/formula`,'affliction_stage_damage_formula','string');add(`${p}/damageType`,'affliction_stage_damage_type','string');add(`${p}/category`,'affliction_stage_damage_category','string',true);});
  array(`${path}/conditions`,'affliction_stage_conditions',p=>{add(`${p}/slug`,'affliction_stage_condition_slug','string');add(`${p}/value`,'affliction_stage_condition_value','number',true);add(`${p}/linked`,'affliction_stage_condition_linked','boolean');});
  array(`${path}/effects`,'affliction_stage_effects',p=>add(`${p}/uuid`,'affliction_stage_effect_uuid','string'));
  add(`${path}/duration/value`,'affliction_stage_duration_value','number');add(`${path}/duration/unit`,'affliction_stage_duration_unit','string',false,[...TIME,'unlimited','encounter']);
 });
 if(stage.present){
  const stages=at(source,'stages'),known=stages.present&&Array.isArray(stages.value),resolved=known&&Number.isInteger(stage.value)&&stage.value>=1&&stage.value<=stages.value.length;
  stage.mapped_value={source_stage:stage.value,stage_index:resolved?stage.value-1:null,status:resolved?'resolved':known?'out_of_range':'unverified',stage_count:known?stages.value.length:null};
 }
 for(const [suffix,concept,type,nullable,choices]of [
  ['duration/value','affliction_duration_value','number'],['duration/unit','affliction_duration_unit','string',false,[...TIME,'unlimited','encounter']],['duration/expiry','affliction_duration_expiry','string',true,['turn-start','turn-end','round-end']],
  ['start/value','affliction_start_time','number'],['start/initiative','affliction_start_initiative','number',true],['fromSpell','affliction_from_spell','boolean'],['slug','source_slug','string',true]
 ])add(suffix,concept,type,nullable,choices);
 array('traits/value','affliction_trait_code');array('traits/otherTags','affliction_other_tag_code');
 if(container('context','affliction_context')){
  add('context/origin/actor','affliction_origin_actor_uuid','string');add('context/origin/token','affliction_origin_token_uuid','string',true);add('context/origin/item','affliction_origin_item_uuid','string',true);
  array('context/origin/rollOptions','affliction_origin_roll_option');
  if(container('context/origin/spellcasting','affliction_origin_spellcasting')){
   add('context/origin/spellcasting/attribute/type','affliction_origin_spellcasting_attribute','string',false,['str','dex','con','int','wis','cha']);add('context/origin/spellcasting/attribute/mod','affliction_origin_spellcasting_modifier','number');add('context/origin/spellcasting/tradition','affliction_origin_spellcasting_tradition','string',true);
  }
  if(container('context/target','affliction_target')){add('context/target/actor','affliction_target_actor_uuid','string');add('context/target/token','affliction_target_token_uuid','string',true);}
  if(container('context/roll','affliction_context_roll')){add('context/roll/total','affliction_context_roll_total','number');add('context/roll/degreeOfSuccess','affliction_context_roll_degree','number',true,[0,1,2,3]);}
 }
 for(const [key,type]of [['title','string'],['authors','string'],['license','string'],['remaster','boolean']])add(`publication/${key}`,`publication_${key}`,type);
 return fields;
}
