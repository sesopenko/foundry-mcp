/**
 * PF2e-specific persisted condition Item selector, audited PF2e8.6.1/core14.369.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/condition/data.ts
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/base/data/model.ts
 * Accepts detached toObject(true) source. No prepared active/suppressed state,
 * duration, damage getters, formula evaluation, reference resolution or writes.
 */
const SOURCE_LIMIT=['persisted_source_not_effective_condition_state'];
/** PF2e-specific own-source lookup; only schema-optional persistent undefined is absent. */
function at(source,keys) {
 let value=source;
 for(const key of keys) {
  if(value===null||typeof value!=='object'||!Object.hasOwn(value,key))return {present:false};
  value=value[key];
 }
 return value===undefined&&keys.join('/')==='system/persistent'?{present:false}:{present:true,value};
}
/** PF2e-specific primitive source descriptor with no schema defaults or derived values. */
function leaf(source,keys,concept,type,nullable=false,choices=null) {
 const selected=at(source,keys),path='/'+keys.join('/');
 if(selected.present&&!(nullable&&selected.value===null)) {
  if(typeof selected.value!==type||(type==='number'&&!Number.isFinite(selected.value))||(choices&&!choices.includes(selected.value)))throw new TypeError(`Condition source field ${path} has an unexpected type or value; verify the PF2e8.6.1 source schema.`);
 }
 return {path,...selected,concept,limitations:[...SOURCE_LIMIT]};
}
/**
 * PF2e-specific condition source primitive leaves and null/missing/empty markers.
 * Local Item IDs and override slugs remain source text; no effective value,
 * suppression, applicability or persistent damage result is inferred.
 */
export function conditionFields(source) {
 if(source?.type!=='condition')return null;
 const fields=[];
 const add=(suffix,concept,type,nullable=false,choices=null)=>fields.push(leaf(source,['system',...suffix.split('/')],concept,type,nullable,choices));
 const marker=(path,selected,concept)=>fields.push({path,...selected,concept,limitations:[...SOURCE_LIMIT]});
 const container=(suffix,concept)=>{
  const path='/system/'+suffix,selected=at(source,['system',...suffix.split('/')]);
  if(!selected.present||selected.value===null){marker(path,selected,concept);return false;}
  if(typeof selected.value!=='object'||Array.isArray(selected.value))throw new TypeError(`Condition source container ${path} must be an object or null.`);
  return true;
 };
 const array=(suffix,concept,reference=false)=>{
  const path='/system/'+suffix,selected=at(source,['system',...suffix.split('/')]);
  if(!selected.present){marker(path,selected,concept);return;}
  if(!Array.isArray(selected.value))throw new TypeError(`Condition source ${path} must be an array.`);
  if(!selected.value.length)marker(path,{present:true,value:[]},concept);
  selected.value.forEach((value,index)=>{
   if(reference){
    if(value===null||typeof value!=='object'||Array.isArray(value))throw new TypeError(`Condition source ${path}/${index} must be a condition reference object.`);
    add(`${suffix}/${index}/id`,concept.replace(/_reference$/,'_item_id'),'string');
    add(`${suffix}/${index}/type`,concept.replace(/_reference$/,'_item_type'),'string',false,['condition']);
   }else{
    if(typeof value!=='string')throw new TypeError(`Condition source ${path}/${index} must be a string.`);
    marker(`${path}/${index}`,{present:true,value},concept);
   }
  });
 };
 add('value/isValued','condition_is_valued','boolean');add('value/value','condition_stored_value','number',true);
 if(container('persistent','condition_persistent_damage')) {
  add('persistent/formula','condition_persistent_formula','string');add('persistent/damageType','condition_persistent_damage_type','string');
  add('persistent/dc','condition_persistent_recovery_dc','number');add('persistent/criticalHit','condition_persistent_critical_hit','boolean');
 }
 if(container('references/parent','condition_parent_reference'))add('references/parent/id','condition_parent_item_id','string');
 for(const [suffix,concept]of [['children','child'],['overrides','override'],['overriddenBy','overridden_by']])array(`references/${suffix}`,`condition_${concept}_reference`,true);
 array('overrides','condition_override_slug');
 add('fromSpell','condition_from_spell','boolean');add('group','condition_group','string',true);
 array('traits/value','condition_trait_code');array('traits/otherTags','condition_other_tag_code');
 add('slug','source_slug','string',true);
 for(const [key,type]of [['title','string'],['authors','string'],['license','string'],['remaster','boolean']])add(`publication/${key}`,`publication_${key}`,type);
 return fields;
}
