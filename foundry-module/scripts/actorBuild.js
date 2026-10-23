/**
 * PF2e-specific character Build source joins; Foundry14.369/PF2e8.6.1.
 * Public Actor.items, Item identity/permission and toObject(true) only.
 * Persisted schemas, never prepared benefits or acquisition inference:
 * https://github.com/foundryvtt/pf2e/tree/28d9d156f252d084371d994dc359509b49eadf18/src/module/item
 */
import {embeddedIdentity,permitted,ITEM_TYPES} from './actorDocuments.js';
import {ancestryFields} from './actorAncestry.js';
import {heritageFields} from './actorHeritage.js';
import {backgroundFields} from './actorBackground.js';
import {classFields} from './actorClass.js';
import {deityFields} from './actorDeity.js';
import {featFields} from './actorFeat.js';
import {featSelectionFields} from './actorFeatSelections.js';
import {itemGrantFields} from './actorFeatGrants.js';
import {loreFields} from './actorLore.js';
const SELECTORS={ancestry:ancestryFields,heritage:heritageFields,background:backgroundFields,class:classFields,deity:deityFields,feat:featFields,lore:source=>loreFields(source,'character')};
/** PF2e-specific 8.6.1 exact persisted contributor, no derived values. */
function raw(item,field){return {document_uuid:item.uuid,path:field.path,present:field.present,...(field.present?{value:field.value}:{}),basis:'source'};}
/** PF2e-specific 8.6.1 detached Build record; source provenance remains exact. */
function record(key,concept,raw,value,mapping,limitations,kind='field'){return {key,section:'build',kind,raw,mapped:{concept,value,unit:null},provenance:{contributors:raw.map(({document_uuid,path,basis})=>({document_uuid,path,basis})),mapping,limitations:[...limitations]}};}
/** PF2e-specific 8.6.1 cached source label; actual owned identity, no derived name. */
function identity(node,target){const id=embeddedIdentity(node.item,{document:target.document,token:target.token}),name=[...node.source.name];return {status:'resolved',target_uuid:id.uuid,document_name:'Item',type:id.type,name:name.slice(0,256).join(''),name_truncated:name.length>256,...(target.token?{token_uuid:target.token.uuid}:{})};}
/**
 * PF2e-specific character-only owned Build snapshot, pinned schema URL above.
 * Seven contributor types retain original typed source selectors. Exact local
 * grant IDs may resolve other supported owned types except affliction. Offered
 * definitions, labels and selections never resolve documents. Cached persisted
 * source is read once per readable donor; denied identities remain withheld.
 * Caller revalidates this complete snapshot for pagination. 12000 Item and
 * 24000 record bounds are independent of shared byte/count pagination.
 */
export function actorBuildRecords(target){
 const actor=target.document,records=[],reasons=new Set(),all=new Map(),nodes=new Map();
 if(actor.documentName!=='Actor'||actor.type!=='character')throw new TypeError('Build source requires a character Actor.');
 for(const item of actor.items.values()){if(all.size>=12000)throw new TypeError('Build source exceeds 12000 owned Items.');all.set(item.id,item);}
 /** PF2e-specific 8.6.1 bounded append, source-only snapshot. */
 const emit=row=>{if(records.length>=24000)throw new TypeError('Build source exceeds 24000 selected records.');records.push(row);};
 /** PF2e-specific 8.6.1 public owned source cache; permissions precede reads. */
 const read=item=>{if(nodes.has(item.id))return nodes.get(item.id);const source=item.toObject(true);if(source?.type!==item.type||typeof source.name!=='string')throw new TypeError('Build Item source identity is invalid.');const node={item,source,grants:itemGrantFields(source)};nodes.set(item.id,node);return node;};
 let denied=false;
 for(const item of all.values())if(Object.hasOwn(SELECTORS,item.type)){if(!permitted(item)){denied=true;continue;}read(item);}
 // PF2e-specific 8.6.1 direct claims only: do not recursively expand grants.
 const donors=[...nodes.values()];
 for(const donor of donors)for(const field of donor.grants)if(['grant_item_id','granted_by_item_id'].includes(field.concept)&&field.present&&field.value){const item=all.get(field.value);if(item&&permitted(item)&&ITEM_TYPES.includes(item.type)&&item.type!=='affliction')read(item);}
 const ordered=[...nodes.values()].sort((a,b)=>a.item.uuid<b.item.uuid?-1:a.item.uuid>b.item.uuid?1:0);
 for(const node of ordered){const {item,source}=node,typeRaw=raw(item,{path:'/type',present:true,value:source.type});
  emit(record('build:item:'+item.uuid,'build_item',[raw(item,{path:'/name',present:true,value:source.name}),typeRaw],identity(node,target),'pf2e.build.identity.v1',['owned_document_not_effective_benefit'],'relationship'));
  if(!Object.hasOwn(SELECTORS,item.type))continue;
  const fields=SELECTORS[item.type](source);
  if(item.type==='feat'){const selections=featSelectionFields(source);fields.push(...selections.fields);if(selections.issues.length)reasons.add('unsupported_selection_values');}
  for(const field of fields)emit(record(`build:source:${item.uuid}:${field.path}`,field.concept,[typeRaw,raw(item,field)],Object.hasOwn(field,'mapped_value')?field.mapped_value:field.present?field.value:null,`pf2e.${item.type}.source.v1`,field.limitations));
  for(const field of node.grants){
   emit(record(`build:source:${item.uuid}:${field.path}`,field.concept,[typeRaw,raw(item,field)],field.present?field.value:null,'pf2e.build.grants.v1',field.limitations));
   if(!['grant_item_id','granted_by_item_id'].includes(field.concept))continue;
   const outgoing=field.concept==='grant_item_id',actual=field.present&&field.value?all.get(field.value):null;
   let value={status:'missing',target_uuid:null},inverse=[];
   if(actual){if(!permitted(actual))value={status:'denied',target_uuid:null};else if(!ITEM_TYPES.includes(actual.type)||actual.type==='affliction')value={status:'unsupported',target_uuid:null};else value=identity(nodes.get(actual.id),target);}
   let reciprocity='not_evaluated';
   if(outgoing&&value.status==='resolved'){
    const targetNode=nodes.get(actual.id),witness=targetNode.grants.find(row=>row.concept==='granted_by_item_id')??targetNode.grants.find(row=>row.concept==='granted_by_source');
    inverse=[raw(actual,witness)];reciprocity=witness.concept==='granted_by_item_id'&&witness.present?(witness.value===item.id?'agree':'disagree'):'absent';
   }
   emit(record(`build:claim:${item.uuid}:${field.path}`,outgoing?'build_grant_claim':'build_granted_by_claim',[typeRaw,raw(item,field),...inverse],{...value,reciprocity},'pf2e.build.claim.v1',['persisted_claim_not_causality_or_active_benefit'],'relationship'));
   if(field.present&&field.value&&value.status!=='resolved')reasons.add('build_grant_target_'+value.status);
  }
 }
 if(denied){reasons.add('build_items_denied');emit(record('build:scope','build_scope',[],{status:'denied',target_uuid:null},'pf2e.build.identity.v1',['owned_document_not_effective_benefit'],'relationship'));}
 else if(!nodes.size)emit(record('build:scope','build_scope',[],{status:'empty',target_uuid:null},'pf2e.build.identity.v1',['owned_document_not_effective_benefit'],'relationship'));
 return {records,reasons:[...reasons].sort()};
}
