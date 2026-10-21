/**
 * PF2e-specific weapon selectedAmmoId8.6.1/core14.369 source reference.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/weapon/data.ts
 * Actual owner Items and public identities use actorDocuments.js. No prepared
 * ammo getter, reload/compatibility logic, loaded subitems, rolls or consumption.
 */
import {embeddedIdentity,permitted} from './actorDocuments.js';
/** PF2e-specific selected source local ID; absent/null remain distinguishable. */
export function weaponAmmoReference(source){
 const system=source.system;const present=system!==null&&typeof system==='object'&&Object.hasOwn(system,'selectedAmmoId');
 const value=system?.selectedAmmoId;
 if(present&&value!==null&&typeof value!=='string')throw new TypeError('Stored selectedAmmoId must be source string or null.');
 return {path:'/system/selectedAmmoId',present,...(present?{value}:{})};
}
/**
 * PF2e-specific immediate selected local-ID lookup within the actual owner.
 * A resolved ammo/weapon identity is only a stored selection, never proof of
 * compatibility, loaded ammunition, quantity, usability or final Strike bonuses.
 * No owner means unverified local scope. No target source is read or UUID built.
 */
export function weaponAmmoRelationship(target,reference){
 const unresolved=status=>({status,target_uuid:null});
 if(!reference.present||reference.value===null||reference.value==='')return unresolved('missing');
 if(!target.actor)return unresolved('unverified');
 const item=[...target.actor.items.values()].find(candidate=>candidate.id===reference.value);
 if(!item)return unresolved('missing');
 if(!permitted(item))return unresolved('denied');
 if(!['ammo','weapon'].includes(item.type))return unresolved('unsupported');
 const identity=embeddedIdentity(item,{document:target.actor,token:target.token});
 return {status:'resolved',target_uuid:identity.uuid,document_name:'Item',type:identity.type,name:identity.name,name_truncated:identity.name_truncated,...(target.token?{token_uuid:target.token.uuid}:{})};
}
