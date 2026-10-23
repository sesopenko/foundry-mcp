/**
 * PF2e-specific book.contents8.6.1 immediate Item UUID references.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/book/data.ts
 * Public core14.369 fromUuid, Item.parent and Actor.token:
 * https://foundryvtt.com/api/v14/functions/foundry.utils.fromUuid.html
 * https://foundryvtt.com/api/v14/classes/foundry.documents.Actor.html#token
 * Uses the shared public document boundary; no target source, recursive
 * contents, preparation, acquisition, casting, imports or mutations.
 */
import {itemTarget,permitted} from './actorDocuments.js';
const LIMIT=['stored_book_contents_not_ownership_or_preparation'];
/** PF2e-specific detached book reference source and identity record. */
function record(target,field,result){
 const raw=[{document_uuid:target.identity.uuid,path:field.path,present:field.present,...(field.present?{value:field.value}:{}),basis:'source'}];
 return {key:'relationships:book:contents'+(field.path==='/system/contents'?'':':'+field.path.split('/').at(-1)),section:'relationships',kind:'relationship',raw,
  mapped:{concept:'book_content_reference',value:result,unit:null},provenance:{contributors:raw.map(({document_uuid,path,basis})=>({document_uuid,path,basis})),mapping:'pf2e.book.content-reference.v1',limitations:[...LIMIT]}};
}
/**
 * PF2e-specific explicit book content lookup: up to200 source references.
 * Duplicate claims keep distinct index records but reuse one resolution within
 * this snapshot. Only actual canonical Item UUIDs are admitted; no name search,
 * relative-ID inference or recursive reading. Unknown/denied targets expose no
 * identity. Resolved labels are document display names, not source book text.
 * The caller includes these detached results in revision/permission rechecks.
 */
export async function bookRelationships(target,fields){
 const contents=fields.filter(field=>field.path==='/system/contents'||/^\/system\/contents\/\d+$/.test(field.path));
 if(contents.length>200)throw new TypeError('Book relationships exceed200 source references.');
 const cache=new Map();
 /** PF2e-specific canonical content selector lookup; no source hydration. */
 const resolve=async uuid=>{
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
 };
 const records=[];
 for(const field of contents){
  let result;
  if(field.path==='/system/contents')result={status:field.present?'empty':'missing',target_uuid:null};
  else{if(!cache.has(field.value))cache.set(field.value,await resolve(field.value));result=cache.get(field.value);}
  records.push(record(target,field,result));
 }
 return records;
}
