/**
 * PF2e-specific declared CharacterSystemData/NPCSystemData.actions selection.
 * Tested boundary Foundry14.369/PF2e8.6.1. Public Actor.system own data only:
 * https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.ActorData.html#system
 * https://github.com/foundryvtt/pf2e/tree/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor
 * character/data.ts, npc/data.ts, data/base.ts and modifiers.ts declare selected
 * fields. Prepared model values are transformed, never persisted source or a
 * target-context roll. No getters, methods, damage or MAP arithmetic are used.
 */
import {embeddedIdentity, permitted} from './actorDocuments.js';
import {fail, textFragments} from './actorReadUtils.js';

const LIMIT = ['current_strike_not_target_context'];
const COMMON = {type:['type','string'],slug:['slug','string'],label:['label','string'],glyph:['action_glyph','string'],description:['description','string'],breakdown:['attack_breakdown','string'],ready:['ready','boolean'],canAttack:['can_attack','boolean'],totalModifier:['attack_modifier','number']};
const CHARACTER = {visible:['visible','boolean'],handsAvailable:['hands_available','boolean']};
const NPC = {sourceId:['source_item_local_id','string'],attackRollType:['attack_roll_type','string']};

/** PF2e-specific selected own descriptor, never inherited/accessor evaluation. */
function own(value, key) {
 if(value===null||typeof value!=='object')return {present:false};
 const descriptor=Object.getOwnPropertyDescriptor(value,key);
 if(!descriptor)return {present:false};
 if(!Object.hasOwn(descriptor,'value'))return {accessor:true};
 if(descriptor.value===undefined)return {present:false};
 return {present:true,value:descriptor.value};
}

/** PF2e-specific declared Strike snapshot; every origin is authorized first.
 * Same-owner ephemeral weapons are generated context, not canonical Items.
 * Source witnesses use exact permitted Item membership; defaults/source readers
 * must not call this helper. Returned records/reasons participate in revision.
 */
export function actorStrikeSnapshot(target) {
 const actor=target.document;
 if(!['character','npc'].includes(actor.type))fail('UnsupportedType','Current Strikes require a character or NPC.');
 if(actor.items.size>12000)fail('ReadFailed','Current Strike owned Item bound exceeded.');
 const records=[],reasons=new Set(['target_context_not_evaluated','current_strike_damage_unsupported']);
 let nodes=0,denied=false,otherKinds=false;
 const ancestry=new Set();
 /** PF2e-specific bounded detached current record admission. */
 function push(record){records.push(record);if(records.length>24000)fail('ReadFailed','Current Strike record bound exceeded.');}
 /** PF2e-specific current capability; empty provenance never claims source. */
 function capability(key,concept,value){push({key,section:'strikes',kind:'field',raw:[],mapped:{concept,value,unit:null},provenance:{contributors:[],mapping:'pf2e.actor.strike-capability.v1',limitations:[...LIMIT]}});}
 /** PF2e-specific accessors are unavailable, distinct from absent own fields. */
 function unavailable(path){reasons.add('current_strike_fields_unavailable');capability('strikes:unavailable:'+path,'current_strike_field_support',{status:'unsupported',reason:'accessor_not_read',path});}
 /** PF2e-specific current primitive/array marker with explicit own presence. */
 function field(path,concept,selected,type,nullable=false){
  if(selected.accessor){unavailable(path);return;}
  if(!selected.present)reasons.add('current_strike_fields_unavailable');
  if(selected.present){const value=selected.value;
   if(!(nullable&&value===null)&&(type==='array'?!Array.isArray(value)||value.length!==0:typeof value!==type||type==='number'&&!Number.isFinite(value)))fail('ReadFailed','Malformed declared current Strike field.');
   if(typeof value==='string'&&value.length>300000)fail('ReadFailed','Current Strike text bound exceeded.');
  }
  // PF2e-specific model collection markers detach their empty contents; retaining
  // a model array could later execute its unselected toJSON during hashing/RPC.
  const raw={document_uuid:actor.uuid,path,present:!!selected.present,...(selected.present?{value:type==='array'?[]:selected.value}:{}),basis:'transformed'};
  const row={key:'strikes:current:'+path,section:'strikes',kind:'field',raw:[raw],mapped:{concept:'current_strike_'+concept,value:selected.present&&type!=='array'?selected.value:null,unit:null},provenance:{contributors:[{document_uuid:actor.uuid,path,basis:'transformed'}],mapping:'pf2e.actor.strike-current.v1',limitations:[...LIMIT]}};
  if(selected.present&&typeof selected.value==='string'&&new TextEncoder().encode(JSON.stringify(selected.value)).length>1000){
   for(const [index,fragment]of textFragments(selected.value).entries())push({...row,key:row.key+':text:'+index,kind:'text',raw:[{...raw,value:fragment.value}],mapped:{...row.mapped,value:null},text:{path,...fragment.text}});
  }else push(row);
 }
 /** PF2e-specific bounded dense array; no iterator/getter execution. */
 function array(value,key,path,max,concept){
  const selected=own(value,key);
  if(selected.accessor){unavailable(path);return null;}
  if(!selected.present){field(path,concept,selected,'array');return null;}
  if(!Array.isArray(selected.value)||selected.value.length>max)fail('ReadFailed','Current Strike array bound or type invalid.');
  if(!selected.value.length){field(path,concept,selected,'array');return [];}
  const values=[];
  for(let index=0;index<selected.value.length;index++){
   const entry=own(selected.value,String(index));
   if(!entry.present||entry.accessor)fail('ReadFailed','Current Strike arrays require dense own data entries.');
   values.push(entry.value);
  }
  return values;
 }
 /** PF2e-specific permission-first source origin; labels cannot leak denial. */
 function origin(node,path,typeWitness){
  const reference=own(node,'item');
  if(reference.accessor||!reference.present)return {status:'unavailable',raw:[typeWitness]};
  const item=reference.value;
  if(!item||typeof item!=='object'||item.documentName!=='Item'||item.parent!==actor||item.type!==(actor.type==='character'?'weapon':'melee'))return {status:'unavailable',raw:[typeWitness]};
  const member=actor.items.get(item.id);
  if(!permitted(actor)||!permitted(item)||(member&&!permitted(member)))return {status:'denied'};
  // PF2e-specific NPC sourceId is an owner-local claim, never a guessed UUID.
  const sourceId=actor.type==='npc'?own(node,'sourceId'):{present:false};
  if(sourceId.present&&typeof sourceId.value==='string'){
   const source=actor.items.get(sourceId.value);
   if(source&&!permitted(source))return {status:'denied'};
  }
  if(member!==item)return {status:'generated',raw:[typeWitness]};
  const identity=embeddedIdentity(item,target),source=item.toObject(true);
  const sourceName=own(source,'name'),sourceType=own(source,'type');
  if(!sourceName.present||sourceName.accessor||typeof sourceName.value!=='string'||!sourceType.present||sourceType.accessor||sourceType.value!==item.type)fail('ReadFailed','Current Strike origin source invalid.');
  const name=[...sourceName.value];
  if(sourceName.value.length>300000)fail('ReadFailed','Current Strike origin name bound exceeded.');
  const clipped=name.slice(0,256).join('');
  const value={status:'resolved',target_uuid:identity.uuid,type:item.type,name:clipped,name_truncated:name.length>256};
  if(target.token)value.token_uuid=target.token.uuid;
  return {status:'resolved',value,raw:[typeWitness,{document_uuid:identity.uuid,path:'/name',present:true,value:sourceName.value,basis:'source'},{document_uuid:identity.uuid,path:'/type',present:true,value:sourceType.value,basis:'source'}]};
 }
 /** PF2e-specific Strike node traversal; alternatives retain response paths. */
 function visit(node,path,depth){
  if(++nodes>256||depth>4)fail('ReadFailed','Current Strike node/depth bound exceeded.');
  if(node===null||typeof node!=='object'||Array.isArray(node)||ancestry.has(node))fail('ReadFailed','Malformed or cyclic current Strike node.');
  const type=own(node,'type');
  if(type.accessor){unavailable(path+'/type');return;}
  if(!type.present){field(path+'/type','type',type,'string');return;}
  if(typeof type.value!=='string')fail('ReadFailed','Current Strike type must be a string.');
  if(type.value!=='strike'){otherKinds=true;reasons.add('non_strike_actions_unsupported');return;}
  const typeWitness={document_uuid:actor.uuid,path:path+'/type',present:true,value:'strike',basis:'transformed'};
  const resolved=origin(node,path,typeWitness);
  if(resolved.status==='denied'){denied=true;reasons.add('strike_items_denied');return;}
  const value=resolved.value??{status:resolved.status,target_uuid:null};
  push({key:'strikes:origin:'+path,section:'strikes',kind:'relationship',raw:resolved.raw,mapped:{concept:'current_strike_origin',value,unit:null},provenance:{contributors:resolved.raw.map(({document_uuid,path,basis})=>({document_uuid,path,basis})),mapping:'pf2e.actor.strike-origin.v1',limitations:[...LIMIT]}});
  if(resolved.status==='unavailable'){reasons.add('current_strike_origins_unavailable');return;}
  ancestry.add(node);
  for(const [key,[concept,type]]of Object.entries({...COMMON,...(actor.type==='character'?CHARACTER:NPC)}))field(path+'/'+key,concept,own(node,key),type);
  for(const key of actor.type==='character'?['options','domains']:['options']){
   const values=array(node,key,path+'/'+key,256,key);
   if(values)values.forEach((value,index)=>field(path+'/'+key+'/'+index,key==='options'?'option':'domain',{present:true,value},'string'));
  }
  for(const key of actor.type==='character'?['traits','weaponTraits']:['traits']){
   const values=array(node,key,path+'/'+key,64,key==='traits'?'traits':'weapon_traits');
   if(values)values.forEach((value,index)=>{
    if(value===null||typeof value!=='object'||Array.isArray(value))fail('ReadFailed','Malformed current Strike trait.');
    for(const [leaf,suffix]of [['name','code'],['label','label'],['description','description']])field(path+'/'+key+'/'+index+'/'+leaf,(key==='traits'?'trait_':'weapon_trait_')+suffix,own(value,leaf),'string',leaf==='description');
   });
  }
  const variants=array(node,'variants',path+'/variants',16,'variants');
  if(variants)variants.forEach((value,index)=>{
   if(value===null||typeof value!=='object'||Array.isArray(value))fail('ReadFailed','Malformed current Strike variant.');
   field(path+'/variants/'+index+'/penalty','map_penalty',own(value,'penalty'),'number');
   field(path+'/variants/'+index+'/label','variant_label',own(value,'label'),'string');
  });
  const alternatives=array(node,'altUsages',path+'/altUsages',256,'alternate_usages');
  if(alternatives)alternatives.forEach((value,index)=>visit(value,path+'/altUsages/'+index,depth+1));
  ancestry.delete(node);
 }
 const system=own(actor,'system');
 if(system.accessor)unavailable('/system/actions');
 else{
  const actions=array(system.present?system.value:null,'actions','/system/actions',256,'collection');
  if(actions)actions.forEach((action,index)=>visit(action,'/system/actions/'+index,0));
 }
 if(otherKinds)capability('strikes:capability:non_strike_actions','current_strike_capability',{status:'unsupported',reason:'non_strike_actions_unsupported'});
 if(denied)capability('strikes:current:denied','current_strike_capability',{status:'denied',target_uuid:null});
 return {records,reasons:[...reasons].sort()};
}
