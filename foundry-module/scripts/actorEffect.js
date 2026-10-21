/**
 * PF2e-specific persisted `effect` Item selector; audited PF2e8.6.1/core14.369.
 * Source contract (never prepared badge/expired data):
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/effect/data.ts
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/abstract-effect/data.ts
 * Accepts detached toObject(true) source. No document APIs, writes, clocks,
 * formula evaluation, reference resolution, flags or effective-state getters.
 */
const EVENTS=['initiative-roll','turn-start','turn-end'];
const SOURCE_LIMIT=['persisted_source_not_effective_or_expiration_state'];
const OPTIONAL_PATHS=new Set(['badge/labels','badge/loop','badge/evaluate','badge/reevaluate/initial','context','context/origin/token','context/origin/item','context/origin/spellcasting','context/origin/spellcasting/tradition','context/target','context/target/token','context/roll/degreeOfSuccess']);
/** PF2e-specific own-source lookup; missing fields receive no schema defaults. */
function at(source,keys) {
 let value=source;
 for(const key of keys) {
  if(value===null||typeof value!=='object'||!Object.hasOwn(value,key))return {present:false};
  value=value[key];
 }
 if(value===undefined&&OPTIONAL_PATHS.has(keys.slice(1).join('/')))return {present:false};
 return {present:true,value};
}
/** PF2e-specific primitive descriptor; rejects malformed selected source values. */
function leaf(source,keys,concept,type,nullable=false,choices=null) {
 const selected=at(source,keys),path='/'+keys.join('/');
 if(selected.present&&!(nullable&&selected.value===null)) {
  if(typeof selected.value!==type||(type==='number'&&!Number.isFinite(selected.value))||(choices&&!choices.includes(selected.value)))throw new TypeError(`Effect source field ${path} has an unexpected type or value; verify the PF2e8.6.1 source schema.`);
 }
 return {path,...selected,concept,limitations:[...SOURCE_LIMIT]};
}
/**
 * PF2e-specific effect schema primitive leaves, discriminated badge children and
 * explicit null/missing/empty markers. UUIDs and codes remain exact source text;
 * neither reference validity nor remaining duration/roll totals are inferred.
 * Unknown badge discriminator throws rather than silently dropping new schemas.
 */
export function effectFields(source) {
 if(source?.type!=='effect')return null;
 const fields=[];
 const add=(suffix,concept,type,nullable=false,choices=null)=>fields.push(leaf(source,['system',...suffix.split('/')],concept,type,nullable,choices));
 // PF2e-specific nullable schema containers are emitted only as null/missing.
 const container=(suffix,concept)=>{
  const selected=at(source,['system',...suffix.split('/')]),path='/system/'+suffix;
  if(!selected.present||selected.value===null) {fields.push({path,...selected,concept,limitations:[...SOURCE_LIMIT]});return false;}
  if(typeof selected.value!=='object'||Array.isArray(selected.value))throw new TypeError(`Effect source container ${path} must be an object or null.`);
  return true;
 };
 const strings=(suffix,concept,nullable=false)=>{
  const selected=at(source,['system',...suffix.split('/')]),path='/system/'+suffix;
  if(!selected.present||(nullable&&selected.value===null)) {fields.push({path,...selected,concept,limitations:[...SOURCE_LIMIT]});return;}
  if(!Array.isArray(selected.value))throw new TypeError(`Effect source ${path} must be a string array${nullable?' or null':''}.`);
  if(!selected.value.length)fields.push({path,present:true,value:[],concept,limitations:[...SOURCE_LIMIT]});
  selected.value.forEach((value,index)=>{
   if(typeof value!=='string')throw new TypeError(`Effect source ${path}/${index} must be a string.`);
   fields.push({path:`${path}/${index}`,present:true,value,concept,limitations:[...SOURCE_LIMIT]});
  });
 };
 for(const [path,concept,type,nullable,choices]of [
  ['level/value','effect_level','number'],['duration/value','effect_duration_value','number'],
  ['duration/unit','effect_duration_unit','string',false,['rounds','minutes','hours','days','unlimited','encounter']],
  ['duration/expiry','effect_duration_expiry','string',true,['turn-start','turn-end','round-end']],
  ['duration/sustained','effect_sustained','boolean'],['start/value','effect_start_time','number'],
  ['start/initiative','effect_start_initiative','number',true],['tokenIcon/show','effect_token_icon_show','boolean'],
  ['unidentified','effect_unidentified','boolean'],['fromSpell','effect_from_spell','boolean'],['slug','source_slug','string',true]
 ])add(path,concept,type,nullable,choices);
 const level=fields[0];
 if(level.present&&!Number.isInteger(level.value))throw new TypeError('Effect source level must be an integer.');
 const duration=fields[1];
 if(duration.present&&duration.value< -1)throw new TypeError('Effect source duration value must be at least -1.');
 strings('traits/value','effect_trait_code');strings('traits/otherTags','effect_other_tag_code');
 if(container('badge','effect_badge')) {
  const badge=source.system.badge;
  if(!['counter','value','formula'].includes(badge.type))throw new TypeError('Effect source /system/badge/type must be counter, value or formula; verify the source schema before reading this badge.');
  add('badge/type','effect_badge_type','string',false,['counter','value','formula']);
  strings('badge/labels','effect_badge_label',true);
  add('badge/value','effect_badge_value',badge.type==='formula'?'string':'number');
  if(badge.type==='counter') {
   add('badge/min','effect_badge_min','number',true);add('badge/max','effect_badge_max','number',true);add('badge/loop','effect_badge_loop','boolean');
   for(const field of fields.filter(field=>['/system/badge/min','/system/badge/max'].includes(field.path)))if(field.present&&field.value!==null&&!Number.isInteger(field.value))throw new TypeError(`Effect source ${field.path} must be an integer or null.`);
  } else if(badge.type==='formula') {
   add('badge/evaluate','effect_badge_evaluate','boolean');add('badge/reevaluate','effect_badge_reevaluate_event','string',true,EVENTS);
  } else if(container('badge/reevaluate','effect_badge_reevaluate')) {
   add('badge/reevaluate/event','effect_badge_reevaluate_event','string',false,EVENTS);
   add('badge/reevaluate/formula','effect_badge_reevaluate_formula','string');add('badge/reevaluate/initial','effect_badge_reevaluate_initial','number');
  }
 }
 if(container('context','effect_context')) {
  add('context/origin/actor','effect_origin_actor_uuid','string');add('context/origin/token','effect_origin_token_uuid','string',true);add('context/origin/item','effect_origin_item_uuid','string',true);
  strings('context/origin/rollOptions','effect_origin_roll_option');
  if(container('context/origin/spellcasting','effect_origin_spellcasting')) {
   add('context/origin/spellcasting/attribute/type','effect_origin_spellcasting_attribute','string',false,['str','dex','con','int','wis','cha']);
   add('context/origin/spellcasting/attribute/mod','effect_origin_spellcasting_modifier','number');
   add('context/origin/spellcasting/tradition','effect_origin_spellcasting_tradition','string',true);
  }
  if(container('context/target','effect_target')) {
   add('context/target/actor','effect_target_actor_uuid','string');add('context/target/token','effect_target_token_uuid','string',true);
  }
  if(container('context/roll','effect_context_roll')) {
   add('context/roll/total','effect_context_roll_total','number');add('context/roll/degreeOfSuccess','effect_context_roll_degree','number',true,[0,1,2,3]);
  }
 }
 for(const [key,type]of [['title','string'],['authors','string'],['license','string'],['remaster','boolean']])add(`publication/${key}`,`publication_${key}`,type);
 return fields;
}
