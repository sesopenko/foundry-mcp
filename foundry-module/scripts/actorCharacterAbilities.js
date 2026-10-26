/**
 * PF2e-specific character owned action/feat reference view, verified boundary
 * Foundry14.369/PF2e8.6.1. Public Actor.items, Item.parent/identity/permissions
 * and toObject(true) only. Persisted source names/types are witnesses; no sheet,
 * prepared activation, rules evaluation or exhaustive ability claim is used.
 * https://foundryvtt.com/api/v14/classes/foundry.documents.Actor.html
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/ability/data.ts
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/feat/data.ts
 */
import {embeddedIdentity, permitted} from './actorDocuments.js';

const LIMITATIONS=['owned_item_reference_not_complete_or_active_ability'];

/** PF2e-specific persisted identity leaf; never invoke selected accessors. */
function sourceLeaf(source,key) {
 if(source===null||typeof source!=='object')throw new TypeError('Character ability Item source must be an object.');
 const descriptor=Object.getOwnPropertyDescriptor(source,key);
 if(!descriptor||!Object.hasOwn(descriptor,'value')||typeof descriptor.value!=='string')throw new TypeError('Character ability source name/type requires own string data properties.');
 return descriptor.value;
}

/** PF2e-specific reference DTO; raw fields remain exact source witnesses. */
function record(key,raw,value) {
 return {key,section:'abilities',kind:'relationship',raw,mapped:{concept:'character_ability_item',value,unit:null},provenance:{contributors:raw.map(({document_uuid,path,basis})=>({document_uuid,path,basis})),mapping:'pf2e.character.ability-reference.v1',limitations:[...LIMITATIONS]}};
}

/**
 * PF2e-specific character action/feat Items, including all owned feat features.
 * Each source is checked only after permission and exact parent/membership.
 * Names are source-based, mapped labels clip to256 Unicode codepoints; raw
 * strings remain exact and reject over6000 UTF-16 units with actionable errors.
 * Follow canonical targets through read_item for activation/category/prose.
 * Other abilities/basic actions and effective application remain unevaluated.
 * Caller enforces ready/system/version, token authorization and shared paging;
 * this synchronous snapshot caps all owned Items at12000 and mutates nothing.
 */
export function characterAbilityRecords(target) {
 const actor=target.document;
 if(actor?.documentName!=='Actor'||actor.type!=='character')throw new TypeError('Character ability references require a character Actor.');
 if(actor.items.size>12000)throw new TypeError('Character ability owner exceeds12000 Items; read selected Items separately.');
 const entries=[],reasons=['other_abilities_not_enumerated'],seen=new Set();
 let denied=false,count=0;
 for(const item of actor.items.values()) {
  if(++count>12000)throw new TypeError('Character ability owner exceeds12000 Items; read selected Items separately.');
  if(!['action','feat'].includes(item.type))continue;
  if(item.parent!==actor||actor.items.get(item.id)!==item||seen.has(item.id))throw new TypeError('Character ability Item must have exact selected Actor parent and membership.');
  seen.add(item.id);
  if(!permitted(item)){denied=true;continue;}
  const source=item.toObject(true),name=sourceLeaf(source,'name'),type=sourceLeaf(source,'type');
  if(type!==item.type)throw new TypeError('Character ability source type differs from its actual Item.');
  if(name.length>6000)throw new TypeError('Character ability source name exceeds6000 UTF-16 units; shorten that Item name or read a smaller selection.');
  const identity=embeddedIdentity(item,target),codepoints=[...name];
  const raw=[{document_uuid:identity.uuid,path:'/name',present:true,value:name,basis:'source'},{document_uuid:identity.uuid,path:'/type',present:true,value:type,basis:'source'}];
  const value={status:'resolved',target_uuid:identity.uuid,type,name:codepoints.slice(0,256).join(''),name_truncated:codepoints.length>256};
  if(target.token)value.token_uuid=target.token.uuid;
  entries.push({name:name.toLowerCase(),uuid:identity.uuid,record:record('abilities:item:'+identity.uuid,raw,value)});
 }
 const compare=(a,b)=>a<b?-1:a>b?1:0;
 entries.sort((a,b)=>compare(a.name,b.name)||compare(a.uuid,b.uuid));
 const records=entries.map(entry=>entry.record);
 if(denied){reasons.push('ability_items_denied');records.push(record('abilities:items:denied',[],{status:'denied',target_uuid:null}));}
 return {records,reasons};
}
