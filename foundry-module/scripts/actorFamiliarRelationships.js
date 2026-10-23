/**
 * PF2e-specific familiar source relationships, Foundry14.369/PF2e8.6.1.
 * Pinned schema: https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/familiar/data.ts
 * master.id is a nullable Character foreign-document ID, never a token selector.
 * Public APIs: https://foundryvtt.com/api/v14/classes/foundry.documents.Actor.html
 * Only game.actors.get, public identities/permissions and toObject(true) are used.
 * No master getter, preparation, statistics or ability activation is evaluated.
 */
import {actorTarget,embeddedIdentity,permitted,named} from './actorDocuments.js';
import {fail} from './actorReadUtils.js';

/** PF2e-specific familiar source contributor, detached primitive evidence only. */
function raw(uuid,field){return {document_uuid:uuid,path:field.path,present:field.present,...(field.present?{value:field.value}:{}),basis:'source'};}
/** PF2e-specific familiar relationship DTO; source is never derived state. */
function record(key,section,concept,evidence,value,mapping,limitation){return {key,section,kind:'relationship',raw:evidence,mapped:{concept,value,unit:null},provenance:{contributors:evidence.map(({document_uuid,path,basis})=>({document_uuid,path,basis})),mapping,limitations:[limitation]}};}

/**
 * PF2e-specific familiar master.id source link to one actual world character.
 * Stored source evidence survives lookup failure; denied targets reveal no identity.
 * Caller re-snapshots source and relationship after awaits for revision safety.
 */
export async function familiarMasterRelationship(target,field){
 if(target.document.type!=='familiar'||field?.path!=='/system/master/id')throw new TypeError('Expected familiar master ID descriptor.');
 let value={status:'missing',target_uuid:null};
 if(field.present&&field.value===null)value={status:'unassociated',target_uuid:null};
 else if(field.present&&field.value){
  try{
   const master=game.actors.get(field.value);
   if(master){
    if(!permitted(master))value={status:'denied',target_uuid:null};
    else if(master.documentName!=='Actor'||master.type!=='character')value={status:'unsupported',target_uuid:null};
    else if(master.id!==field.value||master.compendium||master.parent||master.uuid!==`Actor.${master.id}`)value={status:'unverified',target_uuid:null};
    else{
     const resolved=await actorTarget({actor_uuid:master.uuid});
     if(resolved.document!==master||resolved.token||resolved.identity.uuid!==master.uuid||resolved.identity.id!==field.value||resolved.identity.type!=='character')value={status:'unverified',target_uuid:null};
     else value={status:'resolved',target_uuid:master.uuid,document_name:'Actor',type:'character',...named(master),next_call:{tool:'read_actor',arguments:{actor_uuid:master.uuid}}};
    }
   }
  }catch(error){value={status:error?.rpcError?.code==='PermissionDenied'?'denied':'unverified',target_uuid:null};}
 }
 return {record:record('identity:familiar_master','identity','familiar_master',[raw(target.identity.uuid,field)],value,'pf2e.familiar.master.v1','stored_master_reference_not_current_statistics'),reasons:value.status==='resolved'?[]:['familiar_master_'+value.status]};
}

/**
 * PF2e-specific familiar actual owned action Items, source-only partial abilities.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/ability/data.ts
 * Pinned src/scripts/config/traits.ts actionTraits defines neither familiar nor
 * master; packs/pf2e/familiar-abilities/accompanist.json and restorative-familiar.json
 * use category with empty traits. No machine-readable familiar/master discriminator
 * is verified. Classification therefore stays unclassified
 * rather than inventing unsupported trait semantics or inferring from category.
 * Bounds: 12000 owned Items, 24000 records, 200 complete trait leaves per Item.
 * Denied Items are never serialized or named. Caller re-snapshots for revision.
 */
export function familiarAbilityRecords(target){
 if(target.document.documentName!=='Actor'||target.document.type!=='familiar')throw new TypeError('Familiar abilities require a familiar Actor.');
 const records=[],seen=new Set();let count=0,denied=false;
 for(const item of target.document.items.values()){
  if(++count>12000)fail('ReadFailed','Familiar abilities exceed 12000 owned Items.','Use list_actor_items and read_item for selected abilities.');
  if(item.type!=='action')continue;
  if(!permitted(item)){denied=true;continue;}
  const id=embeddedIdentity(item,target);
  if(seen.has(id.uuid))continue;
  seen.add(id.uuid);
  const source=item.toObject(true);
  if(source?.type!=='action'||typeof source.name!=='string')fail('ReadFailed','Familiar ability source identity is invalid.','Inspect the selected owned action with read_item.');
  const traits=source.system?.traits?.value,evidence=[raw(id.uuid,{path:'/name',present:true,value:source.name}),raw(id.uuid,{path:'/type',present:true,value:'action'})];
  if(traits===undefined)evidence.push(raw(id.uuid,{path:'/system/traits/value',present:false}));
  else{
   if(!Array.isArray(traits)||traits.length>200||Array.from(traits).some(value=>typeof value!=='string'))fail('ReadFailed','Familiar ability traits exceed 200 entries or do not match the source schema.','Read the selected owned action with read_item.');
   if(!traits.length)evidence.push(raw(id.uuid,{path:'/system/traits/value',present:true,value:[]}));
   else for(let index=0;index<traits.length;index++)evidence.push(raw(id.uuid,{path:`/system/traits/value/${index}`,present:true,value:traits[index]}));
  }
  const name=[...source.name],value={status:'resolved',target_uuid:id.uuid,document_name:'Item',type:'action',name:name.slice(0,256).join(''),name_truncated:name.length>256,ability_kind:'unclassified',...(target.token?{token_uuid:target.token.uuid}:{})};
  if(records.length>=24000)fail('ReadFailed','Familiar abilities exceed 24000 records.','Use list_actor_items and read_item for selected abilities.');
  const row=record('abilities:familiar:'+id.uuid,'abilities','familiar_ability',evidence,value,'pf2e.familiar.ability.v1','owned_action_reference_not_complete_or_active_ability');
  row.provenance.limitations.push('ability_scope_requires_description');records.push(row);
 }
 if(denied){const row=record('abilities:familiar:denied','abilities','familiar_ability',[],{status:'denied',target_uuid:null},'pf2e.familiar.ability.v1','owned_action_reference_not_complete_or_active_ability');row.provenance.limitations.push('ability_scope_requires_description');records.push(row);}
 return {records,reasons:['other_abilities_pending',...(denied?['related_items_denied']:[])]};
}
