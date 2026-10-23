/**
 * PF2e-specific character source selectors, audited PF2e 8.6.1/core14.369.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/character/data.ts
 * Shared creature/base source and static/template.json at that same revision.
 * Detached Actor.toObject(true) input only; no runtime/prepared statistics.
 * Exact allowlist: docs/actor-item-story-map/character-fields.md.
 */
const LIMIT=['character_source_not_effective_statistics'];
const RANK_LABELS=['Untrained','Trained','Expert','Master','Legendary'];
const MAX_ENTRIES=12000;
/** PF2e-specific character source path escaping; no inferred identities. */
function escape(key){return key.replaceAll('~','~0').replaceAll('/','~1');}
/** PF2e-specific character own-source lookup; optional undefined stays absent. */
function at(source,keys){let value=source;for(const key of keys){if(value===null||typeof value!=='object'||!Object.hasOwn(value,key)||value[key]===undefined)return {present:false};value=value[key];}return {present:true,value};}
/** PF2e-specific character source descriptor; values never become defaults. */
function descriptor(keys,selected,concept,limits=[]){return {path:'/'+keys.map(escape).join('/'),...selected,concept,limitations:[...LIMIT,...limits]};}
/** PF2e-specific character scalar schema selection, never coerced or computed. */
function scalar(source,keys,concept,type,nullable=false,limits=[]){const selected=at(source,keys);if(selected.present&&!(nullable&&selected.value===null)&&(typeof selected.value!==type||(type==='number'&&!Number.isFinite(selected.value))))throw new TypeError(`Character source /${keys.map(escape).join('/')} has an unexpected type.`);return descriptor(keys,selected,concept,limits);}
/** PF2e-specific character ordered code/prose arrays retain duplicates and empties. */
function strings(source,keys,concept){const selected=at(source,keys);if(!selected.present)return [descriptor(keys,selected,concept)];if(!Array.isArray(selected.value)||selected.value.length>MAX_ENTRIES)throw new TypeError('Character source list must contain at most 12000 strings.');if(!selected.value.length)return [descriptor(keys,{present:true,value:[]},concept)];return selected.value.map((value,i)=>{if(typeof value!=='string')throw new TypeError('Character source list entry must be a string.');return descriptor([...keys,String(i)],{present:true,value},concept);});}
/** PF2e-specific character source record validation; no prepared object copying. */
function record(selected,name){if(selected.value===null||typeof selected.value!=='object'||Array.isArray(selected.value)||Object.keys(selected.value).length>MAX_ENTRIES)throw new TypeError(`Character source ${name} must be a record of at most 12000 entries.`);}
/** PF2e-specific character skill source rank, labelled separately from check totals. */
function rank(source,keys){const row=scalar(source,keys,'recorded_skill_proficiency_rank','number',false,['rank_not_total_check_modifier']);if(row.present){if(!Number.isInteger(row.value)||row.value<0||row.value>4)throw new TypeError('Character source skill rank must be an integer from 0 to 4.');row.mapped_value={rank:row.value,label:RANK_LABELS[row.value]};}return row;}
/**
 * PF2e-specific CharacterSystemSource8.6.1 selected persisted leaves: nullable
 * abilities, identity/level/languages/XP, HP, skill ranks, resources and recorded
 * build choices. Null abilities stay one root marker; no six fabricated zeroes.
 * HP/focus maxima, traits, saves, Perception, AC, movement, IWR, prepared build
 * additions and identity convenience properties are excluded. Rank is not a
 * total, and choices do not establish eligibility or effective benefits.
 * Returns null for other actor types; shared reader owns system/permission gates.
 */
export function characterFields(source){
 if(source?.type!=='character')return null;
 const fields=[];
 /** PF2e-specific character detached system scalar, without derived fallback. */
 const add=(path,concept,type,nullable=false,limits=[])=>fields.push(scalar(source,['system',...path.split('/')],concept,type,nullable,limits));
 const abilities=at(source,['system','abilities']);
 if(!abilities.present||abilities.value===null)fields.push(descriptor(['system','abilities'],abilities,'recorded_attribute_modifiers',['null_not_zero_attributes']));
 else{record(abilities,'abilities');for(const key of ['str','dex','con','int','wis','cha']){const entry=at(source,['system','abilities',key]);if(entry.present)record(entry,`abilities/${key}`);add(`abilities/${key}/mod`,`attribute_modifier_${key}`,'number',false,['source_manual_modifier_not_effective_attribute']);}}
 add('details/level/value','character_level','number');
 for(const key of ['age','height','weight','gender','ethnicity','nationality'])add(`details/${key}/value`,`character_${key}_source`,'string');
 add('details/keyability/value','recorded_key_attribute_code','string');
 fields.push(...strings(source,['system','details','languages','value'],'recorded_language_code'));
 for(const key of ['value','min','max'])add(`details/xp/${key}`,`recorded_experience_${key}`,'number');
 for(const key of ['appearance','backstory','personality','campaign'])add(`details/biography/visibility/${key}`,`biography_${key}_visibility_source`,'boolean',false,['visibility_not_caller_authorization']);
 for(const key of ['value','temp'])add(`attributes/hp/${key}`,key==='value'?'recorded_hit_points':'recorded_temporary_hit_points','number');
 add('attributes/hp/tempSource','temporary_hit_point_source_item_id','string',false,['local_item_id_not_verified_uuid']);
 add('attributes/hp/sp/value','recorded_stamina_points','number',false,['stamina_variant_source_only']);
 const skills=at(source,['system','skills']);
 if(!skills.present)fields.push(descriptor(['system','skills'],skills,'recorded_skill_ranks'));
 else{record(skills,'skills');const keys=Object.keys(skills.value);if(!keys.length)fields.push(descriptor(['system','skills'],{present:true,value:{}},'recorded_skill_ranks'));for(const key of keys){record({value:skills.value[key]},`skills/${key}`);fields.push(rank(source,['system','skills',key,'rank']));}}
 for(const key of ['value','max'])add(`resources/heroPoints/${key}`,`recorded_hero_points_${key}`,'number');
 add('resources/focus/value','recorded_focus_value','number',false,['focus_pool_maximum_not_source']);
 add('resources/crafting/infusedReagents/value','recorded_infused_reagents_value','number',false,['crafting_availability_not_evaluated']);
 add('resources/resolve/value','recorded_resolve_value','number',false,['stamina_variant_source_only']);
 add('build/attributes/manual','recorded_manual_attributes','boolean');
 for(const key of ['1','5','10','15','20'])fields.push(...strings(source,['system','build','attributes','boosts',key],'recorded_attribute_boost_code'));
 add('build/attributes/apex','recorded_apex_attribute_code','string',true);
 return fields;
}
/**
 * PF2e-specific CharacterBiography8.6.1 and language-details source prose only.
 * Exact HTML/plain strings and ordered edict/anathema arrays; no enrichment,
 * parsing or execution. Explicit description selection, GM rights, text bounds
 * and continuation belong to the shared reader. Other actor types return null.
 */
export function characterNoteFields(source){
 if(source?.type!=='character')return null;
 const fields=[scalar(source,['system','details','languages','details'],'language_exception_notes','string')];
 for(const key of ['appearance','backstory','campaignNotes','allies','enemies','organizations','birthPlace','attitude','beliefs','likes','dislikes','catchphrases'])fields.push(scalar(source,['system','details','biography',key],`character_biography_${key}_source`,'string'));
 for(const key of ['edicts','anathema'])fields.push(...strings(source,['system','details','biography',key],`character_biography_${key}_source`));
 return fields;
}
