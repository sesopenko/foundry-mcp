/**
 * PF2e-specific spellcastingEntry source selector, audited against 8.6.1.
 * Detached Item.toObject(true) fields only; no collection/sheet state or getters.
 * Official template additionally declares opaque slot11, without rank semantics:
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/static/template.json
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/spellcasting-entry/data.ts
 */
const LIMIT=['source_only_no_castability_or_resource_expenditure','template_slot11_no_spell_rank_semantics'];
/** PF2e-specific own-source lookup; no defaults or document resolution. */
function at(source,path){let value=source;for(const key of path.split('/')){if(value===null||typeof value!=='object'||!Object.hasOwn(value,key))return {present:false};value=value[key];}return {present:true,value};}
/** PF2e-specific casting-entry selected-source walk, preserving preparation indexes.
 * Malformed/legacy preparations are explicit issues, never coerced to arrays or
 * dumped as arbitrary objects. Valid siblings remain readable. Other invalid
 * selected scalars reject. Slot value zero never determines exhaustion.
 */
function select(source){
 const fields=[],issues=[];
 /** PF2e-specific casting-entry descriptor emission with a finite source bound. */
 const emit=(path,concept,selected)=>{if(fields.length>=12000)throw new TypeError(`Spellcasting entry source /${path} exceeds 12000 selected fields.`);fields.push({path:'/'+path,...selected,concept:'casting_entry_'+concept,limitations:[...LIMIT]});};
 /** PF2e-specific malformed preparation marker; source content remains undisclosed. */
 const issue=(path,reason)=>{if(issues.length>=64)throw new TypeError(`Spellcasting entry source /${path} exceeds 64 incomplete preparation issues.`);issues.push({path:'/'+path,reason});};
 /** PF2e-specific casting-entry primitive selection without coercion or calculations. */
 const scalar=(path,concept,type,nullable=false,optional=false,tolerant=false)=>{
  const selected=at(source,path);if(optional&&selected.value===undefined)delete selected.value,selected.present=false;
  if(selected.present&&!(nullable&&selected.value===null)&&(typeof selected.value!==type||type==='number'&&!Number.isFinite(selected.value))){if(tolerant){issue(path,'malformed_preparation');return;}throw new TypeError(`Spellcasting entry source /${path} has an unexpected type.`);}
  emit(path,concept,selected);
 };
 for(const [path,concept,type,nullable,optional]of [
  ['tradition/value','tradition_code','string'],['prepared/value','mode_code','string'],['prepared/flexible','flexible','boolean',false,true],['prepared/validItems','valid_items_code','string',true,true],
  ['ability/value','ability_code','string'],['proficiency/value','proficiency_rank','number'],['spelldc/value','spell_attack_source','number'],['spelldc/dc','spell_dc_source','number'],['autoHeightenLevel/value','auto_heighten_rank','number',true],['slug','source_slug','string',true],
  ...[['title','string'],['authors','string'],['license','string'],['remaster','boolean']].map(([k,t])=>['publication/'+k,'publication_'+k,t]),
 ])scalar('system/'+path,concept,type,nullable,optional);
 const tags=at(source,'system/traits/otherTags');if(!tags.present)emit('system/traits/otherTags','other_tag_code',tags);else{if(!Array.isArray(tags.value))throw new TypeError('Spellcasting entry source /system/traits/otherTags must be an array.');if(!tags.value.length)emit('system/traits/otherTags','other_tag_code',{present:true,value:[]});for(let i=0;i<tags.value.length;i++)scalar('system/traits/otherTags/'+i,'other_tag_code','string');}
 const slots=at(source,'system/slots');
 if(slots.present&&(slots.value===null||typeof slots.value!=='object'||Array.isArray(slots.value))){issue('system/slots','malformed_slot');return {fields,issues};}
 else if(slots.present)for(const key of Object.keys(slots.value))if(!/^slot(?:[0-9]|10|11)$/.test(key))issue('system/slots/'+key.replaceAll('~','~0').replaceAll('/','~1'),'unsupported_slot_key');
 for(let rank=0;rank<=11;rank++){
  const path='system/slots/slot'+rank,node=at(source,path);
  if(node.present&&(node.value===null||typeof node.value!=='object'||Array.isArray(node.value))){issue(path,'malformed_slot');continue;}
  scalar(path+'/value','slot_value','number');scalar(path+'/max','slot_max','number');
  const p=path+'/prepared',prepared=at(source,p);
  if(!prepared.present){emit(p,'preparations',prepared);continue;}
  if(!Array.isArray(prepared.value)){issue(p,'malformed_preparations');continue;}
  if(prepared.value.length>6000)throw new TypeError(`Spellcasting entry source /${p} exceeds 6000 preparations.`);
  if(!prepared.value.length)emit(p,'preparations',{present:true,value:[]});
  for(let i=0;i<prepared.value.length;i++){
   const item=prepared.value[i],q=p+'/'+i;
   if(!Object.hasOwn(prepared.value,i)||item===null||typeof item!=='object'||Array.isArray(item)){issue(q,'malformed_preparation');continue;}
   for(const [key,concept,type,nullable]of [['id','prepared_spell_local_id','string',true],['expended','prepared_expended','boolean',false]]){
    scalar(q+'/'+key,concept,type,nullable,false,true);
   }
  }
 }
 return {fields,issues};
}
/** PF2e-specific casting-entry scalar source fields; no current resource inference.
 * Repeated spell IDs retain distinct array indexes, null IDs remain explicit and
 * unknown mode/tradition codes are retained. See spellcastingEntryIssues for gaps.
 */
export function spellcastingEntryFields(source){return source?.type==='spellcastingEntry'?select(source).fields:null;}
/** PF2e-specific casting-entry incomplete preparation paths, without private values.
 * Non-schema legacy shapes are not normalized or treated as empty preparations.
 */
export function spellcastingEntryIssues(source){return source?.type==='spellcastingEntry'?select(source).issues:[];}
