/**
 * PF2e-specific selected physical Item source fields, tested against 8.6.1.
 * Input is detached Item.toObject(true), never a prepared Item/system object.
 * PhysicalSystemSource and concrete overrides establish source-only contracts:
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/physical/data.ts
 * No effective Bulk, actor bonuses, price normalization or resale is calculated.
 */
export const PHYSICAL_TYPES = Object.freeze(['weapon','armor','shield','equipment','consumable','ammo','backpack','book','treasure']);
const ATTACHMENT_TYPES = new Set(['weapon','armor','shield','equipment']);
const COMMON = [
 ['level/value','item_level'],['quantity','quantity'],['baseItem','base_item_code'],['size','size_code'],
 ['bulk/value','source_bulk'],['hp/value','current_item_hit_points'],['hp/max','source_maximum_item_hit_points'],['hardness','source_hardness'],
 ['price/value/pp','price_platinum'],['price/value/gp','price_gold'],['price/value/sp','price_silver'],['price/value/cp','price_copper'],
 ['price/per','price_per_quantity'],['price/sizeSensitive','price_size_sensitive'],
 ['equipped/carryType','carry_type_code'],['equipped/inSlot','in_slot'],['equipped/handsHeld','hands_held'],['equipped/invested','investment_state'],
 ['containerId','container_local_id'],['material/type','material_type_code'],['material/grade','material_grade_code'],
 ['identification/status','identification_status'],['identification/unidentified/name','unidentified_name'],
 ['identification/unidentified/img','unidentified_image'],['identification/unidentified/data/description/value','unidentified_description'],
 ['temporary','temporary_item']
];
const NUMBER_CONCEPTS = new Set(['item_level','quantity','source_bulk','current_item_hit_points','source_maximum_item_hit_points','source_hardness','price_platinum','price_gold','price_silver','price_copper','price_per_quantity','hands_held']);
const BOOLEAN_CONCEPTS = new Set(['price_size_sensitive','in_slot','investment_state','temporary_item']);
const NULLABLE_CONCEPTS = new Set(['base_item_code','container_local_id','material_type_code','material_grade_code','investment_state']);
function field(source,path,concept,limitations=[]) {
 let value=source; let present=true;
 for(const key of path.split('/')) {
  if(value===null||typeof value!=='object'||!Object.hasOwn(value,key)){present=false;break;}
  value=value[key];
 }
 // PF2e PriceField explicitly gives this optional source BooleanField initial undefined.
 // It has no JSON source value; do not confuse its prepared false with persisted data.
 if(present && value===undefined && path==='system/price/sizeSensitive') present=false;
 if(present) {
  const expected=NUMBER_CONCEPTS.has(concept)?'number':BOOLEAN_CONCEPTS.has(concept)?'boolean':'string';
  if (!(value===null&&NULLABLE_CONCEPTS.has(concept)) && (typeof value!==expected || (expected==='number'&&!Number.isFinite(value)))) {
   throw new TypeError(`Physical source field /${path} has an unexpected type.`);
  }
 }
 return {path:`/${path}`,present,...(present?{value}:{}),concept,limitations:[...limitations]};
}
/**
 * PF2e-specific 8.6.1 physical source selector for the nine PHYSICAL_TYPES.
 * Returns null for kit/nonphysical types; otherwise returns primitive descriptors
 * {path,present,value?,concept,limitations}. Absent is not null/zero/inapplicable.
 * Unknown codes and GM-unidentified source text are retained without substitution.
 * Armor/shield/treasure usage and treasure investment are excluded by their source
 * overrides. Subitems are serialized attachments, never embedded document UUIDs;
 * only direct local IDs/names/types are selected, without recursion or resolution.
 * Source schema: physical/data.ts; concrete armor/shield/treasure/container and
 * ammo/book/consumable/equipment/weapon data.ts at the pinned URL above.
 */
export function physicalFields(source) {
 if(!PHYSICAL_TYPES.includes(source?.type)) return null;
 const fields=COMMON.filter(([path])=>source.type!=='treasure'||!['equipped/invested','equipped/inSlot','equipped/handsHeld'].includes(path))
  .map(([path,concept])=>field(source,`system/${path}`,concept,['source_only_no_effective_calculation']));
 if(!['armor','shield','treasure'].includes(source.type)) fields.push(field(source,'system/usage/value','usage_code'));
 if(ATTACHMENT_TYPES.has(source.type)) {
  const system=source.system;
  if(system&&Object.hasOwn(system,'subitems')) {
   if(!Array.isArray(system.subitems)) throw new TypeError('Physical source /system/subitems must be an array.');
   if(!system.subitems.length) fields.push({path:'/system/subitems',present:true,value:[],concept:'serialized_attachments',limitations:['serialized_sources_not_embedded_documents']});
   for(let index=0;index<system.subitems.length;index++) {
    const attachment=system.subitems[index];
    if(!attachment||typeof attachment!=='object'||Array.isArray(attachment)) throw new TypeError('Physical attachment source must be an object.');
    for(const [key,concept] of [['_id','attachment_local_id'],['name','attachment_name'],['type','attachment_type_code']]) {
     fields.push(field(source,`system/subitems/${index}/${key}`,concept,['serialized_source_not_document','attachment_interpretation_pending']));
    }
   }
  } else fields.push({path:'/system/subitems',present:false,concept:'serialized_attachments',limitations:['serialized_sources_not_embedded_documents']});
 }
 return fields;
}
