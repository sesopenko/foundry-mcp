/**
 * PF2e-specific Actor inventory source joins, Foundry14.369/PF2e8.6.1.
 * Public Actor.items, Item identities, permissions and toObject(true) only.
 * Persisted physical/container/weapon schemas:
 * https://github.com/foundryvtt/pf2e/tree/28d9d156f252d084371d994dc359509b49eadf18/src/module/item
 * No inventory getter, prepared Bulk, activation, price calculation or writes.
 */
import {embeddedIdentity,permitted} from './actorDocuments.js';
import {PHYSICAL_TYPES,physicalFields} from './actorPhysical.js';
import {weaponAmmoReference} from './actorWeaponRelationships.js';
const LIMIT=['stored_inventory_not_effective_benefits'];
/** PF2e-specific exact physical source parent claim; missing is not null. */
function containerReference(source){
 const present=source.system!==null&&typeof source.system==='object'&&Object.hasOwn(source.system,'containerId'),value=source.system?.containerId;
 if(present&&value!==null&&typeof value!=='string')throw new TypeError('Inventory source /system/containerId must be a string or null.');
 return {path:'/system/containerId',present,...(present?{value}:{})};
}
/** PF2e-specific source-only bounded record; caller handles pagination/text. */
function record(key,concept,raw,value,kind='relationship',mapping='pf2e.actor.inventory-source.v1',limitations=LIMIT){
 return {key,section:'inventory',kind,raw,mapped:{concept,value,unit:null},provenance:{contributors:raw.map(({document_uuid,path,basis})=>({document_uuid,path,basis})),mapping,limitations:[...limitations]}};
}
/** PF2e-specific exact persisted Item contributor, with no fabricated identity. */
function raw(item,selected){return {document_uuid:item.uuid,...selected,basis:'source'};}
/** PF2e-specific actual same-owner Item identity retaining selected token.
 * Display labels use cached persisted source names, never prepared magic names. */
function identity(item,target,source){const value=embeddedIdentity(item,{document:target.document,token:target.token}),name=[...source.name];return {status:'resolved',target_uuid:value.uuid,document_name:'Item',type:value.type,name:name.slice(0,256).join(''),name_truncated:name.length>256,...(target.token?{token_uuid:target.token.uuid}:{})};}
/**
 * PF2e-specific owner-wide physical inventory source snapshot.
 * Every actual physical Item occurs once, including disconnected/orphan/cyclic
 * components. Each parent edge is a stored local-ID claim. cycle=true means
 * following readable physical parent claims reaches a cycle, including a tail
 * entering that cycle; false does not prove inaccessible data is acyclic.
 * Books retain common possession facts with specialty interpretation partial.
 * Kits and serialized subitems never become owned Item document identities.
 * Returns detached {records,reasons}; shared reader applies byte/continuation
 * bounds and revision revalidation. Limits: 12000 owner Items/24000 records.
 */
export function actorInventoryRecords(target){
 const actor=target.document,records=[],reasons=new Set();
 if(actor.documentName!=='Actor'||!['character','npc','familiar'].includes(actor.type))throw new TypeError('Inventory source requires a supported Actor.');
 const items=[...actor.items.values()];if(items.length>12000)throw new TypeError('Inventory source exceeds 12000 owned Items.');
 const all=new Map(items.map(item=>[item.id,item])),nodes=new Map(),kits=[];let denied=false;
 for(const item of items){
  if(!PHYSICAL_TYPES.includes(item.type)&&item.type!=='kit')continue;
  if(!permitted(item)){denied=true;continue;}
  const source=item.toObject(true);
  if(source?.type!==item.type||typeof source.name!=='string')throw new TypeError('Inventory Item source identity is invalid.');
  if(item.type==='kit')kits.push({item,source});else nodes.set(item.id,{item,source,ref:containerReference(source)});
 }
 // PF2e-specific functional source graph: memoize each ancestry once; no depth recursion.
 const cycles=new Map();
 for(const id of nodes.keys()){
  if(cycles.has(id))continue;
  const path=[],positions=new Set();let current=id,cycle=false;
  while(nodes.has(current)&&!cycles.has(current)){
   if(positions.has(current)){cycle=true;break;}
   positions.add(current);path.push(current);const next=nodes.get(current).ref.value;
   if(typeof next!=='string'||!next){current=null;break;}current=next;
  }
  if(cycles.has(current))cycle=cycles.get(current);
  for(const member of path)cycles.set(member,cycle);
 }
 /** PF2e-specific same-owner stored-ID lookup; denied identity stays withheld. */
 const resolve=(reference,types)=>{
  if(!reference.present||reference.value===null||reference.value==='')return {status:'missing',target_uuid:null};
  const item=all.get(reference.value);if(!item)return {status:'missing',target_uuid:null};
  if(!permitted(item))return {status:'denied',target_uuid:null};
  if(!types.includes(item.type))return {status:'unsupported',target_uuid:null};
  const source=nodes.get(item.id)?.source;if(!source)return {status:'denied',target_uuid:null};
  return identity(item,target,source);
 };
 for(const {item,source,ref}of [...nodes.values()].sort((a,b)=>a.item.uuid<b.item.uuid?-1:a.item.uuid>b.item.uuid?1:0)){
  records.push(record('inventory:item:'+item.uuid,'inventory_item',[raw(item,{path:'/name',present:true,value:source.name}),raw(item,{path:'/type',present:true,value:source.type})],identity(item,target,source)));
  for(const field of physicalFields(source).filter(field=>field.concept!=='unidentified_description')){
   records.push(record(`inventory:source:${item.type}:${item.uuid}:${field.path}`,field.concept,[raw(item,{path:field.path,present:field.present,...(field.present?{value:field.value}:{})})],field.present?field.value:null,'field','pf2e.physical.source.v1',field.limitations));
  }
  const parent={...resolve(ref,['backpack']),cycle:cycles.get(item.id)===true};
  records.push(record('inventory:container:'+item.uuid,'inventory_container',[raw(item,ref)],parent));
  if(parent.cycle)reasons.add('containment_cycle');
  if(ref.present&&ref.value&&parent.status!=='resolved')reasons.add('container_parent_'+parent.status);
  if(item.type==='weapon'){
   const selected=weaponAmmoReference(source),ammo=resolve(selected,['ammo','weapon']);
   records.push(record('inventory:ammunition:'+item.uuid,'inventory_selected_ammunition',[raw(item,selected)],ammo));
   if(selected.present&&selected.value&&ammo.status!=='resolved')reasons.add('selected_ammunition_'+ammo.status);
  }
  if(item.type==='book')reasons.add('book_interpretation_pending');
  if(records.length>24000)throw new TypeError('Inventory source exceeds 24000 selected records.');
 }
 for(const {item,source}of kits.sort((a,b)=>a.item.uuid<b.item.uuid?-1:a.item.uuid>b.item.uuid?1:0)){
  records.push(record('inventory:kit:'+item.uuid,'inventory_kit_definition',[raw(item,{path:'/name',present:true,value:source.name}),raw(item,{path:'/type',present:true,value:source.type})],identity(item,target,source)));
  reasons.add('kit_interpretation_pending');
 }
 if(denied){reasons.add('inventory_items_denied');records.push(record('inventory:scope','inventory_scope',[],{status:'denied',target_uuid:null}));}
 else if(!nodes.size&&!kits.length)records.push(record('inventory:scope','inventory_scope',[],{status:'empty',target_uuid:null}));
 if(records.length>24000)throw new TypeError('Inventory source exceeds 24000 selected records.');
 return {records,reasons:[...reasons].sort()};
}
