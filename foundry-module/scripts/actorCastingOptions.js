/**
 * PF2e-specific contextual source options for character/NPC/familiar owned spell
 * and spellcastingEntry Items, PF2e8.6.1. No APIs, getters or rank calculations.
 * Contracts: https://github.com/foundryvtt/pf2e/tree/28d9d156f252d084371d994dc359509b49eadf18/src/module/item
 * spell/data.ts location/base-rank/traits and spellcasting-entry/data.ts modes,
 * indexed preparations and slots. Actor focus source follows character/data.ts
 * (value only) or creature/data.ts (optional value/max); familiar focus excluded.
 * Configuration is not effective rank or availability; auto-heighten overrides
 * and signature flags are preserved without generating rank alternatives.
 */
const LIMITATIONS=['availability_not_evaluated','configured_rank_not_final_cast_rank'];

/** PF2e-specific selected own detached data; prototypes/accessors never read. */
function at(source,path){
 let value=source;
 for(const key of path.slice(1).split('/')){
  if(value===null||typeof value!=='object')throw new TypeError('Casting option source container is malformed.');
  const descriptor=Object.getOwnPropertyDescriptor(value,key);
  if(!descriptor)return {present:false};
  if(!Object.hasOwn(descriptor,'value'))throw new TypeError('Casting option source requires detached data properties.');
  value=descriptor.value;if(value===undefined)return {present:false};
 }
 return {present:true,value};
}

/**
 * PF2e-specific source-context joins; target is detached Actor identity, items
 * are readable actual-owned {identity,source} snapshots. relationshipRecords
 * are the existing casting-source assignment records, retaining canonical
 * denied/missing/unsupported statuses when an entry is not readable. No API is
 * called. Unresolved preparations remain existing casting_preparation records;
 * this helper emits only contexts for actual readable spells. Bounds: 12000
 * Item snapshots and 24000 options. Keys are response-local, never UUIDs.
 * Returns {records,reasons}; all cast_rank values are null and availability is
 * not_evaluated, including cantrips and fully populated resource counters.
 */
export function actorCastingOptions(target,items,actorSource,relationshipRecords=[]){
 if(!['character','npc','familiar'].includes(target.type)||at(actorSource,'/type').value!==target.type)throw new TypeError('Casting options require a matching supported Actor source.');
 if(!Array.isArray(items)||items.length>12000)throw new TypeError('Casting options exceed 12000 owned Items.');
 const records=[],reasons=new Set(['availability_not_evaluated']),byId=new Map(),preparationIndexes=new Map();let preparationCount=0;
 for(const row of items){const {identity,source}=row;if(!identity||identity.actor?.uuid!==target.uuid||at(source,'/type').value!==identity.type||typeof at(source,'/name').value!=='string'||byId.has(identity.id))throw new TypeError('Casting option Item source/owner identity is invalid.');byId.set(identity.id,row);}
 /** PF2e-specific single-pass preparation index shared by every assigned spell. */
 const preparationIndex=entry=>{
  if(preparationIndexes.has(entry.identity.id))return preparationIndexes.get(entry.identity.id);
  const indexBySpell=new Map();preparationIndexes.set(entry.identity.id,indexBySpell);
  const slots=at(entry.source,'/system/slots');
  if(slots.present&&(slots.value===null||typeof slots.value!=='object'||Array.isArray(slots.value))){reasons.add('malformed_slot');return indexBySpell;}
  for(let rank=0;rank<=10;rank++){
   const slot=at(entry.source,`/system/slots/slot${rank}`);
   if(slot.present&&(slot.value===null||typeof slot.value!=='object'||Array.isArray(slot.value))){reasons.add('malformed_slot');continue;}
   const path=`/system/slots/slot${rank}/prepared`,prepared=at(entry.source,path);
   if(!prepared.present)continue;
   if(!Array.isArray(prepared.value)){reasons.add('malformed_preparations');continue;}
   if(prepared.value.length>6000)throw new TypeError('Casting options exceed 6000 preparations in one slot.');
   preparationCount+=prepared.value.length;if(preparationCount>24000)throw new TypeError('Casting options exceed 24000 preparation positions.');
   for(let index=0;index<prepared.value.length;index++){
    const descriptor=Object.getOwnPropertyDescriptor(prepared.value,String(index));
    if(!descriptor||!Object.hasOwn(descriptor,'value')||descriptor.value===null||typeof descriptor.value!=='object'||Array.isArray(descriptor.value)){reasons.add('malformed_preparation');continue;}
    const id=at(descriptor.value,'/id');if(id.present&&id.value!==null&&typeof id.value!=='string'){reasons.add('malformed_preparation');continue;}if(typeof id.value==='string'){if(!indexBySpell.has(id.value))indexBySpell.set(id.value,[]);indexBySpell.get(id.value).push({rank,index,path});}
   }
  }
  if(at(entry.source,'/system/slots/slot11').present)reasons.add('template_slot11_no_spell_rank_semantics');
  return indexBySpell;
 };
 for(const spell of items.filter(row=>row.identity.type==='spell')){
  const assignment=at(spell.source,'/system/location/value');
  if(assignment.present&&assignment.value!==null&&typeof assignment.value!=='string')throw new TypeError('Casting option assignment must be a local Item ID.');
  const candidate=byId.get(assignment.value),entry=candidate?.identity.type==='spellcastingEntry'?candidate:null;
  let positions=entry?(preparationIndex(entry).get(spell.identity.id)??[]):[];
  const mode=entry?at(entry.source,'/system/prepared/value'): {present:false};
  const flexible=entry?at(entry.source,'/system/prepared/flexible'): {present:false};
  if(mode.present&&typeof mode.value!=='string'||flexible.present&&typeof flexible.value!=='boolean')throw new TypeError('Casting option mode configuration is malformed.');
  const ritual=at(spell.source,'/system/ritual');
  if(ritual.present&&ritual.value!==null&&(typeof ritual.value!=='object'||Array.isArray(ritual.value)))throw new TypeError('Casting option ritual configuration is malformed.');
  const isRitual=ritual.present&&ritual.value!==null;
  if(isRitual&&['/primary/check','/secondary/checks','/secondary/casters'].some(path=>!at(ritual.value,path).present))throw new TypeError('Casting option ritual requires its declared scalar fields.');
  const unsupported=isRitual||entry&&(flexible.value===true||!['prepared','spontaneous','innate','focus'].includes(mode.value));
  if(unsupported)reasons.add('unsupported_casting_mode');
  if(mode.value!=='prepared'||unsupported||!positions.length)positions=[null];
  for(const position of positions){
   const raw=[];
   /** PF2e-specific scalar witness selection; missing stays absent. */
   const read=(row,path,type,nullable=false)=>{
    const selected=at(row.source,path);
    if(selected.present&&!(nullable&&selected.value===null)&&(typeof selected.value!==type||type==='number'&&!Number.isFinite(selected.value)))throw new TypeError(`Casting option ${path} has an unexpected value.`);
    raw.push({document_uuid:row.identity.uuid,path,...selected,basis:'source'});return selected.present?selected.value:null;
   };
   /** PF2e-specific canonical identity with source name/type witnesses. */
   const identify=row=>{read(row,'/name','string');read(row,'/type','string');const identity=row.identity;return {status:'resolved',target_uuid:identity.uuid,type:identity.type,name:identity.name,name_truncated:identity.name_truncated,...(target.instance?.token_uuid?{token_uuid:target.instance.token_uuid}:{})};};
   const spellIdentity=identify(spell);read(spell,'/system/location/value','string',true);
   if(isRitual){read(spell,'/system/ritual/primary/check','string');read(spell,'/system/ritual/secondary/checks','string');read(spell,'/system/ritual/secondary/casters','number');}
   let entryIdentity;
   if(entry)entryIdentity=identify(entry);
   else{const existing=relationshipRecords.find(row=>row.key===`spellcasting:assignment:${spell.identity.uuid}`);entryIdentity=existing?.mapped?.value;if(!entryIdentity||!['missing','denied','unsupported'].includes(entryIdentity.status)||entryIdentity.target_uuid!==null)throw new TypeError('Casting option requires a canonical unresolved assignment record.');entryIdentity={status:entryIdentity.status,target_uuid:null};}
   const baseRank=read(spell,'/system/level/value','number'),configuredRank=read(spell,'/system/location/heightenedLevel','number');
   const spellAuto=read(spell,'/system/location/autoHeightenLevel','number',true),signature=read(spell,'/system/location/signature','boolean');
   if(signature===true)reasons.add('signature_alternatives_not_evaluated');
   const traits=at(spell.source,'/system/traits/value');let cantrip=null;
   if(traits.present){if(!Array.isArray(traits.value)||traits.value.length>200)throw new TypeError('Casting option spell traits must be an array of at most 200 entries.');cantrip=false;if(!traits.value.length)raw.push({document_uuid:spell.identity.uuid,path:'/system/traits/value',present:true,value:[],basis:'source'});for(let index=0;index<traits.value.length;index++){const trait=read(spell,`/system/traits/value/${index}`,'string');if(trait==='cantrip')cantrip=true;}}
   else raw.push({document_uuid:spell.identity.uuid,path:'/system/traits/value',present:false,basis:'source'});
   let entryAuto=null;
   if(entry){read(entry,'/system/prepared/value','string');read(entry,'/system/prepared/flexible','boolean');entryAuto=read(entry,'/system/autoHeightenLevel/value','number',true);}
   let expended=null;
   if(position){read(entry,`${position.path}/${position.index}/id`,'string',true);const selected=at(entry.source,`${position.path}/${position.index}/expended`);if(selected.present&&typeof selected.value!=='boolean')reasons.add('malformed_preparation');else expended=read(entry,`${position.path}/${position.index}/expended`,'boolean');for(const leaf of ['value','max'])read(entry,`/system/slots/slot${position.rank}/${leaf}`,'number');}
   const uses=mode.value==='innate'?{value:read(spell,'/system/location/uses/value','number'),max:read(spell,'/system/location/uses/max','number')}:null;
   const context=unsupported?'unsupported_mode':position?'prepared_use':mode.value==='spontaneous'?'spontaneous_repertoire':mode.value==='innate'?'innate_spell':mode.value==='focus'?'focus_spell':'listed_spell';
   const resourceScope={prepared_use:'individual_preparation',spontaneous_repertoire:'shared_entry_slots',innate_spell:'individual_spell_uses',focus_spell:'shared_actor_focus'}[context]??'not_evaluated';
   if(context==='focus_spell'&&target.type!=='familiar'){const actorRow={identity:target,source:actorSource};read(actorRow,'/system/resources/focus/value','number');if(target.type==='npc')read(actorRow,'/system/resources/focus/max','number');}
   const value={spell:spellIdentity,entry:entryIdentity,mode:mode.present?mode.value:null,context,base_rank:baseRank,configured_rank:configuredRank,spell_auto_heighten_rank:spellAuto,entry_auto_heighten_rank:entryAuto,cast_rank:null,slot_rank:position?.rank??null,preparation_index:position?.index??null,expended,signature,cantrip,uses,resource_scope:resourceScope,availability:'not_evaluated'};
   records.push({key:`spellcasting:option:${spell.identity.uuid}:${entry?.identity.uuid??'unassigned'}:${position?.rank??'none'}:${position?.index??'none'}`,section:'spellcasting',kind:'relationship',raw,mapped:{concept:'casting_contextual_option',value,unit:null},provenance:{contributors:raw.map(({document_uuid,path,basis})=>({document_uuid,path,basis})),mapping:'pf2e.actor.casting-options.v1',limitations:[...LIMITATIONS]}});
   if(records.length>24000)throw new TypeError('Casting options exceed 24000 selected options.');
  }
 }
 return {records,reasons:[...reasons].sort()};
}
