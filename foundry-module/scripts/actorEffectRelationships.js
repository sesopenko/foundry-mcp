/**
 * PF2e-specific effect context8.6.1 references on core14.369; no expiry/math.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/abstract-effect/data.ts
 * Uses audited public document resolution/permissions through actorDocuments.js.
 * Explicit relationships only; never reads target source, imports, rolls or writes.
 */
import {actorTarget,itemTarget,named} from './actorDocuments.js';
export const EFFECT_REFERENCES=[['origin_actor','origin','actor'],['origin_token','origin','token'],['origin_item','origin','item'],['target_actor','target','actor'],['target_token','target','token']];
/** PF2e-specific context source lookup preserves absent/null without defaults. */
export function effectReferenceFields(source){
 const context=source.system?.context;
 if(context!==undefined&&context!==null&&(typeof context!=='object'||Array.isArray(context)))throw new TypeError('Effect context must be a source object or null.');
 for(const side of ['origin','target']){const value=context?.[side];if(value!==undefined&&value!==null&&(typeof value!=='object'||Array.isArray(value)))throw new TypeError('Effect context side must be a source object or null.');}
 return EFFECT_REFERENCES.map(([role,side,kind])=>{
  const context=source.system?.context?.[side];const present=context!==null&&typeof context==='object'&&Object.hasOwn(context,kind)&&context[kind]!==undefined;
  const value=context?.[kind];
  if(present&&value!==null&&typeof value!=='string')throw new TypeError('Effect context reference is not source UUID text.');
  return {role,path:`/system/context/${side}/${kind}`,present,...(present?{value}:{})};
 });
}
/** PF2e-specific bounded canonical reference; source strings are not selectors until checked. */
function valid(uuid){return typeof uuid==='string'&&uuid.length>0&&uuid.length<=512&&!uuid.includes('#')&&/^(Actor\.|Item\.|Compendium\.|Scene\.)/.test(uuid);}
/**
 * PF2e-specific immediate effect context resolution. Stored Actor/token pairs
 * must identify the same current Actor; a base template never substitutes it.
 * Item follow-ups retain supplied token context for linked or synthetic owners.
 * Errors become explicit per-link status, with no target identity on failure.
 */
export async function effectRelationships(fields){
 const lookup=role=>fields.find(field=>field.role===role);
 const output=[];
 for(const field of fields){
  const unresolved=status=>({status,target_uuid:null});let result;
  if(!field.present||field.value===null||field.value==='')result=unresolved('missing');
  else if(!valid(field.value))result=unresolved('unsupported');
  else try{
   const [side,kind]=field.role.split('_');const tokenField=lookup(side+'_token');
   const tokenUuid=tokenField?.present&&tokenField.value!==null&&tokenField.value!==''?tokenField.value:null;
   if(kind!=='token'&&tokenUuid!==null&&!valid(tokenUuid)){output.push({...field,result:unresolved('unsupported')});continue;}
   let target,document,selectedToken=null;
   if(kind==='token'){
    target=await actorTarget({token_uuid:field.value});document=target.token;selectedToken=target.token.uuid;
   }else if(kind==='actor'){
    target=await actorTarget(tokenUuid?{token_uuid:tokenUuid}:{actor_uuid:field.value});document=target.document;
    if(document.uuid!==field.value){output.push({...field,result:unresolved('unverified')});continue;}
    selectedToken=target.token?.uuid??null;
   }else{
    if(field.value.startsWith('Scene.')&&!tokenUuid){output.push({...field,result:unresolved('unverified')});continue;}
    target=await itemTarget({item_uuid:field.value,...(field.value.startsWith('Scene.')&&tokenUuid?{token_uuid:tokenUuid}:{})});
    if(target.actor&&tokenUuid&&!target.token)target=await itemTarget({item_uuid:field.value,token_uuid:tokenUuid});
    document=target.document;selectedToken=target.token?.uuid??null;
    const actorField=lookup(side+'_actor');
    if(target.actor&&actorField?.present&&typeof actorField.value==='string'&&target.actor.uuid!==actorField.value){output.push({...field,result:unresolved('unverified')});continue;}
   }
   result={status:'resolved',target_uuid:document.uuid,document_name:document.documentName,...named(document),...(selectedToken?{token_uuid:selectedToken}:{})};
  }catch(error){
   const code=error?.rpcError?.code;
   result=unresolved(code==='PermissionDenied'?'denied':['DocumentNotFound','ActorUnavailable'].includes(code)?'missing':['InvalidRequest','UnsupportedType','UnsupportedVersion'].includes(code)?'unsupported':'unverified');
  }
  output.push({...field,result});
 }
 return output;
}
