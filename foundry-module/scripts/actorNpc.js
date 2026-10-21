/**
 * PF2e-specific NPC source selectors; tested boundary core14.369/PF2e8.6.1.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/npc/data.ts
 * Shared contracts: actor/creature/data.ts, actor/data/base.ts, actor/data/iwr.ts
 * at the same immutable revision. Detached toObject(true) data only. Authored
 * statistics are not complete effective/current bonuses; no preparation, rolls,
 * labels from CONFIG, elite/weak arithmetic, predicate evaluation or writes.
 */
const escapePointer=key=>key.replaceAll('~','~0').replaceAll('/','~1');
/** PF2e-specific own source-field lookup; undefined optional fields stay absent. */
function at(source,keys) {
 let value=source;
 for(const key of keys){if(value===null||typeof value!=='object'||!Object.hasOwn(value,key)||value[key]===undefined)return {present:false};value=value[key];}
 return {present:true,value};
}
/** PF2e-specific primitive source descriptor; no coercion or prepared defaults. */
function scalar(source,keys,concept,type,nullable=false,limitations=[]) {
 const selected=at(source,keys),path='/'+keys.map(escapePointer).join('/');
 if(selected.present&&!(nullable&&selected.value===null)&&(typeof selected.value!==type||(type==='number'&&!Number.isFinite(selected.value))))throw new TypeError(`NPC source ${path} has an unexpected type.`);
 return {path,...selected,concept,limitations:[...limitations]};
}
/** PF2e-specific selected source array; ordered duplicate codes stay unchanged. */
function strings(source,keys,concept,limitations=[]) {
 const selected=at(source,keys),path='/'+keys.map(escapePointer).join('/');
 if(!selected.present)return [{path,present:false,concept,limitations:[...limitations]}];
 if(!Array.isArray(selected.value))throw new TypeError(`NPC source ${path} must be an array.`);
 if(!selected.value.length)return [{path,present:true,value:[],concept,limitations:[...limitations]}];
 return selected.value.map((value,i)=>{if(typeof value!=='string')throw new TypeError(`NPC source ${path}/${i} must be a string.`);return {path:`${path}/${i}`,present:true,value,concept,limitations:[...limitations]};});
}
/** PF2e-specific selected source record list; arbitrary member fields excluded. */
function list(source,keys,concept,children) {
 const selected=at(source,keys),path='/'+keys.map(escapePointer).join('/');
 if(!selected.present)return [{path,present:false,concept,limitations:[]}];
 if(!Array.isArray(selected.value))throw new TypeError(`NPC source ${path} must be an array.`);
 if(!selected.value.length)return [{path,present:true,value:[],concept,limitations:[]}];
 return selected.value.flatMap((entry,i)=>{if(entry===null||typeof entry!=='object'||Array.isArray(entry))throw new TypeError(`NPC source ${path}/${i} must be an object.`);return children([...keys,String(i)],entry);});
}
/**
 * PF2e-specific stored predicate JSON leaves only; never evaluate or infer
 * applicability. Guards reject cyclic/excessive depth/count and non-JSON data.
 */
function predicate(source,keys) {
 const selected=at(source,keys),path='/'+keys.map(escapePointer).join('/'),concept='stored_predicate_source',limitations=['predicate_not_evaluated'];
 if(!selected.present)return [{path,present:false,concept,limitations}];
 if(!Array.isArray(selected.value))throw new TypeError(`NPC source ${path} predicate must be an array.`);
 let count=0;const seen=new Set();
 const visit=(value,path,depth)=>{
  if(++count>10000||depth>32)throw new TypeError('NPC source predicate exceeds structural limits.');
  if(value===null||['string','boolean','number'].includes(typeof value)){
   if(typeof value==='number'&&!Number.isFinite(value))throw new TypeError('NPC source predicate has non-finite number.');
   return [{path,present:true,value,concept,limitations:[...limitations]}];
  }
  if(typeof value!=='object'||seen.has(value)||![Object.prototype,null,Array.prototype].includes(Object.getPrototypeOf(value)))throw new TypeError('NPC source predicate must contain JSON values.');
  seen.add(value);const entries=Object.entries(value);let rows=[];
  if(!entries.length)rows=[{path,present:true,value:Array.isArray(value)?[]:{},concept,limitations:[...limitations]}];
  else for(const [key,child]of entries)rows.push(...visit(child,`${path}/${escapePointer(key)}`,depth+1));
  seen.delete(value);return rows;
 };
 return visit(selected.value,path,0);
}
/**
 * PF2e-specific NPCSystemSource8.6.1 stat-block leaves. Level, ability modifiers,
 * authored AC/saves/Perception/skill bonuses, stored HP, source movement and IWR
 * remain distinct concepts. Null skill base defers to attribute in the system;
 * this helper preserves null and does not calculate that value. Unknown codes
 * remain exact. Inline exceptions/notes are retained; biography notes require
 * npcNoteFields explicitly. No embedded Item joins, derived actions, custom
 * modifiers, rule elements, flags, sheet data or effective statistics are read.
 */
export function npcFields(source) {
 if(source?.type!=='npc')return null;
 const rows=[];const add=(keys,concept,type,nullable=false,limits=[])=>rows.push(scalar(source,['system',...keys],concept,type,nullable,limits));
 add(['details','level','value'],'creature_level','number');
 add(['details','alliance'],'recorded_alliance','string',true,['alliance_not_player_assignment_or_narrative_role']);
 add(['traits','size','value'],'creature_size_code','string');add(['traits','rarity'],'creature_rarity_code','string');
 rows.push(...strings(source,['system','traits','value'],'creature_trait_code',['code_preserved_without_unverified_label_lookup']));
 for(const key of ['str','dex','con','int','wis','cha'])add(['abilities',key,'mod'],`attribute_modifier_${key}`,'number',false,['attribute_modifier_not_legacy_ability_score']);
 add(['attributes','adjustment'],'recorded_creature_adjustment','string',true,['elite_weak_math_not_applied']);
 add(['attributes','ac','value'],'authored_armor_class','number',false,['source_not_complete_effective_statistic']);add(['attributes','ac','details'],'armor_class_exception_notes','string');
 for(const key of ['value','max','temp'])add(['attributes','hp',key],{value:'recorded_hit_points',max:'source_maximum_hit_points',temp:'recorded_temporary_hit_points'}[key],'number',false,['stored_source_not_complete_effective_state']);
 add(['attributes','hp','details'],'hit_point_exception_notes','string');add(['attributes','hp','tempSource'],'temporary_hit_point_source_item_id','string',false,['local_item_id_not_verified_uuid']);
 add(['attributes','allSaves','value'],'all_save_exception_notes','string');
 for(const key of ['fortitude','reflex','will']){add(['saves',key,'value'],`authored_${key}_save_bonus`,'number',false,['source_not_ability_modifier_or_complete_effective_statistic']);add(['saves',key,'saveDetail'],`${key}_save_exception_notes`,'string');}
 add(['perception','mod'],'authored_perception_bonus','number',false,['source_not_ability_modifier_or_complete_effective_statistic']);add(['perception','details'],'perception_exception_notes','string');add(['perception','vision'],'recorded_vision','boolean');
 rows.push(...list(source,['system','perception','senses'],'creature_senses',(keys)=>[
  scalar(source,[...keys,'type'],'sense_type_code','string'),scalar(source,[...keys,'acuity'],'sense_acuity_code','string'),scalar(source,[...keys,'range'],'sense_range_feet','number'),scalar(source,[...keys,'source'],'sense_source_label','string',true)
 ]));
 rows.push(...strings(source,['system','details','languages','value'],'language_code'));add(['details','languages','details'],'language_exception_notes','string');
 add(['attributes','speed','value'],'authored_land_speed_feet','number',false,['source_not_complete_effective_movement']);add(['attributes','speed','details'],'movement_exception_notes','string');
 rows.push(...list(source,['system','attributes','speed','otherSpeeds'],'other_movement_sources',(keys)=>[
  scalar(source,[...keys,'type'],'movement_type_code','string'),scalar(source,[...keys,'value'],'authored_movement_speed_feet','number',false,['source_not_complete_effective_movement']),scalar(source,[...keys,'label'],'movement_source_label','string'),scalar(source,[...keys,'source'],'movement_source_reference','string')
 ]));
 const skills=at(source,['system','skills']);
 if(!skills.present)rows.push({path:'/system/skills',present:false,concept:'authored_skill_sources',limitations:[]});
 else{
  if(skills.value===null||typeof skills.value!=='object'||Array.isArray(skills.value))throw new TypeError('NPC source skills must be a record.');
  if(!Object.keys(skills.value).length)rows.push({path:'/system/skills',present:true,value:{},concept:'authored_skill_sources',limitations:[]});
  for(const key of Object.keys(skills.value)){
   if(skills.value[key]===null||typeof skills.value[key]!=='object'||Array.isArray(skills.value[key]))throw new TypeError('NPC source skill entry must be an object.');
   const keys=['system','skills',key];rows.push(scalar(source,[...keys,'base'],'authored_skill_bonus','number',true,['null_defers_to_attribute_not_calculated','source_not_complete_effective_statistic']),scalar(source,[...keys,'note'],'skill_exception_notes','string'));
   rows.push(...list(source,[...keys,'special'],'special_skill_sources',(special)=>[scalar(source,[...special,'label'],'special_skill_label','string'),scalar(source,[...special,'base'],'authored_special_skill_bonus','number',false,['predicate_applicability_not_evaluated']),...predicate(source,[...special,'predicate'])]));
  }
 }
 for(const kind of ['immunities','weaknesses','resistances'])rows.push(...list(source,['system','attributes',kind],`source_${kind}`,(keys)=>{
  const fields=[scalar(source,[...keys,'type'],`${kind}_type_code`,'string',false,['source_iwr_not_effective_or_target_evaluated'])];
  if(kind!=='immunities')fields.push(scalar(source,[...keys,'value'],`${kind}_source_value`,'number'));
  if(kind==='weaknesses')fields.push(scalar(source,[...keys,'applyOnce'],'weakness_apply_once_source','boolean',false,['missing_not_defaulted']));
  for(const property of kind==='resistances'?['exceptions','doubleVs']:['exceptions']){
   const selected=at(source,[...keys,property]),path='/'+[...keys,property].map(escapePointer).join('/');
   if(!selected.present){fields.push({path,present:false,concept:`${kind}_${property}`,limitations:[]});continue;}
   if(!Array.isArray(selected.value))throw new TypeError(`NPC source ${path} must be an array.`);
   if(!selected.value.length)fields.push({path,present:true,value:[],concept:`${kind}_${property}`,limitations:[]});
   selected.value.forEach((entry,i)=>{
    if(typeof entry==='string')fields.push({path:`${path}/${i}`,present:true,value:entry,concept:`${kind}_${property}_code`,limitations:['iwr_applicability_not_evaluated']});
    else if(entry!==null&&typeof entry==='object'&&!Array.isArray(entry))fields.push(scalar(source,[...keys,property,String(i),'label'],`${kind}_${property}_label`,'string'),...predicate(source,[...keys,property,String(i),'definition']));
    else throw new TypeError(`NPC source ${path}/${i} must be a code or predicate exception.`);
   });
  }
  return fields;
 }));
 add(['initiative','statistic'],'initiative_statistic_code','string',false,['initiative_bonus_not_calculated']);
 add(['spellcasting','rituals','dc'],'authored_ritual_dc','number',false,['ritual_castability_not_verified']);
 for(const key of ['value','max'])add(['resources','focus',key],`recorded_focus_${key}`,'number',false,['stored_source_not_complete_casting_resource_state']);
 for(const [key,type]of [['title','string'],['authors','string'],['license','string'],['remaster','boolean']])add(['details','publication',key],`publication_${key}`,type);
 return rows;
}
/**
 * PF2e-specific NPCDetailsSource8.6.1 explicit description-only selection.
 * Exact stored HTML/text blurb/publicNotes/privateNotes; no parsing/enrichment.
 * Caller must request description, fragment text and enforce GM/document rights.
 */
export function npcNoteFields(source){if(source?.type!=='npc')return null;return ['blurb','publicNotes','privateNotes'].map(key=>scalar(source,['system','details',key],`creature_${key}_source`,'string'));}
