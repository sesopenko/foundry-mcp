/**
 * PF2e-specific ancestry Item source selector, audited against PF2e 8.6.1.
 * Detached Item.toObject(true) only; choices and contributions never become
 * effective character statistics or proof of acquiring a referenced feature.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/ancestry/data.ts
 * Feature entry schema: same revision src/module/item/abc/data.ts.
 */
const LIMIT=['ancestry_source_not_effective_character'];
const MAX_ENTRIES=12000;
/** PF2e-specific ancestry JSON pointer escaping for arbitrary persisted record keys. */
function escape(key){return key.replaceAll('~','~0').replaceAll('/','~1');}
/** PF2e-specific ancestry detached own-path lookup; no inherited/default values. */
function at(source,keys){let value=source;for(const key of keys){if(value===null||typeof value!=='object'||!Object.hasOwn(value,key))return {present:false};value=value[key];}return {present:true,value};}
/** PF2e-specific ancestry leaf descriptor retaining exact source presence/value. */
function descriptor(keys,selected,concept){return {path:'/'+keys.map(escape).join('/'),...selected,concept:'ancestry_'+concept,limitations:[...LIMIT]};}
/** PF2e-specific ancestry scalar validation; no defaults or numeric coercion. */
function scalar(source,keys,concept,type,nullable=false){const s=at(source,keys);if(s.present&&!(nullable&&s.value===null)&&(typeof s.value!==type||(type==='number'&&!Number.isFinite(s.value))))throw new TypeError(`Ancestry source /${keys.map(escape).join('/')} has an unexpected type.`);return descriptor(keys,s,concept);}
/** PF2e-specific ancestry ordered code list; nullable alternate choice retained separately. */
function strings(source,keys,concept,nullable=false){const s=at(source,keys);if(!s.present||(nullable&&s.value===null))return [descriptor(keys,s,concept)];if(!Array.isArray(s.value)||s.value.length>MAX_ENTRIES)throw new TypeError('Ancestry source code list is invalid or exceeds 12000 entries.');if(!s.value.length)return [descriptor(keys,s,concept)];return s.value.map((value,i)=>{if(typeof value!=='string')throw new TypeError('Ancestry source code must be a string.');return descriptor([...keys,String(i)],{present:true,value},concept);});}
/** PF2e-specific ancestry keyed source map, bounded without dropping or sorting keys. */
function entries(source,keys,concept){const s=at(source,keys);if(!s.present)return {markers:[descriptor(keys,s,concept)],keys:[]};if(!s.value||typeof s.value!=='object'||Array.isArray(s.value)||Object.keys(s.value).length>MAX_ENTRIES)throw new TypeError('Ancestry source record is invalid or exceeds 12000 entries.');const names=Object.keys(s.value);return {markers:names.length?[]:[descriptor(keys,s,concept)],keys:names};}
/**
 * PF2e-specific ancestry source: offered attribute lists, nullable selections,
 * alternate/voluntary configuration, ancestry HP and movement contributions,
 * language choices and named future feature references. Source hands/reach are
 * schema-defined contributions, never effective creature hands or reach. No rule
 * evaluation, source defaults, UUID resolution, feature acquisition or totals.
 */
export function ancestryFields(source){
 if(source?.type!=='ancestry')return null;
 /** PF2e-specific ancestry scalar rooted in the selected Item source. */
 const s=(path,concept,type,nullable=false)=>scalar(source,['system',...path.split('/')],concept,type,nullable);
 const fields=[];
 for(const [name,label]of [['boosts','boost'],['flaws','flaw']]){
  const map=entries(source,['system',name],label+'_slots');fields.push(...map.markers);
  for(const key of map.keys){const keys=['system',name,key];const slot=at(source,keys).value;if(!slot||typeof slot!=='object'||Array.isArray(slot))throw new TypeError('Ancestry attribute slot must be a source object.');fields.push(...strings(source,[...keys,'value'],label+'_offer_code'),scalar(source,[...keys,'selected'],label+'_selected_code','string',true));}
 }
 fields.push(...strings(source,['system','alternateAncestryBoosts'],'alternate_boost_code',true),s('voluntary/legacy','voluntary_legacy','boolean'),s('voluntary/boost','voluntary_boost_code','string',true),...strings(source,['system','voluntary','flaws'],'voluntary_flaw_code'));
 for(const [path,concept,type]of [['hp','hp_contribution','number'],['size','size_code','string'],['speed','base_speed','number'],['hands','hands','number'],['reach','reach','number'],['vision','vision_code','string'],['languages/custom','language_custom','string'],['additionalLanguages/count','additional_language_count','number'],['additionalLanguages/custom','additional_language_custom','string']])fields.push(s(path,concept,type));
 fields.push(...strings(source,['system','languages','value'],'language_code'),...strings(source,['system','additionalLanguages','value'],'additional_language_code'));
 const features=entries(source,['system','items'],'feature_entries');fields.push(...features.markers);
 for(const key of features.keys){const keys=['system','items',key];const feature=at(source,keys).value;if(!feature||typeof feature!=='object'||Array.isArray(feature))throw new TypeError('Ancestry feature entry must be a source object.');for(const [name,type]of [['uuid','string'],['img','string'],['name','string'],['level','number']]){if(name==='level'){const level=at(source,[...keys,name]);if(level.present&&(!Number.isInteger(level.value)||level.value<0))throw new TypeError('Ancestry feature level must be a nonnegative integer.');}fields.push(scalar(source,[...keys,name],'feature_'+(name==='img'?'image':name),type));}}
 fields.push(...strings(source,['system','traits','value'],'trait_code'),...strings(source,['system','traits','otherTags'],'other_tag_code'),s('traits/rarity','rarity_code','string'),s('slug','source_slug','string',true));
 for(const [key,type]of [['title','string'],['authors','string'],['license','string'],['remaster','boolean']])fields.push(s('publication/'+key,'publication_'+key,type));
 return fields;
}
