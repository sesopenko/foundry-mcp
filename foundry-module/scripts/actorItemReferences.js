/**
 * PF2e-specific immediate Item UUID lookup for book/kit/ancestry definition claims.
 * Tested public document boundary: Foundry14.369/PF2e8.6.1.
 * https://foundryvtt.com/api/v14/functions/foundry.utils.fromUuid.html
 * https://foundryvtt.com/api/v14/classes/foundry.documents.Actor.html#token
 * Uses canonical public Item identity, Actor.token and supported owner types;
 * no target source, recursive definition expansion or inventory acquisition.
 * Persisted claim schemas: book/data.ts, kit/data.ts and ancestry/data.ts at
 * https://github.com/foundryvtt/pf2e/tree/28d9d156f252d084371d994dc359509b49eadf18/src/module/item
 */
import {itemTarget,permitted} from './actorDocuments.js';
/** PF2e-specific bounded canonical Item lookup; unresolved identities withheld.
 * Returns {status,target_uuid:null} or actual resolved Item display identity,
 * with token_uuid for synthetic targets. Does not inherit the claimant's owner.
 */
export async function resolveItemReference(uuid){
  if(typeof uuid!=='string'||!uuid||uuid.length>512||/\s|#/.test(uuid)||!/^(Item\.|Actor\.|Compendium\.|Scene\.)/.test(uuid))return {status:'unsupported',target_uuid:null};
  try{
   const params={item_uuid:uuid};
   if(uuid.startsWith('Scene.')){
    const item=await foundry.utils.fromUuid(uuid);
    if(!item)return {status:'missing',target_uuid:null};
    if(!permitted(item))return {status:'denied',target_uuid:null};
    const actor=item.parent;
    if(item.documentName!=='Item'||actor?.documentName!=='Actor')return {status:'unsupported',target_uuid:null};
    if(!permitted(actor))return {status:'denied',target_uuid:null};
    const token=actor.token;
    if(!token?.uuid)return {status:'unverified',target_uuid:null};
    params.token_uuid=token.uuid;
   }
   const resolved=await itemTarget(params),identity=resolved.identity;
   if(identity.uuid!==uuid)return {status:'unsupported',target_uuid:null};
   return {status:'resolved',target_uuid:identity.uuid,document_name:'Item',type:identity.type,name:identity.name,name_truncated:identity.name_truncated,...(resolved.token?{token_uuid:resolved.token.uuid}:{})};
  }catch(error){
   const code=error?.rpcError?.code;
   return {status:code==='PermissionDenied'?'denied':code==='DocumentNotFound'?'missing':['UnsupportedType','InvalidRequest'].includes(code)?'unsupported':'unverified',target_uuid:null};
  }
}
