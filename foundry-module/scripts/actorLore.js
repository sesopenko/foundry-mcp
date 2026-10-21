/**
 * PF2e-specific Lore Item source selector, audited PF2e8.6.1/core14.369.
 * Detached toObject(true) source only; never prepared actor Skills or totals.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/lore.ts
 * Shared slug/publication: src/module/item/base/data/system.ts at that revision.
 * No ability/level defaults, preparation, rolls, writes or name-to-slug guessing.
 */
const OWNER_LIMIT=['owner_context_required_not_effective_total'];
const RANK_LABELS=['Untrained','Trained','Expert','Master','Legendary'];
/** Standard JSON Pointer escaping, preserving exact map keys. */
const escapePointer=key=>key.replaceAll('~','~0').replaceAll('/','~1');

/** PF2e-specific LoreSystemSource8.6.1 own-source path lookup, no defaults. */
function at(source,keys) {
  let value=source;
  for(const key of keys) {
    if(value===null||typeof value!=='object'||!Object.hasOwn(value,key))return {present:false};
    value=value[key];
  }
  return {present:true,value};
}
/** PF2e-specific LoreSystemSource8.6.1 primitive validation; never coercion. */
function field(source,keys,concept,type,nullable=false,limitations=[]) {
  const selected=at(source,keys);const path='/'+keys.map(escapePointer).join('/');
  if(selected.present&&!(nullable&&selected.value===null)&&(typeof selected.value!==type||(type==='number'&&!Number.isFinite(selected.value))))throw new TypeError(`Lore source field ${path} has an unexpected type.`);
  return {path,...selected,concept,limitations:[...limitations]};
}

/**
 * PF2e-specific `lore` source8.6.1 mod.value, proficient.value, variants,
 * traits.otherTags, slug and publication. Returns null for other Item types.
 * ownerType must come from the resolved actual Actor, never a caller assertion.
 * NPC modifiers are labelled authored; character ranks are labelled proficiency.
 * Unknown/absent owner context remains neutral. Neither becomes a check total.
 * Known rank labels preserve the raw integer; no bonus is calculated. The rank
 * retains its original integer0..4; no proficiency bonus or ability is derived.
 * Variant options are exact source strings, never executed roll options.
 * Only primitive leaves and explicit empty []/{} markers are emitted. No
 * description, rules, prepared skills, level or unsupported trait fields read.
 * Schema URL: src/module/item/lore.ts at the pinned module boundary URL above.
 */
export function loreFields(source,ownerType=null) {
  if(source?.type!=='lore')return null;
  const fields=[
    field(source,['system','mod','value'],ownerType==='npc'?'npc_lore_authored_modifier':'stored_lore_modifier','number',false,ownerType==='npc'?['authored_npc_modifier_not_effective_total']:OWNER_LIMIT),
    field(source,['system','proficient','value'],ownerType==='character'?'character_lore_proficiency_rank':'stored_lore_proficiency_rank','number',false,ownerType==='character'?['proficiency_rank_not_bonus_or_effective_total']:OWNER_LIMIT),
    field(source,['system','slug'],'source_slug','string',true)
  ];
  const rank=fields[1];
  if(rank.present&&(!Number.isInteger(rank.value)||rank.value<0||rank.value>4))throw new TypeError('Lore source proficiency rank must be an integer from 0 to 4.');
  if(rank.present)rank.mapped_value={rank:rank.value,label:RANK_LABELS[rank.value]};
  const tags=at(source,['system','traits','otherTags']);
  if(!tags.present)fields.push({path:'/system/traits/otherTags',present:false,concept:'lore_other_tag_code',limitations:[]});
  else {
    if(!Array.isArray(tags.value))throw new TypeError('Lore source otherTags must be an array.');
    if(!tags.value.length)fields.push({path:'/system/traits/otherTags',present:true,value:[],concept:'lore_other_tag_code',limitations:[]});
    tags.value.forEach((value,index)=>{
      if(typeof value!=='string')throw new TypeError('Lore source otherTags entries must be strings.');
      fields.push({path:`/system/traits/otherTags/${index}`,present:true,value,concept:'lore_other_tag_code',limitations:['code_preserved_without_unverified_label_lookup']});
    });
  }
  const variants=at(source,['system','variants']);
  if(!variants.present||variants.value===undefined)fields.push({path:'/system/variants',present:false,concept:'lore_variants',limitations:[]});
  else {
    if(variants.value===null||typeof variants.value!=='object'||Array.isArray(variants.value))throw new TypeError('Lore source variants must be a record.');
    const keys=Object.keys(variants.value);
    if(!keys.length)fields.push({path:'/system/variants',present:true,value:{},concept:'lore_variants',limitations:[]});
    for(const key of keys) {
      const variant=variants.value[key];
      if(variant===null||typeof variant!=='object'||Array.isArray(variant))throw new TypeError('Lore source variant must be an object.');
      fields.push(field(source,['system','variants',key,'label'],'lore_variant_label','string'),field(source,['system','variants',key,'options'],'lore_variant_options','string',false,['source_options_not_executed_or_effective_modifier']));
    }
  }
  for(const [key,type]of [['title','string'],['authors','string'],['license','string'],['remaster','boolean']])fields.push(field(source,['system','publication',key],`publication_${key}`,type));
  return fields;
}
