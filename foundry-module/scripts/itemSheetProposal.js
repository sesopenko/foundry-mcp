/** PF2e-specific 8.7.0 physical/weapon authoring. Validate detached source only.
 * Derived controls, variant settings and owner context constrain allowable changes.
 * https://github.com/foundryvtt/pf2e/tree/52dfeee703b887237f5e454747bcae45b136f9af/src/module/item
 */
import {fail, integer, validateParams} from './actorReadUtils.js';
import {resolveJournalImage} from './journalImages.js';
import {children, choices, controls, definition, get, groupIds, isCommon, mandatoryRangedGroups} from './itemSheetFields.js';

const propertyId = 'material_and_runes.property_runes';
const invalid = (field, reason) => fail('InvalidRequest', field + ': ' + reason,
  'Read the field with read_item(sheet) and use get_item_field_options for current choices.');
export const equal = (a,b) => JSON.stringify(sorted(a)) === JSON.stringify(sorted(b));
export function sorted(value) {
  if (Array.isArray(value)) return value.map(sorted);
  if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map(k=>[k,sorted(value[k])]));
  return value;
}
function assign(object,path,value) {
  const keys = path.split('.');
  let node = object;
  for (const key of keys.slice(0,-1)) { node[key] ??= {}; node = node[key]; }
  node[keys.at(-1)] = value;
}

/** PF2e-specific 8.7.0 ABP on physical weapon owners. Read registered setting and declared actor flag/level. */
export function variant(target) {
  if (target.document.type !== 'weapon') return {abp:false, bonus:0};
  const setting = game.settings.get('pf2e','automaticBonusVariant');
  if (!['noABP','ABPFundamentalPotency','ABPRulesAsWritten'].includes(setting)) return {abp:null,bonus:null};
  const actor = target.actor;
  const abp = setting !== 'noABP' && (!actor || (!!actor.flags?.pf2e && !actor.flags.pf2e.disableABP));
  const level = abp && actor && actor.type !== 'loot' ? actor.system?.details?.level?.value : 20;
  return {abp, bonus: Number.isInteger(level) ? (level < 2 ? 0 : level < 10 ? 1 : level < 16 ? 2 : 3) : null};
}

/** PF2e-specific 8.7.0 property slots follow grade, material, ABP and applicable potency. */
export function capacity(system, ctx) {
  const {source,current,variant}=ctx;
  if (current.system.grade) return 0;
  // Unchanged dependencies use the transformed Item as on the GM's sheet.
  const material = source.system.material?.type === system.material?.type ? current.system.material?.type : system.material?.type;
  const resultingPotency = source.system.runes?.potency === system.runes?.potency ? current.system.runes?.potency : system.runes?.potency;
  const potency = variant.abp ? variant.bonus : resultingPotency;
  if (variant.abp === null || !Number.isInteger(potency) || potency < 0 || potency > 4) return null;
  return potency + Number(material === 'orichalcum');
}

/** PF2e-specific release-pinned applicability for source controls. Derived rune slots stay read-only. */
export function unavailable(ctx,id,system,slot) {
  if (ctx.target.reason) return ctx.target.reason;
  const type = ctx.target.document.type;
  if (type !== 'weapon' && !isCommon(id)) return 'This control requires a weapon.';
  if (id === 'header.display_name') return 'PF2e supplies the display name.';
  if (type === 'backpack' && id === 'weapon_summary.quantity') return 'Backpack quantity is fixed.';
  if (id === 'weapon_summary.bulk' && system.stackGroup) return 'The stack group determines Bulk.';
  if (id === 'details.range' && system.traits?.value?.some(t=>/^thrown-\d+$/.test(t))) return 'A thrown increment trait fixes this control at melee.';
  if (id.startsWith('material_and_runes.')) {
    if (system.group === 'bomb') return 'Bombs have no material and rune panel.';
    if (id.endsWith('specific_magic_weapon')) return null;
    if (system.specific && id === propertyId) return 'Disable Specific Magic Weapon to change property slots.';
    if (id.includes('precious_material')) return null;
    if (ctx.variant.abp === null || system.grade) return 'Rune configuration is unavailable for this variant or grade.';
    if (id !== propertyId && ctx.variant.abp) return 'Automatic Bonus Progression supplies fundamental bonuses.';
    if (id === propertyId && slot) {
      const count = capacity(system,ctx);
      if (count === null || slot > count) return 'Slot exceeds the resulting capacity.';
      const stored = ctx.source.system.runes?.property ?? [];
      const shown = ctx.current.system?.runes?.property ?? [];
      if (shown[slot-1] && shown[slot-1] !== stored[slot-1]) return 'PF2e supplies this slot.';
      if (slot > 1 && !system.runes?.property?.[slot-2]) return 'Fill preceding slots first.';
    }
  }
  return null;
}

/** PF2e-specific physical Item prose and bounded numeric controls, applied only to authored leaves. */
function normalize(id,kind,value) {
  if (['name','short','text'].includes(kind)) {
    const limit = kind === 'text' ? 2000 : 256;
    if (typeof value !== 'string' || [...value].length > limit || (kind === 'name' && !value.trim()) ||
        /\[\[|@[\w.:-]+\s*\[|[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/.test(value)) invalid(id,'use bounded plain prose.');
    return value.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }
  if (['amount','level','quantity','positive','dice'].includes(kind)) {
    return integer(value,undefined,['quantity','positive'].includes(kind)?1:0,kind === 'level'?30:kind === 'dice'?14:999999,id);
  }
  if (['weaponTraits','otherWeaponTags'].includes(kind)) {
    if (!Array.isArray(value) || value.length > 100 || new Set(value).size !== value.length) invalid(id,'expected distinct codes.');
  }
  return value;
}

function nonempty(object, keys, id) {
  validateParams(object,keys);
  if (!Object.keys(object).length) invalid(id,'supply a changed field.');
}

/** PF2e-specific 8.7.0 weapon classification constraints on final source. A
 * range/group/trait transition must preserve out-of-scope ammunition and alternate modes.
 */
export function classificationIssue(original, system) {
  const traits=system.traits?.value ?? [];
  if (!choices('range',system).some(([value])=>value===system.range)) {
    return ['details.range','incompatible group, traits and range.'];
  }
  const usesAmmo=(mandatoryRangedGroups.has(system.group) || !!system.range) &&
    !traits.includes('thrown') && system.reload?.value != null;
  if ((original.ammo != null || original.expend != null) && !usesAmmo) {
    return ['details.range','this configuration would discard stored ammunition data.'];
  }
  if (['tech','analog','combination'].some(t=>(original.traits?.value??[]).includes(t)!==traits.includes(t))) {
    return ['header.traits','this transition changes an out-of-scope weapon mode.'];
  }
  if (system.group==='bomb' && original.group!=='bomb' && (system.runes?.potency || system.runes?.striking ||
      system.runes?.property?.length || system.material?.type || system.specific)) {
    return ['details.group','clear the weapon configuration before selecting bomb.'];
  }
  return null;
}

/** PF2e-specific 8.7.0 build one allowlisted Foundry patch without mutating the Item.
 * Siblings are preserved by leaf updates. Nullable composites use explicit whole-record transitions.
 */
export async function proposal(ctx, changes) {
  nonempty(changes,groupIds,'changes');
  const source = ctx.source;
  const after = structuredClone(source);
  const patch = {};
  const fields = [];
  const finite = [];
  let slots, specific;
  const put = (path,value) => {assign(after,path,value); patch[path] = value;};
  for (const [group,values] of Object.entries(changes)) {
    const keys = Object.keys(controls).filter(k => k.startsWith(group+'.') && k !== 'header.display_name').map(k=>k.split('.')[1]);
    nonempty(values,keys,group);
    for (const [field,value] of Object.entries(values)) {
      const id = group + '.' + field;
      const [path,,,kind] = definition(id);
      fields.push(id);
      if (kind === 'property') { slots = value; continue; }
      if (id.endsWith('specific_magic_weapon')) { if (typeof value !== 'boolean') invalid(id,'expected boolean'); specific = value; continue; }
      if (kind === 'image') {put(path,(await resolveJournalImage(value)).src); continue;}
      if (kind === 'material' && value === null) {put(path,{type:null,grade:null}); continue;}
      if (kind === 'persistent' && value === null) {put(path,null); continue;}
      if (Object.hasOwn(children,id)) {
        nonempty(value,Object.keys(children[id]),id);
        for (const [leaf,child] of Object.entries(value)) {
          const leafId = id+'.'+leaf;
          const [p,,,k] = definition(leafId);
          put(p,normalize(leafId,k,child));
          finite.push([leafId,k,child]);
        }
      } else {
        put(path,normalize(id,kind,value));
        finite.push([id,kind,value]);
      }
    }
  }
  const sys = after.system;
  if (specific === false) put('system.specific',null);
  for (const id of fields) {
    const reason = unavailable(ctx,id,sys);
    if (reason) invalid(id,reason);
  }
  for (const [id,kind,value] of finite) {
    const domain = choices(kind,sys);
    if (domain && !(Array.isArray(value) ? value : [value]).every(v=>domain.some(([code])=>code===v))) invalid(id,'unavailable choice.');
    if (domain && Array.isArray(value) && !['weaponTraits','otherWeaponTags'].includes(kind)) invalid(id,'expected a scalar.');
  }
  if (fields.some(id=>['details.group','details.range','header.traits'].includes(id))) {
    const issue=classificationIssue(source.system,sys);
    if (issue) invalid(...issue);
  }
  if ((changes.weapon_summary?.hands || changes.other_tags) && sys.traits?.otherTags?.includes('implement') && sys.usage?.value !== 'held-in-one-hand') {
    invalid('other_tags.tags','implement requires one-handed usage.');
  }
  const runeGroup = changes.material_and_runes;
  if (runeGroup && Object.hasOwn(runeGroup,'precious_material') && sys.material.type !== null) {
    if (source.system.specific && specific!==false && source.system.material?.type!==sys.material.type) {
      invalid('material_and_runes.precious_material','specific weapons retain their material type.');
    }
    if (!choices('grade',sys).some(([v])=>v !== null && v === sys.material.grade)) invalid('material_and_runes.precious_material','invalid material and grade pair.');
  }
  if (changes.damage?.persistent) {
    const {number,faces,type} = sys.damage.persistent;
    if (!Number.isSafeInteger(number) || number < 1 || ![null,4,6,8,10,12].includes(faces) ||
        !choices('damageTypes',sys).some(([v])=>v===type)) invalid('damage.persistent','provide a valid amount, faces (null for flat) and type.');
  }
  if (changes.damage?.base) {
    const {dice,die,damageType} = sys.damage;
    integer(dice,undefined,0,14,'damage.base.dice');
    if (!choices('die',sys).some(([v])=>v===die) || !choices('baseType',sys).some(([v])=>v===damageType)) invalid('damage.base','invalid complete damage tuple.');
  }
  if (runeGroup) {
    const property = [...(sys.runes?.property ?? [])];
    const count = capacity(sys,ctx);
    if (slots !== undefined) {
      if (!Array.isArray(slots) || !slots.length || slots.length > 5) invalid(propertyId,'supply one to five slot assignments.');
      const seen = new Set();
      for (const assignment of slots) {
        validateParams(assignment,['slot','value']);
        const {slot,value} = assignment;
        integer(slot,undefined,1,5,'slot');
        if (seen.has(slot) || !choices('property',sys).some(([v])=>v===value)) invalid(propertyId,'duplicate ordinal or unavailable weapon rune.');
        seen.add(slot);
        property[slot-1] = value;
      }
      while (property.length && property.at(-1) == null) property.pop();
      if (Array.from(property).some(v=>v == null) || new Set(property).size!==property.length) invalid(propertyId,'slots must be sequential and distinct.');
      put('system.runes.property',property);
      for (const {slot,value} of slots) {
        const reason = unavailable(ctx,propertyId,sys,slot);
        const clearOverflow = value===null && slot > property.length && slot <= (source.system.runes?.property?.length ?? 0);
        if (reason && !(clearOverflow && (reason.startsWith('Slot exceeds') || reason.startsWith('Fill preceding')))) invalid(propertyId,reason);
      }
    }
    if (count === null || property.length > count) invalid(propertyId,'explicitly clear occupied slots beyond the resulting capacity.');
    if (specific === true && !source.system.specific) {
      put('system.specific',{material:structuredClone(sys.material),runes:structuredClone(sys.runes)});
    }
  }
  if (changes.mystification && ('unidentified_name' in changes.mystification || 'unidentified_description' in changes.mystification) &&
      !source.system.identification?.unidentified) {
    const key = 'system.identification.unidentified';
    const data = sys.identification.unidentified;
    if (!Object.hasOwn(changes.mystification,'unidentified_name') || !Object.hasOwn(changes.mystification,'unidentified_description')) {
      invalid('mystification','initializing alternate presentation requires both display strings.');
    }
    for (const k of Object.keys(patch)) if (k.startsWith(key+'.')) delete patch[k];
    put(key,{...data,img:''});
  }
  for (const path of Object.keys(patch)) if (equal(get(source,path),patch[path])) delete patch[path];
  return {after,patch,fields:fields.sort()};
}
