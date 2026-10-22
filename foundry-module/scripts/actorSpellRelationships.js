/**
 * PF2e-specific spell location.value8.6.1/core14.369 source reference.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/spell/data.ts
 * Actual owner Items and public identities use actorDocuments.js. No prepared
 * casting getter, preparation, spell slots, casting methods, rolls or consumption.
 */
import {embeddedIdentity,permitted} from './actorDocuments.js';
/** PF2e-specific stored spell casting-entry local ID; absent/null remain distinguishable. */
export function spellEntryReference(source){
 const location=source.system?.location;const present=location!==null&&typeof location==='object'&&Object.hasOwn(location,'value');
 const value=location?.value;
 if(present&&value!==null&&typeof value!=='string')throw new TypeError('Stored spell location.value must be source string or null.');
 return {path:'/system/location/value',present,...(present?{value}:{})};
}
/**
 * PF2e-specific immediate selected local-ID lookup within the actual owner.
 * A resolved casting-entry identity is only a stored assignment, never proof of
 * spell availability, effective cast rank, slot resources or current castability.
 * No owner means unverified local scope. No target source is read or UUID built.
 */
export function spellEntryRelationship(target,reference){
 const unresolved=status=>({status,target_uuid:null});
 if(!reference.present||reference.value===null||reference.value==='')return unresolved('missing');
 if(!target.actor)return unresolved('unverified');
 const item=[...target.actor.items.values()].find(candidate=>candidate.id===reference.value);
 if(!item)return unresolved('missing');
 if(!permitted(item))return unresolved('denied');
 if(item.type!=='spellcastingEntry')return unresolved('unsupported');
 const identity=embeddedIdentity(item,{document:target.actor,token:target.token});
 return {status:'resolved',target_uuid:identity.uuid,document_name:'Item',type:identity.type,name:identity.name,name_truncated:identity.name_truncated,...(target.token?{token_uuid:target.token.uuid}:{})};
}
