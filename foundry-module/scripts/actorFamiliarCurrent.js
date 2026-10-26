/**
 * PF2e-specific familiar current document-data selector, tested contract
 * Foundry14.369/PF2e8.6.1. Public Actor.system own-data boundary:
 * https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.ActorData.html#system
 * Pinned FamiliarSystemData explicitly declares CreatureAttributes, saves,
 * Perception, movement and SkillData (source excludes these derived fields):
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/familiar/data.ts
 * Shared contracts actor/creature/data.ts, actor/data/base.ts and
 * system/statistic/data.ts at that revision. Caller must first permission-resolve
 * the familiar's master; this pure helper calls no APIs or runtime getters and
 * neither recalculates from master source nor invents independent attributes.
 */
const LIMIT=['familiar_value_not_recalculated'];
const escape=key=>key.replaceAll('~','~0').replaceAll('/','~1');

/** PF2e-specific own-data lookup, preserving absent/undefined without fallback. */
function selected(serialized,keys){
 let value=serialized;
 for(const key of keys){
  if(value===null||typeof value!=='object'||Array.isArray(value))throw new TypeError('Familiar current field has a malformed container.');
  const descriptor=Object.getOwnPropertyDescriptor(value,key);if(!descriptor)return {present:false};
  if(!Object.hasOwn(descriptor,'value'))throw new TypeError('Familiar current fields require own data properties.');
  value=descriptor.value;if(value===undefined)return {present:false};
 }
 return {present:true,value};
}

/**
 * PF2e-specific familiar current primitives from guarded {type,system} model
 * context. Returns null for other subtypes, otherwise {fields,reasons}. Own data on nonplain
 * containers is accepted; selected accessors reject without invocation and
 * inherited leaves stay absent. Missing fields never use source/master fallback.
 * Ordinary skills are bounded to 512 own keys of 1–256 Unicode code points;
 * Lore or nonempty itemId claims withhold the entire key before labels or totals.
 * No rank, attack, normal Strike, independent attribute or resource is inferred.
 * At most 24000 fields. Every response remains partial.
 */
export function familiarCurrentFields(serialized){
 if(selected(serialized,['type']).value!=='familiar')return null;
 const fields=[],reasons=new Set(['other_statistics_pending']);
 /** PF2e-specific selected scalar admission, no derived arithmetic. */
 const add=(keys,concept,type,nullable=false,literal)=>{
  const result=selected(serialized,['system',...keys]),path='/system/'+keys.map(escape).join('/');
  if(result.present&&!(nullable&&result.value===null)&&(typeof result.value!==type||type==='number'&&!Number.isFinite(result.value)))throw new TypeError(`Familiar current field ${path} has an unexpected value.`);
  if(result.present&&literal!==undefined&&result.value!==literal)throw new TypeError(`Familiar current field ${path} has an unexpected literal.`);
  if(!result.present)reasons.add('current_fields_unavailable');
  fields.push({path,...result,concept,limitations:[...LIMIT]});if(fields.length>24000)throw new TypeError('Familiar current fields exceed 24000 records.');
 };
 for(const [leaf,concept,type]of [['value','current_armor_class','number'],['breakdown','current_armor_class_breakdown','string'],['details','current_armor_class_exception_notes','string']])add(['attributes','ac',leaf],concept,type);
 for(const [leaf,concept]of [['value','current_hit_points'],['max','current_maximum_hit_points'],['temp','current_temporary_hit_points']])add(['attributes','hp',leaf],concept,'number');
 for(const save of ['fortitude','reflex','will'])for(const [leaf,suffix,type]of [['value','modifier','number'],['totalModifier','total_modifier','number'],['breakdown','breakdown','string']])add(['saves',save,leaf],`current_${save}_save_${suffix}`,type);
 for(const [leaf,concept,type]of [['value','current_perception_modifier','number'],['totalModifier','current_perception_total_modifier','number'],['breakdown','current_perception_breakdown','string'],['vision','current_standard_vision','boolean']])add(['perception',leaf],concept,type);
 for(const mode of ['land','burrow','climb','fly','swim','travel']){
  const keys=['movement','speeds',mode],root=selected(serialized,['system',...keys]);
  if(!['land','travel'].includes(mode)&&root.present&&root.value===null){add(keys,`current_${mode}_movement`,'object',true);continue;}
  for(const [leaf,suffix,type]of [['value','speed','number'],['base','base_speed','number'],['type','movement_type','string'],['source','movement_source_label','string']])add([...keys,leaf],`current_${mode}_${suffix}`,type,leaf==='source',leaf==='type'?mode:undefined);
 }
 const skills=selected(serialized,['system','skills']);
 if(!skills.present){fields.push({path:'/system/skills',present:false,concept:'current_skill_collection',limitations:[...LIMIT]});reasons.add('current_fields_unavailable');}
 else{
  if(skills.value===null||typeof skills.value!=='object'||Array.isArray(skills.value))throw new TypeError('Familiar current skills must be an own-data map.');
  const keys=Object.getOwnPropertyNames(skills.value);if(keys.length>512)throw new TypeError('Familiar current skills exceed 512 keys.');
  if(!keys.length)fields.push({path:'/system/skills',present:true,value:{},concept:'current_skill_collection',limitations:[...LIMIT]});
  for(const key of keys){
   if([...key].length<1||[...key].length>256)throw new TypeError('Familiar current skill keys must contain 1–256 code points.');
   const prefix=['system','skills',key],lore=selected(serialized,[...prefix,'lore']),itemId=selected(serialized,[...prefix,'itemId']);
   if(lore.present&&typeof lore.value!=='boolean'||itemId.present&&itemId.value!==null&&typeof itemId.value!=='string')throw new TypeError('Familiar current skill item metadata is malformed.');
   if(lore.value===true||typeof itemId.value==='string'&&itemId.value!==''){reasons.add('familiar_item_linked_skills_unsupported');continue;}
   for(const [leaf,type]of [['slug','string'],['label','string'],['value','number'],['totalModifier','number'],['dc','number'],['breakdown','string']])add(['skills',key,leaf],`current_skill_${leaf==='totalModifier'?'total_modifier':leaf}`,type);
  }
 }
 return {fields,reasons:[...reasons].sort()};
}
