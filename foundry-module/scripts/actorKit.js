/**
 * PF2e-specific kit source descriptors, audited against PF2e 8.6.1.
 * KitSystemData is not PhysicalSystemSource: these are authored bundle entries,
 * not owned possessions, effective prices or prepared/imported equipment.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/kit/data.ts
 * PriceField: same revision, src/module/item/physical/schema.ts.
 */
const LIMIT=['bundle_definition_not_owned_inventory'];
const MAX_ENTRIES=12000;
/** PF2e-specific source path segment escaping; arbitrary kit entry keys retain identity. */
function escape(key){return key.replaceAll('~','~0').replaceAll('/','~1');}
/** PF2e-specific own source lookup distinguishes absent from malformed undefined. */
function at(source,keys){
 let value=source;
 for(const key of keys){if(value===null||typeof value!=='object'||!Object.hasOwn(value,key))return {present:false};value=value[key];}
 return {present:true,value};
}
/** PF2e-specific descriptor builder; no source defaults or derived values are supplied. */
function descriptor(keys,selected,concept){return {path:'/'+keys.map(escape).join('/'),...selected,concept,limitations:[...LIMIT]};}
/** PF2e-specific typed scalar selector for kit source leaves. */
function scalar(source,keys,concept,type,{nullable=false,integer=false,min=-Infinity,optionalUndefined=false}={}){
 let selected=at(source,keys);
 if(optionalUndefined&&selected.present&&selected.value===undefined)selected={present:false};
 if(selected.present&&!(nullable&&selected.value===null)&&(typeof selected.value!==type||(type==='number'&&(!Number.isFinite(selected.value)||(integer&&!Number.isInteger(selected.value))||selected.value<min))))throw new TypeError(`Kit source /${keys.map(escape).join('/')} has an unexpected type.`);
 return descriptor(keys,selected,concept);
}
/** PF2e-specific kit trait code sequence; order, empty and absent remain distinct. */
function strings(source,keys,concept){
 const selected=at(source,keys);
 if(!selected.present)return [descriptor(keys,selected,concept)];
 if(!Array.isArray(selected.value))throw new TypeError('Kit trait source must be an array.');
 if(!selected.value.length)return [descriptor(keys,selected,concept)];
 return selected.value.map((value,index)=>{if(typeof value!=='string')throw new TypeError('Kit trait source must contain strings.');return descriptor([...keys,String(index)],{present:true,value},concept);});
}
/**
 * PF2e-specific KitSystemData 8.6.1 selector for detached Item.toObject(true).
 * The schema's depth <=2 recursive constructor permits entries at levels0..3;
 * level3 children use NullField. At most12000 entries are accepted. Maps flatten
 * to source-path scalars and absent/null/empty markers, never whole object dumps.
 * UUIDs remain authored claims: no document resolution, import, ownership,
 * container effectiveness, stack multiplication or rule execution occurs.
 */
export function kitFields(source){
 if(source?.type!=='kit')return null;
 const fields=[];let count=0;
 /** PF2e-specific bounded kit-entry map traversal preserving original keyed provenance. */
 function entries(keys,level){
  const selected=at(source,keys),concept=level===0?'kit_items':'kit_component_items';
  if(!selected.present||selected.value===null){
   if(selected.present&&level===0)throw new TypeError('Kit root items cannot be null.');
   fields.push(descriptor(keys,selected,concept));return;
  }
  if(level>3)throw new TypeError('Kit nested items exceed the PF2e 8.6.1 schema depth.');
  if(typeof selected.value!=='object'||Array.isArray(selected.value))throw new TypeError('Kit items must be keyed entry maps.');
  const pairs=Object.entries(selected.value);
  if(!pairs.length){fields.push(descriptor(keys,{present:true,value:{}},concept));return;}
  for(const [key,entry]of pairs){
   if(!key||++count>MAX_ENTRIES||entry===null||typeof entry!=='object'||Array.isArray(entry))throw new TypeError('Kit entry is malformed or exceeds the12000-entry limit.');
   const path=[...keys,key];
   for(const [leaf,name,type,options]of [['uuid','uuid','string',{}],['img','image','string',{}],['quantity','quantity','number',{integer:true,min:1}],['name','name','string',{}],['isContainer','is_container','boolean',{}]])fields.push(scalar(source,[...path,leaf],'kit_component_'+name,type,options));
   entries([...path,'items'],level+1);
  }
 }
 entries(['system','items'],0);
 for(const denomination of ['pp','gp','sp','cp'])fields.push(scalar(source,['system','price','value',denomination],'kit_price_'+denomination,'number',{integer:true,min:0}));
 fields.push(scalar(source,['system','price','per'],'kit_price_per','number',{integer:true,min:1}),scalar(source,['system','price','sizeSensitive'],'kit_price_size_sensitive','boolean',{optionalUndefined:true}));
 fields.push(...strings(source,['system','traits','value'],'kit_trait_code'),...strings(source,['system','traits','otherTags'],'kit_other_tag_code'),scalar(source,['system','slug'],'kit_source_slug','string',{nullable:true}));
 for(const [key,type]of [['title','string'],['authors','string'],['license','string'],['remaster','boolean']])fields.push(scalar(source,['system','publication',key],'kit_publication_'+key,type));
 return fields;
}
