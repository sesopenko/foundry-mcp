/**
 * PF2e-specific deity Item source selector, audited against PF2e 8.6.1.
 * Detached Item.toObject(true) source only; offered devotee options never
 * establish worship, acquired spells/weapons, or active character benefits.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/deity/data.ts
 * Shared metadata and defaults: same revision item/base/data/system.ts and static/template.json.
 */
const LIMIT=['deity_options_not_active_benefits'];
const MAX_ENTRIES=12000;
/** PF2e-specific deity JSON Pointer escaping for opaque persisted spell keys. */
function escape(key){return key.replaceAll('~','~0').replaceAll('/','~1');}
/** PF2e-specific deity detached own-path lookup; no inherited/default values. */
function at(source,keys){let value=source;for(const key of keys){if(value===null||typeof value!=='object'||!Object.hasOwn(value,key))return {present:false};value=value[key];}return {present:true,value};}
/** PF2e-specific deity descriptor preserving source presence and exact value. */
function descriptor(keys,selected,concept){return {path:'/'+keys.map(escape).join('/'),...selected,concept:'deity_'+concept,limitations:[...LIMIT]};}
/** PF2e-specific deity scalar validation; source code strings are never normalized. */
function scalar(source,keys,concept,type,nullable=false){const s=at(source,keys);if(s.present&&!(nullable&&s.value===null)&&typeof s.value!==type)throw new TypeError(`Deity source /${keys.map(escape).join('/')} has an unexpected type.`);return descriptor(keys,s,concept);}
/** PF2e-specific deity ordered option/code arrays, optionally nullable skill source; no inferred choices. */
function strings(source,keys,concept,nullable=false){const s=at(source,keys);if(!s.present||(nullable&&s.value===null))return [descriptor(keys,s,concept)];if(!Array.isArray(s.value)||s.value.length>MAX_ENTRIES)throw new TypeError('Deity source code list is invalid or exceeds 12000 entries.');if(!s.value.length)return [descriptor(keys,s,concept)];return s.value.map((value,i)=>{if(typeof value!=='string')throw new TypeError('Deity source code must be a string.');return descriptor([...keys,String(i)],{present:true,value},concept);});}
/**
 * PF2e-specific deity source options from PF2e 8.6.1 deity/data.ts and
 * shared metadata/static template at the pinned module-level schema URL.
 * Handles deity/pantheon/covenant/philosophy category strings without enum
 * coercion; sanctification modal/what, domains, font, attribute, nullable skill,
 * weapons, opaque spell-key UUID map, otherTags, slug and publication only.
 * No effective benefits, spell acquisition/cast rank, UUID hydration, creature
 * conversion, rules execution or reconstruction of missing template defaults.
 */
export function deityFields(source){
 if(source?.type!=='deity')return null;
 /** PF2e-specific deity scalar rooted in detached Item system source. */
 const s=(path,concept,type,nullable=false)=>scalar(source,['system',...path.split('/')],concept,type,nullable);
 const fields=[s('category','category_code','string')];
 const keys=['system','sanctification'],sanctification=at(source,keys);
 if(!sanctification.present||sanctification.value===null)fields.push(descriptor(keys,sanctification,'sanctification'));
 else {if(typeof sanctification.value!=='object'||Array.isArray(sanctification.value))throw new TypeError('Deity sanctification must be a source object or null.');fields.push(s('sanctification/modal','sanctification_modal_code','string'),...strings(source,[...keys,'what'],'sanctification_what_code'));}
 for(const [path,concept,nullable]of [['domains/primary','primary_domain_code'],['domains/alternate','alternate_domain_code'],['font','font_code'],['attribute','attribute_code'],['skill','skill_code',true],['weapons','weapon_code']])fields.push(...strings(source,['system',...path.split('/')],concept,nullable));
 const spellKeys=['system','spells'],spells=at(source,spellKeys);
 if(!spells.present)fields.push(descriptor(spellKeys,spells,'spell_entries'));
 else {if(!spells.value||typeof spells.value!=='object'||Array.isArray(spells.value)||Object.keys(spells.value).length>MAX_ENTRIES)throw new TypeError('Deity spell record is invalid or exceeds 12000 entries.');const names=Object.keys(spells.value);if(!names.length)fields.push(descriptor(spellKeys,spells,'spell_entries'));for(const key of names)fields.push(scalar(source,[...spellKeys,key],'spell_uuid','string'));}
 fields.push(...strings(source,['system','traits','otherTags'],'other_tag_code'),s('slug','source_slug','string',true));
 for(const [key,type]of [['title','string'],['authors','string'],['license','string'],['remaster','boolean']])fields.push(s('publication/'+key,'publication_'+key,type));
 return fields;
}
