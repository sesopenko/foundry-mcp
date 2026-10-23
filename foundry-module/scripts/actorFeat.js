/**
 * PF2e-specific feat Item source selector, pinned PF2e 8.6.1/core14.
 * Detached Item.toObject(true) source only; no effective benefits or defaults.
 * Schema: https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/feat/data.ts
 * Frequency/trait toggle definitions: same revision item/ability/data.ts and
 * item/ability/trait-toggles.ts; shared metadata: item/base/data/model.ts.
 */
const LIMIT=['feat_source_not_effective_benefit'];
const MAX_ENTRIES=12000;
/** PF2e-specific pinned 8.6.1 source keys use JSON Pointer escaping, no derivation. */
function escape(key){return key.replaceAll('~','~0').replaceAll('/','~1');}
/** PF2e-specific pinned 8.6.1 own-source presence, never inherited/prepared defaults. */
function at(source,keys,optional=false){let value=source;for(const key of keys){if(value===null||typeof value!=='object'||!Object.hasOwn(value,key))return {present:false};value=value[key];}return optional&&value===undefined?{present:false}:{present:true,value};}
/** PF2e-specific pinned 8.6.1 source descriptor with exact presence and value. */
function descriptor(keys,selected,concept){return {path:'/'+keys.map(escape).join('/'),...selected,concept:'feat_'+concept,limitations:[...LIMIT]};}
/** PF2e-specific pinned 8.6.1 source scalar validation, no coercion/defaults. */
function scalar(source,keys,concept,type,{nullable=false,optional=false,min=null,max=null,integer=false}={}){const selected=at(source,keys,optional);if(selected.present&&!(nullable&&selected.value===null)){const value=selected.value;if(typeof value!==type||(type==='number'&&(!Number.isFinite(value)||(integer&&!Number.isInteger(value))||(min!==null&&value<min)||(max!==null&&value>max))))throw new TypeError(`Feat source /${keys.map(escape).join('/')} has an unexpected type or range.`);}return descriptor(keys,selected,concept);}
/** PF2e-specific pinned 8.6.1 source containers; optional never reconstructs defaults. */
function object(source,keys,concept,children,{nullable=false,optional=false}={}){const selected=at(source,keys,optional);if(!selected.present||(nullable&&selected.value===null))return [descriptor(keys,selected,concept)];if(!selected.value||typeof selected.value!=='object'||Array.isArray(selected.value))throw new TypeError('Feat source container must be an object.');return children();}
/** PF2e-specific pinned 8.6.1 source ordered string lists retain empty markers. */
function list(source,keys,concept,optional=false,prerequisites=false){const selected=at(source,keys,optional);if(!selected.present)return [descriptor(keys,selected,concept)];if(!Array.isArray(selected.value)||selected.value.length>MAX_ENTRIES)throw new TypeError('Feat source list must have at most 12000 entries.');if(!selected.value.length)return [descriptor(keys,selected,concept)];return selected.value.map((value,i)=>{const path=[...keys,String(i)];if(prerequisites){if(!value||typeof value!=='object'||Array.isArray(value))throw new TypeError('Feat prerequisite must be an object.');return scalar(source,[...path,'value'],'prerequisite_text','string');}return scalar(source,path,concept,'string');});}
/** PF2e-specific pinned 8.6.1 source opaque maps retain exact keys, never grant benefits. */
function record(source,keys,concept,children){return object(source,keys,concept,()=>{const value=at(source,keys).value,names=Object.keys(value);if(names.length>MAX_ENTRIES)throw new TypeError('Feat source map exceeds 12000 entries.');if(!names.length)return [descriptor(keys,{present:true,value:{}},concept)];return names.flatMap(key=>object(source,[...keys,key],concept,()=>children([...keys,key])));});}
/**
 * PF2e-specific feat source fields from pinned 8.6.1 schema above: category,
 * level.value/taken, activation, prerequisites, location, limits, frequency,
 * traits/toggles, subfeatures, selfEffect and shared metadata. Source grants,
 * suppression UUIDs and toggle selection never establish effective benefits,
 * eligibility, applied effects, acquired documents or usable resources.
 * Missing defaults stay missing; only explicit schema-optional undefined fields
 * normalize absent. Returns null for other Item types; caller gates system ID.
 */
export function featFields(source){
 if(source?.type!=='feat')return null;
 /** PF2e-specific pinned 8.6.1 detached system scalar; no derived state. */
 const s=(path,concept,type,options)=>scalar(source,['system',...path.split('/')],concept,type,options);
 const fields=[s('category','category_code','string'),s('level/value','nominal_level','number',{integer:true,min:1,max:30}),s('level/taken','taken_level','number',{nullable:true,optional:true,integer:true,min:1,max:30}),s('onlyLevel1','only_level_one','boolean'),s('maxTakable','maximum_takable','number',{nullable:true,integer:true,min:1}),s('actionType/value','activation_kind','string'),s('actions/value','action_count','number',{nullable:true,integer:true,min:1,max:3}),s('location','location','string',{nullable:true})];
 const category=fields[0];if(category.present){const features=['ancestryfeature','calling','classfeature','curse','deityboon','pfsboon'],feats=['ancestry','bonus','class','general','skill'];category.mapped_value={code:category.value,kind:features.includes(category.value)?'feature':feats.includes(category.value)?'feat':'unknown'};}
 fields.push(...list(source,['system','prerequisites','value'],'prerequisite_entries',false,true));
 fields.push(...object(source,['system','frequency'],'frequency_source',()=>[s('frequency/value','recorded_frequency_remaining','number',{optional:true,integer:true,min:0}),s('frequency/max','frequency_maximum','number',{integer:true,min:1}),s('frequency/per','frequency_interval_code','string')],{nullable:true,optional:true}));
 for(const [path,concept]of [['traits/value','trait_code'],['traits/otherTags','other_tag_code'],['subfeatures/keyOptions','key_option_code'],['subfeatures/suppressedFeatures','suppressed_feature_uuid']])fields.push(...list(source,['system',...path.split('/')],concept,path==='subfeatures/keyOptions'));
 fields.push(s('traits/rarity','rarity_code','string'));
 fields.push(...object(source,['system','traits','toggles'],'trait_toggles',()=>object(source,['system','traits','toggles','mindshift'],'mindshift_toggle',()=>[s('traits/toggles/mindshift/selected','mindshift_selected','boolean')],{nullable:true,optional:true}),{optional:true}));
 fields.push(...object(source,['system','subfeatures','languages'],'language_options',()=>[s('subfeatures/languages/slots','language_slots','number',{integer:true,min:0}),...list(source,['system','subfeatures','languages','granted'],'granted_language_code')],{optional:true}));
 fields.push(...record(source,['system','subfeatures','proficiencies'],'proficiency_entries',keys=>[scalar(source,[...keys,'rank'],'proficiency_rank','number',{integer:true,min:1,max:4}),scalar(source,[...keys,'attribute'],'proficiency_attribute_code','string',{nullable:true})]));
 fields.push(...record(source,['system','subfeatures','senses'],'sense_entries',keys=>[scalar(source,[...keys,'acuity'],'sense_acuity_code','string',{optional:true}),scalar(source,[...keys,'range'],'sense_range','number',{nullable:true,min:5,max:300}),...object(source,[...keys,'special'],'sense_special',()=>['ancestry','llv','second'].map(key=>scalar(source,[...keys,'special',key],'sense_special_'+key,'boolean')),{optional:true})]));
 fields.push(...object(source,['system','selfEffect'],'self_effect_source',()=>[s('selfEffect/uuid','self_effect_uuid','string'),s('selfEffect/name','self_effect_name','string')],{nullable:true,optional:true}));
 fields.push(s('slug','source_slug','string',{nullable:true}));for(const [key,type]of [['title','string'],['authors','string'],['license','string'],['remaster','boolean']])fields.push(s('publication/'+key,'publication_'+key,type));
 return fields;
}
