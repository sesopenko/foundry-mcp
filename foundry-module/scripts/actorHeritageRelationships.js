/**
 * PF2e-specific heritage8.6.1 nullable ancestry association, Foundry14.369.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/heritage/data.ts
 * Immediate public Item identity resolver only; no target source or owner ancestry
 * lookup, heritage acquisition, eligibility, exclusivity or rule application.
 */
import {resolveItemReference} from './actorItemReferences.js';
/**
 * PF2e-specific explicit immediate heritage ancestry definition reference.
 * Null means no stored association, not proof of the owner's ancestry or a full
 * eligibility decision. Absent association/UUID stays missing. A resolved target
 * must actually be an ancestry Item and keeps its own canonical/token context.
 * Caller snapshots recheck source, resolved identity/name and permissions.
 */
export async function heritageRelationship(target,fields){
 const field=fields.find(f=>f.path==='/system/ancestry')??fields.find(f=>f.path==='/system/ancestry/uuid');
 if(!field)throw new TypeError('Heritage ancestry descriptor is missing.');
 let result;
 if(!field.present)result={status:'missing',target_uuid:null};
 else if(field.path==='/system/ancestry')result={status:'unassociated',target_uuid:null};
 else{result=await resolveItemReference(field.value);if(result.status==='resolved'&&result.type!=='ancestry')result={status:'unsupported',target_uuid:null};}
 const raw=[{document_uuid:target.identity.uuid,path:field.path,present:field.present,...(field.present?{value:field.value}:{}),basis:'source'}];
 return {key:'relationships:heritage:ancestry',section:'relationships',kind:'relationship',raw,
  mapped:{concept:'heritage_ancestry_reference',value:result,unit:null},provenance:{contributors:raw.map(({document_uuid,path,basis})=>({document_uuid,path,basis})),mapping:'pf2e.heritage.ancestry-reference.v1',limitations:['ancestry_association_not_owner_membership']}};
}
