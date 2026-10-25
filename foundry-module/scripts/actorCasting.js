/**
 * PF2e-specific Actor spellcasting source joins, core14.369/PF2e8.6.1.
 * Public Item identities and toObject(true/false); no casting getters or writes.
 * Public serialization: https://foundryvtt.com/api/v14/classes/foundry.documents.Item.html#toobject
 * Source contracts at https://github.com/foundryvtt/pf2e/tree/28d9d156f252d084371d994dc359509b49eadf18/src/module
 * item/spell/data.ts, item/spellcasting-entry/data.ts and actor/{character,creature}/data.ts.
 * These are stored configuration/resources, never current available cast options.
 */
import {embeddedIdentity,permitted} from './actorDocuments.js';
import {spellFields} from './actorSpell.js';
import {spellcastingEntryFields,spellcastingEntryIssues} from './actorSpellcastingEntry.js';
import {castingCurrentFields} from './actorCastingCurrent.js';
const LIMIT=['source_configuration_only','availability_not_evaluated'];
/** PF2e-specific own source lookup preserving absent versus zero/null. */
function at(source,path){let node=source;for(const key of path.slice(1).split('/')){if(node===null||typeof node!=='object'||!Object.hasOwn(node,key))return {present:false};node=node[key];}return {present:true,value:node};}
/** PF2e-specific source contributor without fabricated identity or defaults. */
function raw(uuid,path,selected){return {document_uuid:uuid,path,...selected,basis:'source'};}
/** PF2e-specific detached bounded source join record. */
function record(key,concept,raw,value,kind='relationship',mapping='pf2e.actor.casting-source.v1',limitations=LIMIT){return {key,section:'spellcasting',kind,raw,mapped:{concept,value,unit:null},provenance:{contributors:raw.map(({document_uuid,path,basis})=>({document_uuid,path,basis})),mapping,limitations:[...limitations]}};}
/** PF2e-specific actual local Item identity, with retained selected token context. */
function identity(item,target){const id=embeddedIdentity(item,{document:target.document,token:target.token});return {status:'resolved',target_uuid:id.uuid,type:id.type,name:id.name,name_truncated:id.name_truncated,...(target.token?{token_uuid:target.token.uuid}:{})};}
/**
 * PF2e-specific Actor casting snapshot, with same-owner source joins and selected
 * transformed character/NPC focus and spell focus costs. PF2e8.6.1 contracts are
 * pinned in actorCastingCurrent.js; current values never replace source values.
 * Repeated preparations remain distinct; zero counters/expended flags are never
 * combined into availability. Legacy preparation shapes are explicit gaps.
 * Character focus max is derived, therefore excluded; creature optional source
 * max is retained. Descriptions/rules/overlays are not expanded in this section.
 * Returns {records,reasons}; caller applies shared continuation/byte bounds and
 * includes the detached result in its revision/revalidation snapshot.
 */
export function actorCastingRecords(target,actorSource=target.document.toObject(true)){
 const actor=target.document,records=[],reasons=new Set(['availability_not_evaluated']);
 if(actor.documentName!=='Actor'||!['character','npc','familiar'].includes(actor.type))throw new TypeError('Casting source requires a supported Actor.');
 if(['character','npc'].includes(actor.type)){
  const type=actorSource&&typeof actorSource==='object'?Object.getOwnPropertyDescriptor(actorSource,'type'):undefined;
  if(!type||!Object.hasOwn(type,'value')||type.value!==actor.type)throw new TypeError('Casting Actor source identity is invalid.');
 }
 const items=[...actor.items.values()];if(items.length>12000)throw new TypeError('Casting source exceeds 12000 owned Items.');
 const readable=new Map();let denied=false;
 for(const item of items){if(!['spell','spellcastingEntry'].includes(item.type))continue;if(!permitted(item)){denied=true;continue;}const source=item.toObject(true);if(source?.type!==item.type||typeof source.name!=='string')throw new TypeError('Casting Item source identity is invalid.');readable.set(item.id,{item,source});}
 /** PF2e-specific selected source field transfer, preserving existing typed mapping. */
 const fields=(item,rows,mapping)=>{for(const field of rows){records.push(record(`spellcasting:source:${item.uuid}:${field.path}`,field.concept,[raw(item.uuid,field.path,{present:field.present,...(field.present?{value:field.value}:{})})],Object.hasOwn(field,'mapped_value')?field.mapped_value:field.present?field.value:null,'field',mapping,field.limitations));}};
 /** PF2e-specific transformed own data selection, after source/type/owner admission. */
 const current=(document,documentType)=>{
  const serialized=document.toObject(false),type=serialized&&typeof serialized==='object'?Object.getOwnPropertyDescriptor(serialized,'type'):undefined;
  if(!type||!Object.hasOwn(type,'value')||type.value!==document.type)throw new TypeError('Casting transformed identity is invalid.');
  const selected=castingCurrentFields(serialized,documentType);
  if(!selected)throw new TypeError('Casting transformed type is unsupported.');
  for(const field of selected.fields){const selectedRaw={document_uuid:document.uuid,path:field.path,present:field.present,...(field.present?{value:field.value}:{}),basis:'transformed'};records.push(record(`spellcasting:current:${document.uuid}:${field.path}`,field.concept,[selectedRaw],field.present?field.value:null,'field','pf2e.actor.casting-current.v1',field.limitations));}
  if(selected.reasons.includes('current_fields_unavailable'))reasons.add('current_fields_unavailable');
 };
 /** PF2e-specific same-owner lookup; unreadable targets expose no identity. */
 const resolve=(id,type,entryId=null)=>{if(typeof id!=='string'||!id)return {status:'missing',target_uuid:null};const candidate=items.find(item=>item.id===id);if(!candidate)return {status:'missing',target_uuid:null};if(!permitted(candidate))return {status:'denied',target_uuid:null};if(candidate.type!==type)return {status:'unsupported',target_uuid:null};if(entryId!==null){const assigned=readable.get(candidate.id)?.source?.system?.location?.value;if(assigned!==entryId)return {status:'mismatched_assignment',target_uuid:null};}return identity(candidate,target);};
 for(const {item,source}of readable.values()){
  const entry=item.type==='spellcastingEntry';
  records.push(record(`spellcasting:${entry?'entry':'spell'}:${item.uuid}`,entry?'casting_entry':'casting_spell',[raw(item.uuid,'/name',{present:true,value:source.name}),raw(item.uuid,'/type',{present:true,value:source.type})],identity(item,target)));
  if(entry){
   fields(item,spellcastingEntryFields(source),'pf2e.spellcasting-entry.source.v1');
   for(const issue of spellcastingEntryIssues(source))reasons.add(issue.reason);
   if(source.system?.prepared?.flexible||!['prepared','spontaneous','innate','focus'].includes(source.system?.prepared?.value))reasons.add('unsupported_casting_mode');
   for(let rank=0;rank<=11;rank++){
    const prepared=source.system?.slots?.['slot'+rank]?.prepared;if(!Array.isArray(prepared))continue;
    for(let i=0;i<prepared.length;i++){const path=`/system/slots/slot${rank}/prepared/${i}/id`,selected=at(source,path);if(selected.present&&selected.value!==null&&typeof selected.value!=='string')continue;
     if(prepared[i]===null||typeof prepared[i]!=='object'||Array.isArray(prepared[i]))continue;
     records.push(record(`spellcasting:preparation:${item.uuid}:${rank}:${i}`,'casting_preparation',[raw(item.uuid,path,selected)],resolve(selected.value,'spell',item.id)));
    }
   }
  }else{
   if(item.documentName!=='Item'||item.parent!==actor)throw new TypeError('Casting spell must belong to the selected Actor.');
   current(item,'Item');
   // PF2e-specific projection prevents reading unrelated definitions or overlays.
   const system=source.system??{},projection={type:'spell',system:{}};
   for(const key of ['level','location'])if(Object.hasOwn(system,key))projection.system[key]=system[key];
   if(Object.hasOwn(system,'traits')){const traits=system.traits;if(traits===null||typeof traits!=='object'||Array.isArray(traits))throw new TypeError('Spell traits source must be an object.');projection.system.traits={};if(Object.hasOwn(traits,'value'))projection.system.traits.value=traits.value;}
   fields(item,spellFields(projection).filter(field=>['/system/level','/system/level/value','/system/traits','/system/location'].includes(field.path)||/^\/system\/traits\/value(?:\/\d+)?$/.test(field.path)||field.path.startsWith('/system/location/')),'pf2e.spell.source.v1');
   const path='/system/location/value',selected=at(source,path);
   records.push(record(`spellcasting:assignment:${item.uuid}`,'casting_spell_assignment',[raw(item.uuid,path,selected)],resolve(selected.value,'spellcastingEntry')));
   if(system.ritual!==null&&system.ritual!==undefined)reasons.add('unsupported_casting_mode');
  }
  if(records.length>24000)throw new TypeError('Casting source exceeds 24000 selected records.');
 }
 if(denied){reasons.add('casting_items_denied');records.push(record('spellcasting:denied','casting_item',[],{status:'denied',target_uuid:null}));}
 // PF2e-specific familiar focus is excluded pending its separate master contract.
 if(['character','npc'].includes(actor.type))current(actor,'Actor');
 for(const key of actor.type==='character'?['value']:['value','max']){const path='/system/resources/focus/'+key,selected=at(actorSource,path);if(key==='max'&&selected.present&&selected.value===undefined)selected.present=false,delete selected.value;if(selected.present&&(typeof selected.value!=='number'||!Number.isFinite(selected.value)))throw new TypeError('Actor focus source must be a finite number.');records.push(record('spellcasting:focus:'+key,'casting_focus_'+key,[raw(actor.uuid,path,selected)],selected.present?selected.value:null,'field'));}
 if(records.length>24000)throw new TypeError('Casting source exceeds 24000 selected records.');
 return {records,reasons:[...reasons].sort()};
}
