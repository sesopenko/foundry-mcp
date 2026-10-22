/**
 * PF2e-specific backpack/physical containment source, core14.369/PF2e8.6.1.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/physical/data.ts
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/container/data.ts
 * Public actual owner Items, toObject(true), permissions and identities only.
 * Never use prepared contents, total Bulk, sheet state, enrichment or writes.
 */
import {embeddedIdentity,permitted} from './actorDocuments.js';
import {PHYSICAL_TYPES} from './actorPhysical.js';
const LIMIT=['stored_containment_not_effective_bulk'];
/** PF2e-specific exact nullable physical source local ID; no normalization. */
function reference(source){
 const present=source.system!==null&&typeof source.system==='object'&&Object.hasOwn(source.system,'containerId');
 const value=source.system?.containerId;
 if(present&&value!==null&&typeof value!=='string')throw new TypeError('Container source /system/containerId must be a string or null.');
 return {path:'/system/containerId',present,...(present?{value}:{})};
}
/** PF2e-specific source claim record with actual contributing document identity. */
function record(key,concept,document,selected,value){
 const raw=document?[{document_uuid:document.uuid,...selected,basis:'source'}]:[];
 return {key,section:'relationships',kind:'relationship',raw,mapped:{concept,value,unit:null},provenance:{contributors:raw.map(({document_uuid,path,basis})=>({document_uuid,path,basis})),mapping:'pf2e.container.contents.v1',limitations:[...LIMIT]}};
}
/** PF2e-specific public owned Item metadata; preserve selected token selector. */
function identity(item,target){const value=embeddedIdentity(item,{document:target.actor,token:target.token});return {status:'resolved',target_uuid:value.uuid,document_name:'Item',type:value.type,name:value.name,name_truncated:value.name_truncated,...(target.token?{token_uuid:target.token.uuid}:{})};}
/**
 * PF2e-specific selected container claim graph, not effective inventory or Bulk.
 * Each reachable descendant appears once; root never repeats as its own content.
 * Cycles and unsupported parent claims remain explicit. Unreadable potential
 * children disclose no identity and prevent an exhaustive empty claim. Unowned
 * documents have no local-ID contents scope. Returns detached {records,reasons}
 * for shared paging/revision checks. Caps owner scope at 12000 Items.
 */
export function containerRelationships(target,source){
 const records=[],reasons=new Set(),root=target.document,ref=reference(source);
 const unresolved=status=>({status,target_uuid:null,cycle:false});
 let parent=unresolved('missing');
 if(!target.actor){
  if(ref.present&&ref.value)parent=unresolved('unverified');
  records.push(record('relationships:container:parent','container_parent',root,ref,parent));
  records.push(record('relationships:container:scope','container_contents',null,null,{status:'unverified',target_uuid:null}));
  return {records,reasons:['container_scope_unverified']};
 }
 const all=[...target.actor.items.values()];
 if(all.length>12000)throw new TypeError('Container source exceeds 12000 owner Items.');
 const nodes=new Map();let denied=false;
 for(const item of all){
  if(!PHYSICAL_TYPES.includes(item.type))continue;
  if(!permitted(item)){denied=true;continue;}
  nodes.set(item.id,{item,ref:reference(item===root?source:item.toObject(true))});
 }
 let cycle=false,current=root.id;const ancestors=new Set([current]);
 while(nodes.has(current)){
  const next=nodes.get(current).ref.value;if(typeof next!=='string'||!next)break;
  if(ancestors.has(next)){cycle=true;break;}ancestors.add(next);current=next;
 }
 if(cycle)reasons.add('containment_cycle');
 if(ref.present&&ref.value){
  const candidate=all.find(item=>item.id===ref.value);
  if(!candidate){parent=unresolved('missing');reasons.add('container_parent_missing');}
  else if(!permitted(candidate)){parent=unresolved('denied');reasons.add('container_parent_denied');}
  else if(candidate.type!=='backpack'){parent=unresolved('unsupported');reasons.add('container_parent_unsupported');}
  else parent={...identity(candidate,target),cycle};
 }
 records.push(record('relationships:container:parent','container_parent',root,ref,parent));
 const byParent=new Map();
 for(const node of nodes.values())if(typeof node.ref.value==='string'&&node.ref.value){const siblings=byParent.get(node.ref.value)??[];siblings.push(node);byParent.set(node.ref.value,siblings);}
 const seen=new Set([root.id]),queue=[{item:root,depth:0}];let count=0;
 for(let q=0;q<queue.length;q++){
  const {item:parentItem,depth}=queue[q];
  for(const node of byParent.get(parentItem.id)??[]){
   if(seen.has(node.item.id)){reasons.add('containment_cycle');continue;}
   seen.add(node.item.id);count++;
   const parentStatus=parentItem.type==='backpack'?'resolved':'unsupported';
   if(parentStatus==='unsupported')reasons.add('container_parent_unsupported');
   records.push(record('relationships:container:content:'+node.item.uuid,'container_content',node.item,node.ref,{...identity(node.item,target),parent_uuid:parentItem.uuid,parent_status:parentStatus,depth:depth+1}));
   queue.push({item:node.item,depth:depth+1});
  }
 }
 if(denied){reasons.add('container_contents_denied');records.push(record('relationships:container:scope','container_contents',null,null,{status:'denied',target_uuid:null}));}
 else if(!count)records.push(record('relationships:container:scope','container_contents',null,null,{status:'empty',target_uuid:null}));
 return {records,reasons:[...reasons].sort()};
}
