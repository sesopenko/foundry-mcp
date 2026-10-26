/**
 * PF2e-specific character/NPC transformed skill document-data snapshot, pinned to
 * Foundry14.369/PF2e8.6.1. Public serialization:
 * https://foundryvtt.com/api/v14/classes/foundry.documents.Actor.html#toobject
 * Schema contracts at immutable upstream revision:
 * https://github.com/foundryvtt/pf2e/tree/28d9d156f252d084371d994dc359509b49eadf18/src/module
 * actor/{creature,character,npc}/data.ts, actor/data/base.ts and
 * system/statistic/data.ts declare SkillData/StatisticTraceData. itemId is an
 * owner-local Lore Item claim, not a generated UUID or name/slug join. Values
 * come only from toObject(false), never source, getters or local calculations.
 */
import {embeddedIdentity,permitted} from './actorDocuments.js';
const LIMIT=['serialized_current_skill_not_target_context'];
const LORE_LIMIT=['serialized_lore_claim_not_exhaustive_owned_lore'];
const RANKS=['Untrained','Trained','Expert','Master','Legendary'];
const escape=key=>key.replaceAll('~','~0').replaceAll('/','~1');

/** PF2e-specific own detached data selection, including nonplain containers. */
function own(source,key){
 if(source===null||typeof source!=='object'||Array.isArray(source))throw new TypeError('Current skill source has a malformed container.');
 const descriptor=Object.getOwnPropertyDescriptor(source,key);if(!descriptor)return {present:false};
 if(!Object.hasOwn(descriptor,'value'))throw new TypeError('Current skills require detached own data properties.');
 return descriptor.value===undefined?{present:false}:{present:true,value:descriptor.value};
}
/** PF2e-specific one-Actor transformed contributor without source fallback. */
function raw(uuid,path,selected){return {document_uuid:uuid,path,...selected,basis:'transformed'};}
/** PF2e-specific bounded skill DTO with explicit extraction provenance. */
function record(key,kind,concept,evidence,value,mapping='pf2e.actor.skills-current.v1',limitations=LIMIT){return {key,section:'skills',kind,raw:evidence,mapped:{concept,value,unit:null},provenance:{contributors:evidence.map(({document_uuid,path,basis})=>({document_uuid,path,basis})),mapping,limitations:[...limitations]}};}

/**
 * PF2e-specific selected current skills for actual character/NPC Actors. Familiar
 * remains unsupported here and is never serialized. Preserve existing separate
 * owned Lore source listings: prepared keys may collapse multiple owned Items.
 * Bounds: 512 own skill keys, 1–256 Unicode code points per key, 12000 owned Items,
 * 24000 selected records. Missing declared leaves stay unavailable. NPC special
 * variants/predicates and target-dependent modifiers are not evaluated.
 * A Lore claim pointing to an unreadable actual owner Item withholds the entire
 * skill, including its generated key and labels, and adds one aggregate denial.
 * Returns {records,reasons}; caller snapshots it for continuation revisions.
 */
export function actorSkillsSnapshot(target){
 const actor=target.document;
 if(actor.documentName!=='Actor'||!['character','npc','familiar'].includes(actor.type))throw new TypeError('Current skills require a supported Actor.');
 if(actor.type==='familiar')return {records:[],reasons:['other_skills_pending']};
 const items=[...actor.items.values()];if(items.length>12000)throw new TypeError('Current skills exceed 12000 owned Items.');
 const itemsById=new Map(items.map(item=>[item.id,item]));
 const serialized=actor.toObject(false),type=own(serialized,'type');if(!type.present||type.value!==actor.type)throw new TypeError('Current skill serialization type does not match the Actor.');
 const system=own(serialized,'system'),skills=system.present?own(system.value,'skills'):{present:false};
 const reasons=new Set(['other_skills_pending',...(actor.type==='npc'?['conditional_skill_variants_not_evaluated']:[])]),records=[];
 const unavailable=()=>reasons.add('current_skill_fields_unavailable');
 if(!skills.present){unavailable();records.push(record('skills:current:/system/skills','field','current_skill_collection',[raw(actor.uuid,'/system/skills',{present:false})],null));return {records,reasons:[...reasons].sort()};}
 if(skills.value===null||typeof skills.value!=='object'||Array.isArray(skills.value))throw new TypeError('Current skills must be a detached object map.');
 const keys=Object.getOwnPropertyNames(skills.value);if(keys.length>512)throw new TypeError('Current skills exceed 512 keys.');
 if(!keys.length)records.push(record('skills:current:/system/skills','field','current_skill_collection',[raw(actor.uuid,'/system/skills',{present:true,value:{}})],null));
 let denied=false;
 for(const key of keys){
  if([...key].length<1||[...key].length>256)throw new TypeError('Current skill keys must contain 1–256 code points.');
  const selected=own(skills.value,key);if(!selected.present)throw new TypeError('Current skill entry must be an own data object.');
  const skill=selected.value,path=`/system/skills/${escape(key)}`;
  /** PF2e-specific scalar validation; no ordinary-field access before privacy. */
  const select=(leaf,kind,nullable=false)=>{const result=own(skill,leaf);if(result.present&&!(nullable&&result.value===null)&&(kind==='rank'?(!Number.isInteger(result.value)||result.value<0||result.value>4):typeof result.value!==kind||kind==='number'&&!Number.isFinite(result.value)))throw new TypeError(`Current skill ${path}/${leaf} has an unexpected value.`);return result;};
  const lore=select('lore','boolean'),itemId=select('itemId','string',true);
  const claim=lore.value===true&&typeof itemId.value==='string'&&itemId.value!==''?itemsById.get(itemId.value):null;
  if(claim&&!permitted(claim)){denied=true;continue;}
  const specifications=[['slug','string'],['label','string'],['attribute','string'],['value','number'],['totalModifier','number'],['dc','number'],['breakdown','string'],['lore','boolean'],['itemId','string',true],...(actor.type==='character'?[['rank','rank'],['armor','boolean']]:[['base','number'],['mod','number'],['visible','boolean'],['note','string']])];
  for(const [leaf,kind,nullable]of specifications){
   const value=leaf==='lore'?lore:leaf==='itemId'?itemId:select(leaf,kind,nullable);
   if(value.present&&leaf==='attribute'&&!['str','dex','con','int','wis','cha'].includes(value.value))throw new TypeError('Current skill attribute is unsupported.');
   if(!value.present&&leaf!=='note')unavailable();
   records.push(record(`skills:current:${path}/${leaf}`,'field',`current_skill_${leaf==='itemId'?'item_id':leaf==='totalModifier'?'total_modifier':leaf}`, [raw(actor.uuid,`${path}/${leaf}`,value)],value.present?(kind==='rank'?{rank:value.value,label:RANKS[value.value]}:value.value):null));
  }
  if(lore.value===true){
   let value={status:'missing',target_uuid:null};
   if(claim){
    if(claim.documentName!=='Item'||claim.parent!==actor||claim.type!=='lore')value={status:'unsupported',target_uuid:null};
    else{const identity=embeddedIdentity(claim,{document:actor,token:target.token});value={status:'resolved',target_uuid:identity.uuid,document_name:'Item',type:'lore',name:identity.name,name_truncated:identity.name_truncated,...(target.token?{token_uuid:target.token.uuid}:{})};}
   }
   records.push(record(`skills:current-lore:${escape(key)}`,'relationship','current_skill_lore_reference',[raw(actor.uuid,`${path}/lore`,lore),raw(actor.uuid,`${path}/itemId`,itemId)],value,'pf2e.actor.skills-lore.v1',LORE_LIMIT));
  }
  if(records.length>24000)throw new TypeError('Current skills exceed 24000 selected records.');
 }
 if(denied){reasons.add('current_skill_items_denied');records.push(record('skills:current:denied','relationship','current_skill_item_reference',[],{status:'denied',target_uuid:null}));}
 return {records,reasons:[...reasons].sort()};
}
