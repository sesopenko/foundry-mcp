/**
 * PF2e-specific character/NPC transformed senses, languages and IWR selector,
 * Foundry14.369/PF2e8.6.1. Public Actor.toObject(false) boundary:
 * https://foundryvtt.com/api/v14/classes/foundry.documents.Actor.html#toobject
 * Pinned document contracts at upstream revision:
 * https://github.com/foundryvtt/pf2e/tree/28d9d156f252d084371d994dc359509b49eadf18/src/module
 * actor/creature/data.ts, actor/data/base.ts, actor/data/iwr.ts and
 * system/statistic/perception.ts. ActorAttributes declares IWR class instances;
 * IWR declares definition:Predicate|null, but its display serializer may omit it.
 * Only own returned fields are selected. No IWR methods, getters, source fallback,
 * targeting, predicate execution or damage application is adopted.
 * Predicate grammar: system/predication.ts, same pinned revision.
 */
const LIMIT=['serialized_creature_details_not_target_context'];
const INFINITY_TAG=Object.freeze({'$number':'Infinity'});

/** PF2e-specific own serialized-data lookup, including nonplain containers. */
function selected(source,keys){
 let value=source;
 for(const key of keys){
  if(value===null||typeof value!=='object'||Array.isArray(value)&&!/^(?:0|[1-9]\d*)$/.test(key))throw new TypeError('Current creature detail has a malformed container.');
  const descriptor=Object.getOwnPropertyDescriptor(value,key);if(!descriptor)return {present:false};
  if(!Object.hasOwn(descriptor,'value'))throw new TypeError('Current creature details require detached own data properties.');
  value=descriptor.value;if(value===undefined)return {present:false};
 }
 return {present:true,value};
}
/** PF2e-specific bounded text is never silently truncated. */
function text(value){if(typeof value!=='string'||value.length>6000)throw new TypeError('Current creature text must be a string of at most 6000 UTF-16 units.');return value;}

/**
 * PF2e-specific closed RawPredicate grammar, copied as clean JSON without
 * executing predicates or traversing unrelated/prototype properties. Depth is
 * measured from root array at zero; every array/object/primitive counts as one
 * node. Limits: depth8, 512 nodes, 6000 UTF-16 units per string. Predicate array
 * subclasses may carry unrelated own metadata, which is not selected.
 */
function predicate(value){
 let nodes=0;
 const enter=depth=>{if(depth>8||++nodes>512)throw new TypeError('Current IWR predicate exceeds depth8 or 512 nodes.');};
 const get=(node,key)=>{const result=selected(node,[key]);if(!result.present)throw new TypeError('Current IWR predicate has a missing statement.');return result.value;};
 const array=(node,depth,element)=>{enter(depth);if(!Array.isArray(node))throw new TypeError('Current IWR predicate requires an array.');if(node.length>512)throw new TypeError('Current IWR predicate exceeds 512 nodes.');const result=[];for(let index=0;index<node.length;index++)result.push(element(get(node,String(index)),depth+1));return result;};
 const operand=(node,depth)=>{enter(depth);if(typeof node==='string')return text(node);if(typeof node==='number'&&Number.isFinite(node))return node;throw new TypeError('Current IWR predicate operand must be string or finite number.');};
 const statement=(node,depth)=>{
  if(typeof node==='string'){enter(depth);if(!text(node).length)throw new TypeError('Current IWR predicate atoms must be nonempty.');return node;}
  enter(depth);if(node===null||typeof node!=='object'||Array.isArray(node))throw new TypeError('Current IWR predicate statement is malformed.');
  const keys=Object.getOwnPropertyNames(node);if(Object.getOwnPropertySymbols(node).length)throw new TypeError('Current IWR predicate has unknown fields.');
  if(keys.length===2&&keys.includes('if')&&keys.includes('then'))return {if:statement(get(node,'if'),depth+1),then:statement(get(node,'then'),depth+1)};
  if(keys.length!==1)throw new TypeError('Current IWR predicate has unknown fields.');
  const key=keys[0],child=get(node,key);
  if(['eq','gt','gte','lt','lte'].includes(key)){
   if(!Array.isArray(child)||child.length!==2)throw new TypeError('Current IWR predicate comparison requires two operands.');
   const values=array(child,depth+1,operand);if(typeof values[0]!=='string')throw new TypeError('Current IWR predicate left operand must be a string.');return {[key]:values};
  }
  if(['and','or','nand','nor','xor','iff'].includes(key))return {[key]:array(child,depth+1,statement)};
  if(key==='not')return {not:statement(child,depth+1)};
  throw new TypeError('Current IWR predicate operator is unsupported.');
 };
 return array(value,0,statement);
}

/**
 * PF2e-specific detached transformed character/NPC supplement. Returns null for
 * other subtypes; otherwise {fields,reasons}. At most 200 senses, languages or
 * entries per IWR collection, and 200 exceptions/doubleVs per entry, with 24000
 * total fields. Empty arrays and missing arrays retain explicit root markers.
 * Sense range positive Infinity alone is encoded as {$number:"Infinity"}; null
 * and other nonfinite numbers reject for the transformed numeric range contract.
 * Custom predicates remain bounded data, never evaluated applicability.
 * Custom main definitions select only declared own definition data; absence is
 * diagnosed explicitly, never reconstructed from getters or source.
 */
export function creatureSupplementFields(serialized){
 if(!['character','npc'].includes(selected(serialized,['type']).value))return null;
 const fields=[],reasons=new Set(['other_statistics_pending']);
 const emit=(keys,result,concept,mapped)=>{if(!result.present)reasons.add('current_fields_unavailable');fields.push({path:'/'+keys.join('/'),...result,concept,limitations:[...LIMIT],...(mapped?{mapped_value:null}:{})});if(fields.length>24000)throw new TypeError('Current creature details exceed 24000 fields.');};
 /** PF2e-specific typed primitive, preserving unknown source codes. */
 const scalar=(keys,concept,kind,nullable=false)=>{
  const result=selected(serialized,keys);
  if(result.present&&!(nullable&&result.value===null)){
   if(kind==='string')text(result.value);
   else if(kind==='range'&&result.value===Infinity)result.value={...INFINITY_TAG};
   else if(typeof result.value!=='number'||!Number.isFinite(result.value))throw new TypeError('Current creature numeric detail must be finite.');
  }
  emit(keys,result,concept);return result;
 };
 /** PF2e-specific selected collection; own array entries cannot invoke getters. */
 const collection=(keys,concept,visit)=>{
  const result=selected(serialized,keys);if(!result.present){emit(keys,result,concept);return;}
  if(!Array.isArray(result.value)||result.value.length>200)throw new TypeError('Current creature collections require arrays of at most 200 entries.');
  if(!result.value.length)emit(keys,{present:true,value:[]},concept,true);
  for(let index=0;index<result.value.length;index++){const entry=selected(result.value,[String(index)]);if(!entry.present)throw new TypeError('Current creature collection entry is missing.');visit([...keys,String(index)],entry.value);}
 };
 collection(['system','perception','senses'],'current_senses',(keys,value)=>{
  if(value===null||typeof value!=='object'||Array.isArray(value))throw new TypeError('Current sense must be an own-data object.');
  scalar([...keys,'type'],'current_sense_type','string');const acuity=scalar([...keys,'acuity'],'current_sense_acuity','string');if(acuity.present&&!['precise','imprecise','vague'].includes(acuity.value))throw new TypeError('Current sense acuity is unsupported.');
  scalar([...keys,'range'],'current_sense_range','range');scalar([...keys,'source'],'current_sense_source','string',true);scalar([...keys,'label'],'current_sense_label','string',true);
 });
 collection(['system','details','languages','value'],'current_languages',keys=>scalar(keys,'current_language_code','string'));
 scalar(['system','details','languages','details'],'current_language_details','string');
 for(const [group,singular]of [['immunities','immunity'],['weaknesses','weakness'],['resistances','resistance']]){
  collection(['system','attributes',group],`current_${group}`,(keys,value)=>{
   if(value===null||typeof value!=='object'||Array.isArray(value))throw new TypeError('Current IWR entry must be an own-data object.');
   reasons.add('conditional_iwr_not_evaluated');
   const type=scalar([...keys,'type'],`current_${singular}_type`,'string');scalar([...keys,'source'],`current_${singular}_source`,'string',true);scalar([...keys,'label'],`current_${singular}_label`,'string');
   if(group!=='immunities')scalar([...keys,'value'],`current_${singular}_value`,'number');
   if(type.value==='custom'){
    const definition=selected(serialized,[...keys,'definition']);if(!definition.present)reasons.add('custom_iwr_definition_unavailable');else if(definition.value!==null)definition.value=predicate(definition.value);
    emit([...keys,'definition'],definition,`current_${singular}_definition`);
   }
   for(const list of group==='resistances'?['exceptions','doubleVs']:['exceptions']){
    const suffix=list==='doubleVs'?'double_vs':'exception';
    collection([...keys,list],`current_${singular}_${list==='exceptions'?'exceptions':'double_vs'}`,(path,exception)=>{
     if(typeof exception==='string'){scalar(path,`current_${singular}_${suffix}_type`,'string');return;}
     if(exception===null||typeof exception!=='object'||Array.isArray(exception))throw new TypeError('Current IWR exception must be a string or custom definition.');
     const ownKeys=Object.getOwnPropertyNames(exception);if(ownKeys.some(key=>!['label','definition'].includes(key))||Object.getOwnPropertySymbols(exception).length)throw new TypeError('Current custom IWR exception has unknown fields.');
     scalar([...path,'label'],`current_${singular}_${suffix}_label`,'string');
     const definition=selected(serialized,[...path,'definition']);if(definition.present)definition.value=predicate(definition.value);emit([...path,'definition'],definition,`current_${singular}_${suffix}_definition`);
    });
   }
  });
 }
 return {fields,reasons:[...reasons].sort()};
}
