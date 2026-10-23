/**
 * PF2e-specific class Item source selector, audited PF2e 8.6.1.
 * Detached Item.toObject(true) only: definition contributions and progression,
 * never effective character statistics, advancement or acquired features.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/class/data.ts
 * Rank schema: same revision src/module/model.ts; ABC entries: item/abc/data.ts.
 */
const LIMIT=['class_source_not_effective_character'];
const MAX_ENTRIES=12000;
const RANK_LABELS=['Untrained','Trained','Expert','Master','Legendary'];
/** PF2e-specific class source map keys retain exact JSON Pointer escaping. */
function escape(key){return key.replaceAll('~','~0').replaceAll('/','~1');}
/** PF2e-specific class own-source lookup; no defaults or inherited values. */
function at(source,keys){let value=source;for(const key of keys){if(value===null||typeof value!=='object'||!Object.hasOwn(value,key))return {present:false};value=value[key];}return {present:true,value};}
/** PF2e-specific class descriptor preserves detached schema presence and value. */
function descriptor(keys,selected,concept){return {path:'/'+keys.map(escape).join('/'),...selected,concept:'class_'+concept,limitations:[...LIMIT]};}
/** PF2e-specific class primitive validation; no coercion or calculated totals. */
function scalar(source,keys,concept,type,nullable=false){const selected=at(source,keys);if(selected.present&&!(nullable&&selected.value===null)&&(typeof selected.value!==type||(type==='number'&&!Number.isFinite(selected.value))))throw new TypeError(`Class source /${keys.map(escape).join('/')} has an unexpected type.`);return descriptor(keys,selected,concept);}
/** PF2e-specific class source lists retain order, codes and empty markers. */
function list(source,keys,concept,type,min=null){const selected=at(source,keys);if(!selected.present)return [descriptor(keys,selected,concept)];if(!Array.isArray(selected.value)||selected.value.length>MAX_ENTRIES)throw new TypeError('Class source list is invalid or exceeds 12000 entries.');if(!selected.value.length)return [descriptor(keys,selected,concept)];return selected.value.map((value,i)=>{if(typeof value!==type||(type==='number'&&(!Number.isFinite(value)||value<min)))throw new TypeError('Class source list has an invalid entry.');return descriptor([...keys,String(i)],{present:true,value},concept);});}
/** PF2e-specific class starting proficiency rank, not a bonus or effective rank. */
function rank(source,keys,concept){const row=scalar(source,keys,concept,'number');if(row.present){if(!Number.isInteger(row.value)||row.value<0||row.value>4)throw new TypeError('Class source rank must be an integer from 0 to 4.');row.mapped_value={rank:row.value,label:RANK_LABELS[row.value]};}return row;}
/**
 * PF2e-specific class source fields: keyAbility offers/nullable selection, hp,
 * starting proficiency ranks, trainedSkills, five progression value lists,
 * ABC items and shared metadata; PF2e 8.6.1 pinned schema above. Progression
 * accepts finite numbers >=1 (schema has no integer flag); ABC levels require
 * nonnegative integers. Codes remain exact, with no inferred choices, rules,
 * UUID hydration, advancement, acquired-feature claims or actor totals.
 * Returns null for other Item types; system gating belongs to the shared reader.
 */
export function classFields(source){
 if(source?.type!=='class')return null;
 /** PF2e-specific class scalar rooted in detached Item system source. */
 const s=(path,concept,type,nullable=false)=>scalar(source,['system',...path.split('/')],concept,type,nullable);
 const fields=[...list(source,['system','keyAbility','value'],'key_attribute_offer_code','string'),s('keyAbility/selected','key_attribute_selected_code','string',true),s('hp','hp_contribution','number')];
 const hp=fields.at(-1);if(hp.present&&(hp.value<4||hp.value>12))throw new TypeError('Class source hp must be from 4 to 12.');
 fields.push(rank(source,['system','perception'],'starting_perception_rank'));
 for(const name of ['fortitude','reflex','will'])fields.push(rank(source,['system','savingThrows',name],'starting_'+name+'_rank'));
 for(const name of ['simple','martial','advanced','unarmed'])fields.push(rank(source,['system','attacks',name],'starting_'+name+'_attack_rank'));
 // PF2e-specific optional StringField name: core14 constructor is nonnullable,
 // required:false/initial:undefined; missing/undefined remains absent.
 const otherName=at(source,['system','attacks','other','name']);
 fields.push(otherName.present&&otherName.value===undefined?descriptor(['system','attacks','other','name'],{present:false},'other_attack_name'):s('attacks/other/name','other_attack_name','string'),rank(source,['system','attacks','other','rank'],'starting_other_attack_rank'));
 for(const name of ['unarmored','light','medium','heavy'])fields.push(rank(source,['system','defenses',name],'starting_'+name+'_defense_rank'));
 fields.push(rank(source,['system','spellcasting'],'starting_spellcasting_rank'),...list(source,['system','trainedSkills','value'],'trained_skill_code','string'),s('trainedSkills/additional','additional_trained_skills','number'));
 const additional=fields.at(-1);if(additional.present&&(!Number.isInteger(additional.value)||additional.value<0))throw new TypeError('Class source additional trained skills must be a nonnegative integer.');
 for(const name of ['ancestryFeatLevels','classFeatLevels','generalFeatLevels','skillFeatLevels','skillIncreaseLevels'])fields.push(...list(source,['system',name,'value'],name.replace(/[A-Z]/g,c=>'_'+c.toLowerCase()),'number',1));
 const items=at(source,['system','items']);
 if(!items.present)fields.push(descriptor(['system','items'],items,'feature_entries'));
 else{
  if(!items.value||typeof items.value!=='object'||Array.isArray(items.value)||Object.keys(items.value).length>MAX_ENTRIES)throw new TypeError('Class source items must be a record of at most 12000 entries.');
  const keys=Object.keys(items.value);if(!keys.length)fields.push(descriptor(['system','items'],items,'feature_entries'));
  for(const key of keys){const entry=items.value[key];if(!entry||typeof entry!=='object'||Array.isArray(entry))throw new TypeError('Class source feature entry must be an object.');for(const [name,type]of [['uuid','string'],['img','string'],['name','string'],['level','number']]){const row=scalar(source,['system','items',key,name],'feature_'+(name==='img'?'image':name),type);if(name==='level'&&row.present&&(!Number.isInteger(row.value)||row.value<0))throw new TypeError('Class source feature level must be a nonnegative integer.');fields.push(row);}}
 }
 fields.push(...list(source,['system','traits','otherTags'],'other_tag_code','string'),s('traits/rarity','rarity_code','string'),s('slug','source_slug','string',true));
 for(const [key,type]of [['title','string'],['authors','string'],['license','string'],['remaster','boolean']])fields.push(s('publication/'+key,'publication_'+key,type));
 return fields;
}
