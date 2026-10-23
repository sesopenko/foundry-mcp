/**
 * PF2e-specific heritage Item source selector, audited against PF2e 8.6.1.
 * Detached Item.toObject(true) only; ancestry associations never establish an
 * owner ancestry, exclusivity, granted features or effective character state.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/heritage/data.ts
 */
const LIMIT=['heritage_source_not_effective_character'];
const MAX_ENTRIES=12000;
/** PF2e-specific heritage 8.6.1 source JSON pointer escaping for arbitrary persisted record keys. */
function escape(key){return key.replaceAll('~','~0').replaceAll('/','~1');}
/** PF2e-specific heritage 8.6.1 detached own-path lookup; no inherited/default values. */
function at(source,keys){let value=source;for(const key of keys){if(value===null||typeof value!=='object'||!Object.hasOwn(value,key))return {present:false};value=value[key];}return {present:true,value};}
/** PF2e-specific heritage 8.6.1 source leaf descriptor retaining exact source presence/value. */
function descriptor(keys,selected,concept){return {path:'/'+keys.map(escape).join('/'),...selected,concept:'heritage_'+concept,limitations:[...LIMIT]};}
/** PF2e-specific heritage 8.6.1 source scalar validation; no defaults or numeric coercion. */
function scalar(source,keys,concept,type,nullable=false){const s=at(source,keys);if(s.present&&!(nullable&&s.value===null)&&(typeof s.value!==type||(type==='number'&&!Number.isFinite(s.value))))throw new TypeError(`Heritage source /${keys.map(escape).join('/')} has an unexpected type.`);return descriptor(keys,s,concept);}
/** PF2e-specific heritage 8.6.1 ordered traits.value/otherTags source lists; no derived traits. */
function strings(source,keys,concept){const s=at(source,keys);if(!s.present)return [descriptor(keys,s,concept)];if(!Array.isArray(s.value)||s.value.length>MAX_ENTRIES)throw new TypeError('Heritage source code list is invalid or exceeds 12000 entries.');if(!s.value.length)return [descriptor(keys,s,concept)];return s.value.map((value,i)=>{if(typeof value!=='string')throw new TypeError('Heritage source code must be a string.');return descriptor([...keys,String(i)],{present:true,value},concept);});}
/**
 * PF2e-specific heritage Item source, PF2e 8.6.1 heritage/data.ts and
 * base/data/model.ts at the pinned module-level schema URL. Selects nullable
 * ancestry association, trait codes and shared metadata from detached source.
 * No schema defaults, ancestry exclusivity, owner-ancestry inference, UUID
 * resolution, feature acquisition, rule evaluation or effective Actor totals.
 */
export function heritageFields(source){
 if(source?.type!=='heritage')return null;
 /** PF2e-specific heritage 8.6.1 scalar rooted in the selected Item source. */
 const s=(path,concept,type,nullable=false)=>scalar(source,['system',...path.split('/')],concept,type,nullable);
 const fields=[];
 const association=at(source,['system','ancestry']);
 if(!association.present||association.value===null)fields.push(descriptor(['system','ancestry'],association,'ancestry_association'));
 else {
  if(typeof association.value!=='object'||Array.isArray(association.value))throw new TypeError('Heritage ancestry association must be a source object or null.');
  for(const key of ['name','slug','uuid'])fields.push(s('ancestry/'+key,'ancestry_'+key,'string'));
 }
 fields.push(...strings(source,['system','traits','value'],'trait_code'),...strings(source,['system','traits','otherTags'],'other_tag_code'),s('traits/rarity','rarity_code','string'),s('slug','source_slug','string',true));
 for(const [key,type]of [['title','string'],['authors','string'],['license','string'],['remaster','boolean']])fields.push(s('publication/'+key,'publication_'+key,type));
 return fields;
}
