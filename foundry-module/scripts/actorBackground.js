/**
 * PF2e-specific background Item source selector, audited against PF2e 8.6.1.
 * Detached Item.toObject(true) only; choices and contributions never become
 * effective character statistics or proof of acquiring a referenced feature.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/background/data.ts
 * Feature entry schema: same revision src/module/item/abc/data.ts.
 */
const LIMIT=['background_source_not_effective_character'];
const MAX_ENTRIES=12000;
/** PF2e-specific background JSON pointer escaping for arbitrary persisted record keys. */
function escape(key){return key.replaceAll('~','~0').replaceAll('/','~1');}
/** PF2e-specific background detached own-path lookup; no inherited/default values. */
function at(source,keys){let value=source;for(const key of keys){if(value===null||typeof value!=='object'||!Object.hasOwn(value,key))return {present:false};value=value[key];}return {present:true,value};}
/** PF2e-specific background leaf descriptor retaining exact source presence/value. */
function descriptor(keys,selected,concept){return {path:'/'+keys.map(escape).join('/'),...selected,concept:'background_'+concept,limitations:[...LIMIT]};}
/** PF2e-specific background scalar validation; no defaults or numeric coercion. */
function scalar(source,keys,concept,type,nullable=false){const s=at(source,keys);if(s.present&&!(nullable&&s.value===null)&&(typeof s.value!==type||(type==='number'&&!Number.isFinite(s.value))))throw new TypeError(`Background source /${keys.map(escape).join('/')} has an unexpected type.`);return descriptor(keys,s,concept);}
/** PF2e-specific background ordered boosts/trainedSkills/traits list; no inferred training or choices. */
function strings(source,keys,concept){const s=at(source,keys);if(!s.present)return [descriptor(keys,s,concept)];if(!Array.isArray(s.value)||s.value.length>MAX_ENTRIES)throw new TypeError('Background source code list is invalid or exceeds 12000 entries.');if(!s.value.length)return [descriptor(keys,s,concept)];return s.value.map((value,i)=>{if(typeof value!=='string')throw new TypeError('Background source code must be a string.');return descriptor([...keys,String(i)],{present:true,value},concept);});}
/** PF2e-specific background keyed source map, bounded without dropping or sorting keys. */
function entries(source,keys,concept){const s=at(source,keys);if(!s.present)return {markers:[descriptor(keys,s,concept)],keys:[]};if(!s.value||typeof s.value!=='object'||Array.isArray(s.value)||Object.keys(s.value).length>MAX_ENTRIES)throw new TypeError('Background source record is invalid or exceeds 12000 entries.');const names=Object.keys(s.value);return {markers:names.length?[]:[descriptor(keys,s,concept)],keys:names};}
/**
 * PF2e-specific background Item source, PF2e 8.6.1 background/data.ts,
 * abc/data.ts and static/template.json at the pinned module-level schema URL.
 * Selects boosts.value offers versus nullable selected choices, trainedSkills
 * value/lore lists, ABC items and shared metadata from detached source only.
 * No default reconstruction, training rank, Lore creation, duplicate-training
 * handling, skill feat acquisition, UUID resolution or effective Actor totals.
 */
export function backgroundFields(source){
 if(source?.type!=='background')return null;
 /** PF2e-specific background scalar rooted in the selected Item source. */
 const s=(path,concept,type,nullable=false)=>scalar(source,['system',...path.split('/')],concept,type,nullable);
 const fields=[];
 const map=entries(source,['system','boosts'],'boost_slots');fields.push(...map.markers);
 for(const key of map.keys){const keys=['system','boosts',key];const slot=at(source,keys).value;if(!slot||typeof slot!=='object'||Array.isArray(slot))throw new TypeError('Background attribute slot must be a source object.');fields.push(...strings(source,[...keys,'value'],'boost_offer_code'),scalar(source,[...keys,'selected'],'boost_selected_code','string',true));}
 fields.push(...strings(source,['system','trainedSkills','value'],'trained_skill_code'),...strings(source,['system','trainedSkills','lore'],'lore'));
 const features=entries(source,['system','items'],'feature_entries');fields.push(...features.markers);
 for(const key of features.keys){const keys=['system','items',key];const feature=at(source,keys).value;if(!feature||typeof feature!=='object'||Array.isArray(feature))throw new TypeError('Background feature entry must be a source object.');for(const [name,type]of [['uuid','string'],['img','string'],['name','string'],['level','number']]){if(name==='level'){const level=at(source,[...keys,name]);if(level.present&&(!Number.isInteger(level.value)||level.value<0))throw new TypeError('Background feature level must be a nonnegative integer.');}fields.push(scalar(source,[...keys,name],'feature_'+(name==='img'?'image':name),type));}}
 fields.push(...strings(source,['system','traits','value'],'trait_code'),...strings(source,['system','traits','otherTags'],'other_tag_code'),s('traits/rarity','rarity_code','string'),s('slug','source_slug','string',true));
 for(const [key,type]of [['title','string'],['authors','string'],['license','string'],['remaster','boolean']])fields.push(s('publication/'+key,'publication_'+key,type));
 return fields;
}
