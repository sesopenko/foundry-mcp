/**
 * PF2e-specific condition references8.6.1/core14.369. Source schema:
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/condition/data.ts
 * Public actual owned Item identity/permissions use actorDocuments.js. No UUID
 * construction, slug resolution, suppression calculation or target source read.
 */
import {conditionFields} from './actorCondition.js';
import {embeddedIdentity,permitted,ITEM_TYPES} from './actorDocuments.js';
/** PF2e-specific detached condition reference descriptors; selected source only. */
export function conditionReferenceFields(source){return conditionFields(source).filter(field=>field.path.startsWith('/system/references/')||field.path==='/system/overrides'||field.path.startsWith('/system/overrides/'));}
/**
 * PF2e-specific condition local-ID resolution within the actual owning Actor.
 * Parent may be any supported Item; other local reference lists require condition.
 * Override slugs remain unverified named claims, never manufactured Item UUIDs.
 * No actor owner means no local-ID scope. Unreadable target metadata is omitted.
 */
export function conditionRelationships(target,fields){
 const output=[];
 for(const field of fields){
  if(field.path.endsWith('/type'))continue;
  const parent=field.path.startsWith('/system/references/parent');
  const group=field.path.split('/')[3];
  const slug=field.path.startsWith('/system/overrides');
  const concept=slug?'condition_override_slug':parent?'condition_parent_reference':({children:'condition_child_reference',overrides:'condition_override_reference',overriddenBy:'condition_overridden_by_reference'})[group];
  const raw=[field];
  const id=field.path.endsWith('/id');
  if(id&&!parent){const type=fields.find(candidate=>candidate.path===field.path.slice(0,-2)+'type');if(type)raw.push(type);}
  let result={status:'missing',target_uuid:null};
  if(field.present&&typeof field.value==='string'&&field.value!==''){
   if(slug||!target.actor)result={status:'unverified',target_uuid:null};
   else{
    const item=[...target.actor.items.values()].find(candidate=>candidate.id===field.value);
    if(item){
     if(!permitted(item))result={status:'denied',target_uuid:null};
     else if(!ITEM_TYPES.includes(item.type)||(!parent&&item.type!=='condition'))result={status:'unsupported',target_uuid:null};
     else{
      const identity=embeddedIdentity(item,{document:target.actor,token:target.token});
      result={status:'resolved',target_uuid:identity.uuid,document_name:'Item',type:identity.type,name:identity.name,name_truncated:identity.name_truncated,...(target.token?{token_uuid:target.token.uuid}:{})};
     }
    }
   }
  }
  output.push({path:field.path,raw,concept,result});
 }
 return output;
}
