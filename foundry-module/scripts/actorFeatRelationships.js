/**
 * PF2e-specific feat8.6.1 persisted references, tested public boundary core14.369.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/base/data/system.ts
 * Public collections/identity: https://foundryvtt.com/api/v14/modules/foundry.documents.html
 * Feat selfEffect/suppressedFeatures: same revision item/feat/data.ts.
 * Owner-local grant IDs resolve only through the actual Actor.items collection;
 * UUID claims use the shared public document resolver. Neither proves active
 * benefits, reciprocal grant causality, eligibility or executed rules.
 */
import {resolveItemReference} from './actorItemReferences.js';
import {permitted} from './actorDocuments.js';
/** PF2e-specific unresolved feat reference result; no target identity disclosed. */
function unresolved(status){return {status,target_uuid:null};}
/**
 * PF2e-specific feat grant ID claim within its exact current Actor instance.
 * No name/base-Actor/source-ID fallback. Actual owner membership is checked
 * before and after public resolution, with permissions before target metadata.
 * Target source and reciprocal flags are never read; existence is not causality.
 */
async function owned(target,id){
 if(typeof id!=='string'||!id||id.length>512||/[.\s/#]/.test(id))return unresolved('unsupported');
 const owner=target.actor;
 if(!owner)return unresolved('unowned');
 if(!permitted(owner))return unresolved('denied');
 const candidate=owner.items.get(id);
 if(!candidate)return unresolved('missing');
 if(!permitted(candidate))return unresolved('denied');
 if(candidate.documentName!=='Item'||candidate.parent!==owner||candidate.uuid!==owner.uuid+'.Item.'+id)return unresolved('unsupported');
 const result=await resolveItemReference(candidate.uuid);
 if(result.status!=='resolved')return result;
 if(!permitted(owner)||!permitted(candidate))return unresolved('denied');
 if(owner.items.get(id)!==candidate||candidate.parent!==owner||candidate.uuid!==result.target_uuid)return unresolved('unverified');
 return result;
}
/**
 * PF2e-specific explicit feat reference records, maximum200 source occurrences.
 * Absence, empty lists/maps and explicit null remain distinct. Grants identify
 * actual same-owner Items only. selfEffect requires an effect, suppressedFeatures
 * requires feat targets; neither applies an effect or establishes suppression.
 * Each source occurrence retains provenance. Shared snapshots revalidate results
 * after awaits and on every continuation; no recursion, writes or target source.
 */
export async function featRelationships(target,fields){
 const concepts=new Map([['feat_grant_item_id','feat_grant_reference'],['feat_grant_entries','feat_grant_reference'],['feat_granted_by_item_id','feat_granted_by_reference'],['feat_granted_by_source','feat_granted_by_reference'],['feat_self_effect_uuid','feat_self_effect_reference'],['feat_self_effect_source','feat_self_effect_reference'],['feat_suppressed_feature_uuid','feat_suppressed_feature_reference']]);
 const references=fields.filter(field=>concepts.has(field.concept));
 if(references.length>200)throw new TypeError('Feat relationships exceed200 source references.');
 const records=[];
 for(const field of references){
  const concept=concepts.get(field.concept);let result;
  if(!field.present)result=unresolved('missing');
  else if(field.value===null)result=unresolved('unassociated');
  else if(typeof field.value==='object')result=unresolved('empty');
  else if(['feat_grant_item_id','feat_granted_by_item_id'].includes(field.concept))result=await owned(target,field.value);
  else{
   result=await resolveItemReference(field.value);
   const expected=field.concept==='feat_self_effect_uuid'?'effect':'feat';
   if(result.status==='resolved'&&result.type!==expected)result=unresolved('unsupported');
  }
  const raw=[{document_uuid:target.identity.uuid,path:field.path,present:field.present,...(field.present?{value:field.value}:{}),basis:'source'}];
  records.push({key:'relationships:feat:'+field.path,section:'relationships',kind:'relationship',raw,mapped:{concept,value:result,unit:null},provenance:{contributors:raw.map(({document_uuid,path,basis})=>({document_uuid,path,basis})),mapping:'pf2e.feat.reference.v1',limitations:['persisted_reference_not_active_benefit']}});
 }
 return records;
}
