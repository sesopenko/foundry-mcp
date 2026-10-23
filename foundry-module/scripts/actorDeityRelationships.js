/**
 * PF2e-specific deity8.6.1 spell definition UUID claims, Foundry14.369.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/deity/data.ts
 * Public immediate Item lookup is shared with book references. Keyed spell
 * entries remain source paths, not acquired or generated owned Items.
 */
import {resolveItemReference} from './actorItemReferences.js';
/**
 * PF2e-specific explicit immediate deity spell identity links (maximum200).
 * No target source or linked target spell is read, imported or recursively expanded.
 * Each keyed occurrence retains its source path, including repeated UUIDs;
 * duplicate targets share a lookup only within this snapshot. No local entry key
 * is used as a document UUID. Shared reader snapshots revalidate the results.
 */
export async function deityRelationships(target,fields){
 const references=fields.filter(field=>field.concept==='deity_spell_uuid'||field.path==='/system/spells');
 if(references.length>200)throw new TypeError('Deity relationships exceed200 source references.');
 const cache=new Map(),records=[];
 for(const field of references){
  let result;
  if(field.path==='/system/spells')result={status:field.present?'empty':'missing',target_uuid:null};
  else if(!field.present)result={status:'missing',target_uuid:null};
  else{if(!cache.has(field.value))cache.set(field.value,await resolveItemReference(field.value));result=cache.get(field.value);if(result.status==='resolved'&&result.type!=='spell')result={status:'unsupported',target_uuid:null};}
  const raw=[{document_uuid:target.identity.uuid,path:field.path,present:field.present,...(field.present?{value:field.value}:{}),basis:'source'}];
  records.push({key:'relationships:deity:'+field.path,section:'relationships',kind:'relationship',raw,
   mapped:{concept:'deity_spell_reference',value:result,unit:null},provenance:{contributors:raw.map(({document_uuid,path,basis})=>({document_uuid,path,basis})),mapping:'pf2e.deity.spell-reference.v1',limitations:['listed_spell_not_learned_or_prepared']}});
 }
 return records;
}
