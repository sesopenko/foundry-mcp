/** PF2e-specific 8.7.0 weapon and physical Item source paths and choice domains.
 * Machine keys never come from labels. Transformed fields are read independently.
 * https://github.com/foundryvtt/pf2e/tree/52dfeee703b887237f5e454747bcae45b136f9af/src/module/item
 * Public CONFIG.PF2E domains: same revision, src/scripts/config/index.ts.
 */
import {fail} from './actorReadUtils.js';

// Pinned WeaponPropertyRuneType keys and matching localization family in physical/runes.ts.
const runes = [
  'ancestralEchoing', 'anchoring', 'ashen', 'astral', 'authorized', 'bane', 'bloodbane',
  'bloodthirsty', 'bolkasBlessing', 'brilliant', 'called', 'coating', 'conducting', 'corrosive',
  'crushing', 'cunning', 'dancing', 'decaying', 'deathdrinking', 'deflecting', 'demolishing',
  'disrupting', 'earthbinding', 'energizing', 'energyVulnerability', 'extending', 'fanged', 'fearsome',
  'flaming', 'flickering', 'flurrying', 'frost', 'ghostTouch', 'giantKilling', 'greaterAnchoring',
  'greaterAshen', 'greaterAstral', 'greaterBloodbane', 'greaterBolkasBlessing', 'greaterBrilliant', 'greaterCorrosive', 'greaterCrushing',
  'greaterDecaying', 'greaterDisrupting', 'greaterEnergyVulnerability', 'greaterExtending', 'greaterFanged', 'greaterFearsome', 'greaterFlaming',
  'greaterFrost', 'greaterGiantKilling', 'greaterHauling', 'greaterImpactful', 'greaterKolssOath', 'greaterRooting', 'greaterShock',
  'greaterThundering', 'greaterTruddsStrength', 'grievous', 'hauling', 'holy', 'hopeful', 'hooked',
  'impactful', 'impossible', 'keen', 'kinWarding', 'kolssOath', 'majorFanged', 'majorRooting',
  'merciful', 'nightmare', 'pacifying', 'returning', 'rooting', 'serrating', 'shifting',
  'shock', 'shockwave', 'speed', 'spellStoring', 'swarming', 'thundering', 'truddsStrength',
  'trueRooting', 'underwater', 'unholy', 'vorpal', 'wounding',
];
const grades = {
  low: ['cold-iron','silver','sisterstone-dusk','sisterstone-scarlet','throneglass'],
  standard: ['abysium','adamantine','cold-iron','dawnsilver','djezet','duskwood','inubrix','noqual',
    'peachwood','siccatite','silver','sisterstone-dusk','sisterstone-scarlet','sloughstone','sovereign-steel','throneglass'],
  high: ['abysium','adamantine','cold-iron','dawnsilver','djezet','duskwood','inubrix','keep-stone','noqual',
    'orichalcum','peachwood','siccatite','silver','sisterstone-dusk','sisterstone-scarlet','sloughstone','sovereign-steel','throneglass','warpglass'],
};
// [source path, fallback GM label, localization key, choice domain or input kind].
export const controls = {
  'header.image': ['img','Artwork','DOCUMENT.Image','image'],
  'header.name': ['name','Name','Name','name'],
  'header.display_name': ['name','Display Name','', 'readonly'],
  'header.level': ['system.level.value','Level','PF2E.LevelLabel','level'],
  'header.rarity': ['system.traits.rarity','Rarity','PF2E.Rarity','rarityTraits'],
  'header.traits': ['system.traits.value','Traits','PF2E.TraitsLabel','weaponTraits'],
  'weapon_summary.quantity': ['system.quantity','Quantity','PF2E.QuantityLabel','quantity'],
  'weapon_summary.hands': ['system.usage.value','Hands','PF2E.Item.Weapon.HandsLabel','hands'],
  'weapon_summary.bulk': ['system.bulk.value','Bulk','PF2E.Item.Physical.Bulk.Label','bulk'],
  'weapon_summary.size': ['system.size','Size','PF2E.Size','actorSizes'],
  'weapon_summary.price': ['system.price','Price','PF2E.PriceLabel','price'],
  'details.category': ['system.category','Category','PF2E.Category','weaponCategories'],
  'details.group': ['system.group','Group','PF2E.WeaponGroupLabel','weaponGroups'],
  'details.base': ['system.baseItem','Base','PF2E.WeaponBaseLabel','baseWeaponTypes'],
  'details.range': ['system.range','Range','PF2E.TraitRange','range'],
  'material_and_runes.precious_material': ['system.material','Precious Material','PF2E.PreciousMaterialLabel','material'],
  'material_and_runes.potency_rune': ['system.runes.potency','Potency Rune','PF2E.PotencyRuneLabel','potency'],
  'material_and_runes.striking_rune': ['system.runes.striking','Striking Rune','PF2E.StrikingRuneLabel','striking'],
  'material_and_runes.property_runes': ['system.runes.property','Property Rune','PF2E.PropertyRuneLabel','property'],
  'material_and_runes.specific_magic_weapon': ['system.specific','Specific Magic Weapon','PF2E.Item.Weapon.SpecificMagicWeapon.Label','boolean'],
  'damage.base': ['system.damage','Base','PF2E.WeaponBaseLabel','base'],
  'damage.splash': ['system.splashDamage.value','Splash','PF2E.TraitSplash','amount'],
  'damage.persistent': ['system.damage.persistent','Persistent','PF2E.ConditionTypePersistentShort','persistent'],
  'other_tags.tags': ['system.traits.otherTags','Other Tags','PF2E.Item.Physical.OtherTags.Label','otherWeaponTags'],
  'publication.title': ['system.publication.title','Title','PF2E.Publication.Title','short'],
  'publication.authors': ['system.publication.authors','Author(s)','PF2E.Publication.Authors','short'],
  'publication.license': ['system.publication.license','License','PF2E.Publication.License.Label','license'],
  'publication.remaster': ['system.publication.remaster','Remaster?','PF2E.Publication.Remaster','boolean'],
  'description.text': ['system.description.value','Description','PF2E.DescriptionLabel','text'],
  'mystification.identification_status': ['system.identification.status','Identification Status','PF2E.identification.MystificationStatus','status'],
  'mystification.unidentified_name': ['system.identification.unidentified.name','Unidentified Name','','name'],
  'mystification.unidentified_description': ['system.identification.unidentified.data.description.value','Unidentified Description','','text'],
};
// Source child names differ from semantic IDs. Only declared leaves cross the bridge.
export const children = {
  'damage.base': {dice:['dice','dice'], die:['die','die'], type:['damageType','baseType']},
  'damage.persistent': {amount:['number','positive'], faces:['faces','faces'], type:['type','damageTypes']},
  'weapon_summary.price': Object.fromEntries(['pp','gp','sp','cp'].map(code => [code,['value.' + code,'amount']])),
  'material_and_runes.precious_material': {type:['type','materialType'], grade:['grade','grade']},
};
export const groupIds = [...new Set(Object.keys(controls).map(key => key.split('.')[0]))];
const groupLabels = {
  header:['','Header'], weapon_summary:['','Weapon Summary'], details:['PF2E.Details','Details'],
  material_and_runes:['PF2E.Item.Physical.MaterialRunes.Label','Precious Material and Runes'],
  damage:['PF2E.DamageLabel','Damage'], other_tags:['PF2E.Item.Physical.OtherTags.Label','Other Tags'],
  publication:['PF2E.Publication.Label','Publication'], description:['PF2E.Description','Description'],
  mystification:['PF2E.ItemMystification','Mystification'],
};
/** PF2e-specific 8.7.0 physical and weapon form groups in GM presentation order. */
export const groupLabel = id => localized(...groupLabels[id]);
/** PF2e-specific 8.7.0 source controls shared by the supported physical Item types. */
export const isCommon = id => ['header.name','weapon_summary.quantity','description.text'].includes(id) || id.startsWith('mystification.');
export const mandatoryRangedGroups = new Set(['bomb','bow','crossbow','firearm','sling']);
export const get = (data, path) => path.split('.').reduce((node, key) => node != null && Object.hasOwn(node,key) ? node[key] : undefined, data);
export function localized(key, fallback) {
  return key && game.i18n.has(key) ? game.i18n.localize(key) : fallback;
}
/** PF2e-specific 8.7.0 qualified ID to the declared physical/weapon source path and input kind. */
export function definition(id) {
  if (Object.hasOwn(controls,id)) return controls[id];
  const [group, control, leaf, ...extra] = id.split('.');
  const parent = group + '.' + control;
  const child = children[parent] && Object.hasOwn(children[parent],leaf) && children[parent][leaf];
  if (!child || extra.length) fail('InvalidRequest','Unknown Item field: ' + id);
  return [controls[parent][0] + '.' + child[0], controls[parent][1] + ' · ' + leaf, '', child[1]];
}
/** PF2e-specific 8.7.0 GM control labels, including the ordinal property slot. */
export const label = (id, slot) => {
  const [,fallback,key] = definition(id);
  return slot ? localized(key + slot, fallback + ' (' + slot + ')') : localized(key,fallback);
};

/** PF2e-specific 8.7.0 choice pairs for weapon/physical schemas and final source dependencies.
 * CONFIG.PF2E includes world homebrew. A missing config cannot authorize an arbitrary code.
 */
export function choices(kind, system) {
  const pairs = values => values.map(value => [value,String(value)]);
  const blank = [null,localized('None','None')];
  const config = globalThis.CONFIG?.PF2E ?? {};
  const configured = name => Object.entries(config[name] ?? {}).filter(([,v]) => typeof v === 'string')
    .map(([v,k]) => [v,localized(k,v)]);
  switch (kind) {
    case 'hands': return [['worngloves','0'],['held-in-one-hand','1'],['held-in-one-plus-hands','1+'],['held-in-two-hands','2']];
    case 'license': return pairs(['OGL','ORC']);
    case 'boolean': return pairs([false,true]);
    case 'status': return ['identified','unidentified'].map(v => [v,localized('PF2E.identification.' + v[0].toUpperCase() + v.slice(1),v)]);
    case 'bulk': return [[0,localized('PF2E.Item.Physical.Bulk.Negligible.Label','Negligible')],[0.1,localized('PF2E.Item.Physical.Bulk.Light.Label','Light')],...pairs(Array.from({length:50},(_,i)=>i+1))];
    case 'range': {
      const traits = system.traits?.value ?? [];
      const ranged = mandatoryRangedGroups.has(system.group) ||
        traits.some(t => ['combination','thrown','volley-20','volley-30','volley-50'].includes(t));
      const melee = traits.some(t => /^thrown-\d+$/.test(t));
      return [...(ranged ? [] : [[null,localized('PF2E.Item.Weapon.NoRangeMelee','None (Melee)')]]),
        ...(melee ? [] : [10,15,20,30,40,50,60,70,80,90,100,110,120,140,150,180,200,240,300]
          .map(v=>[v,game.i18n.has('PF2E.WeaponRangeN')?game.i18n.format('PF2E.WeaponRangeN',{range:v}):String(v)]))];
    }
    case 'materialType': return grades.high.filter(v=>!system.specific || v===system.material?.type)
      .map(v => [v,localized(config.preciousMaterials?.[v],v)]);
    case 'grade': return Object.keys(grades).filter(k => grades[k].includes(system.material?.type))
      .map(v => [v,localized(config.preciousMaterialGrades?.[v],v)]);
    case 'potency': return [0,1,2,3,4].map(v => [v,v ? localized('PF2E.WeaponPotencyRune'+v,'+'+v) : blank[1]]);
    case 'striking': return ['','Striking','Greater','Major','Mythic'].map((v,i) => [i,v ? localized('PF2E.Item.Weapon.Rune.Striking.'+v,v) : blank[1]]);
    case 'property': return [blank,...runes.map(v => [v,localized('PF2E.WeaponPropertyRune.'+v+'.Name',v)])];
    case 'die': return [blank,...pairs(['d4','d6','d8','d10','d12'])];
    case 'faces': return [[null,'Flat'],...[4,6,8,10,12].map(v => [v,'d'+v])];
    case 'baseType': return configured('damageTypes').filter(([v]) => v !== 'bleed');
    case 'weaponGroups': case 'baseWeaponTypes': return [blank,...configured(kind)];
    case 'actorSizes': return configured(kind).filter(([v]) => v !== 'sm');
    case 'otherWeaponTags': return configured(kind).filter(([v]) => v !== 'implement' || system.usage?.value === 'held-in-one-hand');
    case 'rarityTraits': case 'weaponCategories': case 'weaponTraits': case 'damageTypes': return configured(kind);
    default: return null;
  }
}
