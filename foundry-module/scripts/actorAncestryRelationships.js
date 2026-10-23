/**
 * PF2e-specific ancestry8.6.1 feature definition UUID claims, Foundry14.369.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/ancestry/data.ts
 * Public immediate Item lookup is shared with book references. Keyed feature
 * entries remain source paths, not acquired or generated owned Items.
 */
import {resolveItemReference} from './actorItemReferences.js';
/**
 * PF2e-specific explicit immediate ancestry feature identity links (maximum200).
 * No target source or linked target feature is read, imported or recursively expanded.
 * Each keyed occurrence retains its source path, including repeated UUIDs;
 * duplicate targets share a lookup only within this snapshot. No local entry key
 * is used as a document UUID. Shared reader snapshots revalidate the results.
 */
export async function ancestryRelationships(target,fields){
 const references=fields.filter(field=>field.concept==='ancestry_feature_uuid'||field.path==='/system/items');
 if(references.length>200)throw new TypeError('Ancestry relationships exceed200 source references.');
 const cache=new Map(),records=[];
 for(const field of references){
  let result;
  if(field.path==='/system/items')result={status:field.present?'empty':'missing',target_uuid:null};
  else if(!field.present)result={status:'missing',target_uuid:null};
  else{if(!cache.has(field.value))cache.set(field.value,await resolveItemReference(field.value));result=cache.get(field.value);}
  const raw=[{document_uuid:target.identity.uuid,path:field.path,present:field.present,...(field.present?{value:field.value}:{}),basis:'source'}];
  records.push({key:'relationships:ancestry:'+field.path,section:'relationships',kind:'relationship',raw,
   mapped:{concept:'ancestry_feature_reference',value:result,unit:null},provenance:{contributors:raw.map(({document_uuid,path,basis})=>({document_uuid,path,basis})),mapping:'pf2e.ancestry.feature-reference.v1',limitations:['definition_reference_not_acquired_feature']}});
 }
 return records;
}
