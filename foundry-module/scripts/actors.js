/** Read-only Actor/Item extraction foundation; contract: docs/actor-tools.md. */
import { fail, validateParams, integer, selector, selectSections, digest, textFragments, paginate } from './actorReadUtils.js';
import { ACTOR_TYPES, ITEM_TYPES, runtime, ready, named, permitted, actorTarget, itemTarget, embeddedIdentity } from './actorDocuments.js';
import { physicalFields, PHYSICAL_TYPES } from './actorPhysical.js';
import { weaponFields } from './actorWeapon.js';
import { ammoFields } from './actorAmmo.js';
import { armorFields } from './actorArmor.js';
import { containerFields } from './actorContainer.js';
import { treasureFields } from './actorTreasure.js';
import { containerRelationships } from './actorContainerRelationships.js';
import { shieldFields } from './actorShield.js';
import { equipmentFields } from './actorEquipment.js';
import { consumableFields,consumableSpellFields,consumableSpellDescriptionFields } from './actorConsumable.js';
import { spellFields,spellDescriptionFields } from './actorSpell.js';
import { spellcastingEntryFields,spellcastingEntryIssues } from './actorSpellcastingEntry.js';
import { actorCastingRecords } from './actorCasting.js';
import { actorInventoryRecords } from './actorInventory.js';
import { bookFields } from './actorBook.js';
import { bookRelationships } from './actorBookRelationships.js';
import { kitFields } from './actorKit.js';
import { kitRelationships } from './actorKitRelationships.js';
import { ancestryFields } from './actorAncestry.js';
import { ancestryRelationships } from './actorAncestryRelationships.js';
import { backgroundFields } from './actorBackground.js';
import { backgroundRelationships } from './actorBackgroundRelationships.js';
import { heritageFields } from './actorHeritage.js';
import { heritageRelationship } from './actorHeritageRelationships.js';
import { featGrantFields } from './actorFeatGrants.js';
import { featRelationships } from './actorFeatRelationships.js';
import { featFields } from './actorFeat.js';
import { deityFields } from './actorDeity.js';
import { deityRelationships } from './actorDeityRelationships.js';
import { classFields } from './actorClass.js';
import { classRelationships } from './actorClassRelationships.js';
import { spellEntryReference,spellEntryRelationship } from './actorSpellRelationships.js';
import { weaponAmmoReference,weaponAmmoRelationship } from './actorWeaponRelationships.js';
import { actionFields, actionReferenceFields } from './actorAction.js';
import { meleeFields, meleeEffectFields } from './actorMelee.js';
import { loreFields } from './actorLore.js';
import { npcFields, npcNoteFields } from './actorNpc.js';
import { effectFields } from './actorEffect.js';
import { conditionFields } from './actorCondition.js';
import { conditionReferenceFields,conditionRelationships } from './actorConditionRelationships.js';
import { effectReferenceFields,effectRelationships } from './actorEffectRelationships.js';

const ACTOR_SECTIONS = ['identity','source','description','build','statistics','skills','strikes','abilities','spellcasting','inventory','state','effective'];
const ITEM_SECTIONS = ['identity','source','description','rules','relationships','effective'];
const LIMITS = {default_limit:50,max_records:100,min_bytes:8000,max_bytes:48000,max_text_units:6000,max_cursor_characters:4096,max_selector_characters:512};
const PENDING = 'type_reader_pending';
const VERIFICATION = {deterministic:{status:'passed',evidence:['tests/js/actor-readers.test.js','tests/test_actor_tools.py']},live:{status:'not_run',evidence:[]}};

/** PF2e-specific8.6.1 selected Actor/Item source and explicit section joins.
 * Each typed selector documents its pinned schema boundary, including ancestry
 * choices/contributions in actorAncestry.js. Prepared values are never substituted.
 * Descriptions require their explicit section.
 * Never expose flags, migrations or the whole source object.
 */
function selection(target, sections) {
  const source = target.document.toObject(true);
  if (!source || typeof source!=='object' || Array.isArray(source)) fail('ReadFailed','Document source is not a serialized object.','Inspect the selected document in Foundry.');
  const selected = {};
  let physical=[];
  let weapon=[];
  let ammo=[];
  let armor=[];
  let treasure=[];let container=[];let containment={records:[],reasons:[]};
  let shield=[];
  let equipment=[];
  let consumable=[];let containedSpell=[];let containedDescriptions=[];
  let spell=[];let spellReference=null;let spellDescriptions=[];
  let castingEntry=[];let castingIssues=[];
  let castingView={records:[],reasons:[]};
  let inventoryView={records:[],reasons:[]};
  let book=[];let kit=[];let ancestry=[];let background=[];let heritage=[];let classSource=[];let deity=[];let feat=[];
  let weaponReference=null;
  let action=[];
  let melee=[];
  let lore=[];
  let npc=[];
  let effect=[];
  let condition=[];
  let conditionReferences=[];
  let effectReferences=[];
  let npcNotes=[];
  const specialties=[];const deniedLore=[];
  const npcItemSections={};
  if (sections.includes('source')) {
    for (const field of ['name','type']) if (Object.hasOwn(source,field)) {
      if (typeof source[field]!=='string') fail('ReadFailed',`Source ${field} has an unexpected type.`,'Inspect the selected document in Foundry.');
      selected[`/${field}`] = source[field];
    }
  }
  if (target.document.documentName==='Item' && PHYSICAL_TYPES.includes(source.type) && sections.includes('source')) {
    try { physical=physicalFields(source).filter(field=>field.concept!=='unidentified_description'); }
    catch (error) {
      const path=String(error?.message??'').match(/\/system\/[A-Za-z0-9_/-]+/)?.[0];
      fail('ReadFailed',`Selected physical source${path?` at ${path}`:''} does not match the verified field schema.`,'Inspect this Item source; malformed fields cannot be interpreted safely.');
    }
  }
  // PF2e-specific weapon8.6.1 definition/configuration; common source fields
  // remain in actorPhysical.js. No effective Strike or NPC attack is generated.
  if(target.document.documentName==='Item'&&source.type==='weapon'&&sections.includes('source')){
    try{weapon=weaponFields(source);}
    catch(error){
      const path=String(error?.message??'').match(/\/system\/[A-Za-z0-9_~/-]+/)?.[0];
      fail('ReadFailed',`Selected weapon source${path?` at ${path}`:''} does not match the verified schema.`,'Inspect weapon source; carried gear is not a prepared Strike or proof of usability.');
    }
  }
  if(target.document.documentName==='Item'&&source.type==='weapon'&&sections.includes('relationships')){
    try{weaponReference=weaponAmmoReference(source);}
    catch{fail('ReadFailed','Stored weapon ammunition reference has an unexpected type.','Inspect selectedAmmoId source; no loaded ammunition or compatibility is inferred.');}
  }
  // PF2e-specific ammo8.6.1 stored stock/use configuration, not compatibility,
  // automatic rule application or proof of a usable attack. See actorAmmo.js.
  if(target.document.documentName==='Item'&&source.type==='ammo'&&sections.includes('source')){
    try{ammo=ammoFields(source);}
    catch(error){
      const path=String(error?.message??'').match(/\/system\/[A-Za-z0-9_~/-]+/)?.[0];
      fail('ReadFailed',`Selected ammunition source${path?` at ${path}`:''} does not match the verified schema.`,'Inspect ammunition stock/use source; no weapon compatibility or consumption is inferred.');
    }
  }
  // PF2e-specific armor8.6.1 source constraints are not actor AC/saves/Speed.
  // Shared physical carrying/investment source remains separate; no benefits apply.
  if(target.document.documentName==='Item'&&source.type==='armor'&&sections.includes('source')){
    try{armor=armorFields(source);}
    catch(error){
      const path=String(error?.message??'').match(/\/system\/[A-Za-z0-9_~/-]+/)?.[0];
      fail('ReadFailed',`Selected armor source${path?` at ${path}`:''} does not match the verified schema.`,'Inspect armor source; no worn benefits, actor defense or rune effects are calculated.');
    }
  }
  // PF2e-specific treasure8.6.1 valuables; price/per, quantity and denomination
  // source remain separate. No derived asset value, stackGroup or sale arithmetic.
  if(target.document.documentName==='Item'&&source.type==='treasure'&&sections.includes('source')){
    try{treasure=treasureFields(source);}
    catch(error){
      const path=String(error?.message??'').match(/\/system\/[A-Za-z0-9_~/-]+/)?.[0];
      fail('ReadFailed',`Selected treasure source${path?` at ${path}`:''} does not match the verified schema.`,'Inspect treasure source; no denomination conversion, stack valuation or sale return is inferred.');
    }
  }
  // PF2e-specific backpack8.6.1 container source and explicit containment claims;
  // capacity/ignored Bulk never become a calculated contents or Actor total.
  if(target.document.documentName==='Item'&&source.type==='backpack'){
    try{
      if(sections.includes('source'))container=containerFields(source);
      if(sections.includes('relationships'))containment=containerRelationships(target,source);
    }catch(error){
      const path=String(error?.message??'').match(/\/system\/[A-Za-z0-9_~/-]+/)?.[0];
      fail('ReadFailed',`Selected container source${path?` at ${path}`:''} does not match the verified schema.`,'Inspect stored container links and Bulk configuration; no effective Bulk, capacity usage or inventory state is inferred.');
    }
  }
  // PF2e-specific shield8.6.1 stored definition/durability is not raised state,
  // Shield Block access or class-granted effective reinforcement. See actorShield.js.
  if(target.document.documentName==='Item'&&source.type==='shield'&&sections.includes('source')){
    try{shield=shieldFields(source);}
    catch(error){
      const path=String(error?.message??'').match(/\/system\/[A-Za-z0-9_~/-]+/)?.[0];
      fail('ReadFailed',`Selected shield source${path?` at ${path}`:''} does not match the verified schema.`,'Inspect shield source; no raised state, blocking access or effective reinforcement is inferred.');
    }
  }
  // PF2e-specific equipment8.6.1 metadata accompanies shared usage/investment.
  // Abilities may exist only in prose; no benefit or activation is applied.
  if(target.document.documentName==='Item'&&source.type==='equipment'&&sections.includes('source')){
    try{equipment=equipmentFields(source);}
    catch(error){
      const path=String(error?.message??'').match(/\/system\/[A-Za-z0-9_~/-]+/)?.[0];
      fail('ReadFailed',`Selected equipment source${path?` at ${path}`:''} does not match the verified schema.`,'Inspect equipment source; read description for prose abilities. Investment does not establish effective benefits.');
    }
  }
  // PF2e-specific consumable8.6.1 stock/uses and damage/healing source.
  // Contained spell definitions retain source paths on this consumable's UUID.
  if(target.document.documentName==='Item'&&source.type==='consumable'){
    try{
      if(sections.includes('source')){consumable=consumableFields(source);containedSpell=consumableSpellFields(source);}
      if(sections.includes('description'))containedDescriptions=consumableSpellDescriptionFields(source);
    }
    catch(error){
      const path=String(error?.message??'').match(/\/system\/[A-Za-z0-9_~/-]+/)?.[0];
      fail('ReadFailed',`Selected consumable source${path?` at ${path}`:''} does not match the verified schema.`,'Inspect consumable source; no use, activation, spell casting or formula evaluation occurs.');
    }
  }
  // PF2e-specific spell8.6.1 authored definitions; never prepare cast variants.
  if(target.document.documentName==='Item'&&source.type==='spell'){
    try{
      if(sections.includes('source'))spell=spellFields(source);
      if(sections.includes('relationships'))spellReference=spellEntryReference(source);
      if(sections.includes('description'))spellDescriptions=spellDescriptionFields(source);
    }catch(error){
      const path=String(error?.message??'').match(/\/system\/[A-Za-z0-9_~/-]+/)?.[0];
      fail('ReadFailed',`Selected spell source${path?` at ${path}`:''} does not match the verified schema.`,'Inspect spell source; no overlay evaluation, heightening or castability is calculated.');
    }
  }
  // PF2e-specific spellcastingEntry8.6.1 stored mode/resources, not usable casts.
  // Malformed preparation subtrees stay uninterpreted with explicit partial reasons.
  if(target.document.documentName==='Item'&&source.type==='spellcastingEntry'&&sections.includes('source')){
    try{castingEntry=spellcastingEntryFields(source);castingIssues=spellcastingEntryIssues(source);}
    catch(error){
      const path=String(error?.message??'').match(/\/system\/[A-Za-z0-9_~/-]+/)?.[0];
      fail('ReadFailed',`Selected casting-entry source${path?` at ${path}`:''} does not match the verified schema.`,'Inspect casting-entry source; prepared uses, shared slots, innate uses and focus resources are not interchangeable.');
    }
  }
  // PF2e-specific action source8.6.1; source-only selection never hydrates effects.
  if (target.document.documentName==='Item' && source.type==='action' && (sections.includes('source')||sections.includes('relationships'))) {
    try {action=sections.includes('source')?actionFields(source):actionReferenceFields(source);}
    catch (error) {
      const path=String(error?.message??'').match(/\/system\/[A-Za-z0-9_/-]+/)?.[0];
      fail('ReadFailed',`Selected action source${path?` at ${path}`:''} does not match the verified schema.`,'Inspect this action Item source; no prepared defaults are substituted.');
    }
  }
  // PF2e-specific authored NPC attacks: labels are source, not effect UUIDs.
  if (target.document.documentName==='Item' && source.type==='melee' && (sections.includes('source')||sections.includes('relationships'))) {
    try {melee=sections.includes('source')?meleeFields(source):meleeEffectFields(source);}
    catch (error) {
      const path=String(error?.message??'').match(/\/system\/[A-Za-z0-9_~/-]+/)?.[0];
      fail('ReadFailed',`Selected NPC attack source${path?` at ${path}`:''} does not match the verified schema.`,'Inspect this attack Item; authored fields cannot be replaced with carried weapon or prepared values.');
    }
  }
  // PF2e-specific Lore8.6.1: owner comes from the resolved document boundary,
  // not caller input. Rank labels never become an effective skill total.
  if (target.document.documentName==='Item' && source.type==='lore' && sections.includes('source')) {
    try {lore=loreFields(source,target.actor?.type??null);}
    catch (error) {
      const path=String(error?.message??'').match(/\/system\/[A-Za-z0-9_~/-]+/)?.[0];
      fail('ReadFailed',`Selected Lore source${path?` at ${path}`:''} does not match the verified schema.`,'Inspect this Lore Item; missing or malformed values cannot become calculated skill totals.');
    }
  }
  // PF2e-specific effect8.6.1 source; no preparation, formula evaluation or
  // derived expiry. Pinned schema and discriminators live in actorEffect.js.
  if (target.document.documentName==='Item' && source.type==='effect' && sections.includes('source')) {
    try {effect=effectFields(source);}
    catch (error) {
      const path=String(error?.message??'').match(/\/system\/[A-Za-z0-9_~/-]+/)?.[0];
      fail('ReadFailed',`Selected effect source${path?` at ${path}`:''} does not match the verified schema.`,'Inspect the effect source; malformed fields cannot be replaced with derived expiry or evaluated formulas.');
    }
  }
  if(target.document.documentName==='Item'&&source.type==='effect'&&sections.includes('relationships')){
    try{effectReferences=effectReferenceFields(source);}
    catch{fail('ReadFailed','Stored effect context references have an unexpected type.','Inspect the effect source context; no origin or target is inferred.');}
  }
  // PF2e-specific condition8.6.1 persisted source; stored presence/value and
  // override claims are not active/suppressed state. See actorCondition.js.
  if(target.document.documentName==='Item'&&source.type==='condition'&&sections.includes('source')){
    try{condition=conditionFields(source);}
    catch(error){
      const path=String(error?.message??'').match(/\/system\/[A-Za-z0-9_~/-]+/)?.[0];
      fail('ReadFailed',`Selected condition source${path?` at ${path}`:''} does not match the verified schema.`,'Inspect the condition source; no active state, suppression or damage roll is inferred.');
    }
  }
  if(target.document.documentName==='Item'&&source.type==='condition'&&sections.includes('relationships')){
    try{conditionReferences=conditionReferenceFields(source);}
    catch{fail('ReadFailed','Stored condition reference fields do not match the verified schema.','Inspect the condition source; no origin or suppression is inferred.');}
  }
  // PF2e-specific NPC8.6.1 authored stat-block source; no elite/weak math.
  // The pinned schema contract is documented in actorNpc.js.
  if (target.document.documentName==='Actor' && source.type==='npc' && sections.includes('source')) {
    try {npc=npcFields(source);}
    catch (error) {
      const path=String(error?.message??'').match(/\/system\/[A-Za-z0-9_~/-]+/)?.[0];
      fail('ReadFailed',`Selected NPC source${path?` at ${path}`:''} does not match the verified schema.`,'Inspect this NPC source; no prepared statistics or defaults are substituted.');
    }
  }
  // PF2e-specific NPC biography8.6.1 is explicit GM-only description source.
  if (target.document.documentName==='Actor' && source.type==='npc' && sections.includes('description')) {
    try {npcNotes=npcNoteFields(source);}
    catch {fail('ReadFailed','Selected NPC biography has an unexpected type.','Inspect the NPC blurb/public/private source notes; no prepared text is substituted.');}
  }
  // PF2e-specific feat8.6.1 source options, nominal/taken levels and subfeatures.
  // Declared source grants are not inferred from rules or offered progression.
  if(target.document.documentName==='Item'&&source.type==='feat'&&sections.some(name=>['source','relationships'].includes(name))){
    try{feat=[...featFields(source),...featGrantFields(source)];}
    catch{fail('ReadFailed','Selected feat source does not match the verified schema.','Inspect nominal/taken levels, activation, prerequisites and subfeatures; no choices, grants or effective benefits are inferred.');}
  }
  // PF2e-specific deity8.6.1 options do not establish active benefits.
  if(target.document.documentName==='Item'&&source.type==='deity'&&sections.some(name=>['source','relationships'].includes(name))){
    try{deity=deityFields(source);}
    catch{fail('ReadFailed','Selected deity source does not match the verified schema.','Inspect deity options and spell claims; no active benefits are inferred.');}
  }
  // PF2e-specific class8.6.1 starting ranks/progression are source contributions.
  if(target.document.documentName==='Item'&&source.type==='class'&&sections.some(name=>['source','relationships'].includes(name))){
    try{classSource=classFields(source);}
    catch(error){
      const path=String(error?.message??'').match(/\/system\/[A-Za-z0-9_~/-]+/)?.[0];
      fail('ReadFailed',`Selected class source${path?` at ${path}`:''} does not match the verified schema.`,'Inspect class key attribute, starting ranks, progression and feature definitions; no character totals, advancement or acquired features are inferred.');
    }
  }
  // PF2e-specific heritage8.6.1 association is a definition, not owner membership.
  if(target.document.documentName==='Item'&&source.type==='heritage'&&sections.some(name=>['source','relationships'].includes(name))){
    try{heritage=heritageFields(source);}
    catch(error){
      const path=String(error?.message??'').match(/\/system\/[A-Za-z0-9_~/-]+/)?.[0];
      fail('ReadFailed',`Selected heritage source${path?` at ${path}`:''} does not match the verified schema.`,'Inspect the stored nullable ancestry association and heritage metadata; no owner ancestry, eligibility or benefits are inferred.');
    }
  }
  // PF2e-specific background8.6.1 source choices/training and named definitions.
  if(target.document.documentName==='Item'&&source.type==='background'&&sections.some(name=>['source','relationships'].includes(name))){
    try{background=backgroundFields(source);}
    catch(error){
      const path=String(error?.message??'').match(/\/system\/[A-Za-z0-9_~/-]+/)?.[0];
      fail('ReadFailed',`Selected background source${path?` at ${path}`:''} does not match the verified schema.`,'Inspect stored background boosts, training and feature definitions; no missing grant, Lore or Actor training is created.');
    }
  }
  // PF2e-specific ancestry8.6.1 authored choices and contributions only.
  if(target.document.documentName==='Item'&&source.type==='ancestry'&&sections.some(name=>['source','relationships'].includes(name))){
    try{ancestry=ancestryFields(source);}
    catch(error){
      const path=String(error?.message??'').match(/\/system\/[A-Za-z0-9_~/-]+/)?.[0];
      fail('ReadFailed',`Selected ancestry source${path?` at ${path}`:''} does not match the verified schema.`,'Inspect stored ancestry choices and feature definitions; no prepared selections, acquired benefits or character totals are substituted.');
    }
  }
  // PF2e-specific kit8.6.1 is a serialized bundle, not physical owned stock.
  if(target.document.documentName==='Item'&&source.type==='kit'&&sections.some(name=>['source','relationships'].includes(name))){
    try{kit=kitFields(source);}
    catch(error){
      const path=String(error?.message??'').match(/\/system\/[A-Za-z0-9_~/-]+/)?.[0];
      fail('ReadFailed',`Selected kit source${path?` at ${path}`:''} does not match the verified schema.`,'Inspect serialized kit components and price source; no bundle is imported or converted into Actor possessions.');
    }
  }
  // PF2e-specific book8.6.1 source definitions, not owned formulas/prepared spells.
  if(target.document.documentName==='Item'&&source.type==='book'&&sections.some(name=>['source','relationships'].includes(name))){
    try{book=bookFields(source);}
    catch(error){
      const path=String(error?.message??'').match(/\/system\/[A-Za-z0-9_~/-]+/)?.[0];
      fail('ReadFailed',`Selected book source${path?` at ${path}`:''} does not match the verified schema.`,'Inspect book category, capacity and content UUID source; no contents, preparation or ownership is inferred.');
    }
  }
  // PF2e-specific Actor8.6.1 casting joins use actual owner Items and persisted
  // focus source only; availability and effective variants remain unevaluated.
  if(target.document.documentName==='Actor'&&sections.includes('spellcasting')){
    try{castingView=actorCastingRecords(target,source);}
    catch(error){
      const path=String(error?.message??'').match(/\/system\/[A-Za-z0-9_~/-]+/)?.[0];
      fail('ReadFailed',`Selected Actor casting source${path?` at ${path}`:''} does not match the verified schema.`,'Inspect the Actor casting source; no preparation, casting, resource expenditure or derived availability is evaluated.');
    }
  }
  // PF2e-specific8.6.1 inventory uses actual owned physical source and stored
  // containment/ammunition claims, never effective benefits or total Bulk.
  if(target.document.documentName==='Actor'&&sections.includes('inventory')){
    try{inventoryView=actorInventoryRecords(target);}
    catch(error){
      const path=String(error?.message??'').match(/\/system\/[A-Za-z0-9_~/-]+/)?.[0];
      fail('ReadFailed',`Selected Actor inventory source${path?` at ${path}`:''} does not match the verified schema.`,'Inspect owned Item source and stored container/ammunition links; no inventory mutation or effective calculation is performed.');
    }
  }
  // PF2e-specific Lore specialties are actual owned Item references only.
  // Source contract: src/module/item/lore.ts at the actorLore.js pinned revision.
  if (target.document.documentName==='Actor' && sections.includes('skills')) {
    for (const item of target.document.items.values()) {
      if (item.type!=='lore') continue;
      if (!permitted(item)) {deniedLore.push(item.uuid);continue;}
      const identity=embeddedIdentity(item,{document:target.document,token:target.token});
      const itemSource=item.toObject(true);
      if (typeof itemSource?.name!=='string'||itemSource.type!=='lore') fail('ReadFailed','Lore specialty source identity is invalid.','Inspect the owned Lore Item in the selected Actor.');
      specialties.push({identity,name:itemSource.name,type:itemSource.type});
    }
    const compare=(a,b)=>a<b?-1:a>b?1:0;
    specialties.sort((a,b)=>compare(a.name.toLowerCase(),b.name.toLowerCase())||compare(a.identity.uuid,b.identity.uuid));
    deniedLore.sort(compare);
  }
  // PF2e-specific NPC8.6.1 melee/action Items are explicit source references,
  // never prepared Strike arrays, acquired benefits or carried-weapon attacks.
  if (target.document.documentName==='Actor' && source.type==='npc') {
    for (const [section,type] of [['strikes','melee'],['abilities','action']]) {
      if(!sections.includes(section))continue;
      const entries=[],denied=[];
      for(const item of target.document.items.values()) {
        if(item.type!==type)continue;
        if(!permitted(item)){denied.push(item.uuid);continue;}
        const identity=embeddedIdentity(item,{document:target.document,token:target.token});
        const itemSource=item.toObject(true);
        if(typeof itemSource?.name!=='string'||itemSource.type!==type)fail('ReadFailed','NPC owned Item source identity is invalid.','Inspect the selected NPC attack or ability Item.');
        entries.push({identity,name:itemSource.name,type:itemSource.type});
      }
      const compare=(a,b)=>a<b?-1:a>b?1:0;
      entries.sort((a,b)=>compare(a.name.toLowerCase(),b.name.toLowerCase())||compare(a.identity.uuid,b.identity.uuid));denied.sort(compare);
      npcItemSections[section]={entries,denied};
    }
  }
  if (sections.includes('description') && source.system?.description && Object.hasOwn(source.system.description,'value')) selected['/system/description/value'] = source.system.description.value;
  if (sections.includes('description') && PHYSICAL_TYPES.includes(source.type)) {
    const data=source.system?.identification?.unidentified?.data?.description;
    if (data&&Object.hasOwn(data,'value')) selected['/system/identification/unidentified/data/description/value']=data.value;
  }
  return { identity: target.identity, selected, physical, weapon, ammo, armor, treasure, container, containment, shield, equipment, consumable, containedSpell, containedDescriptions, spell, spellReference, spellDescriptions, castingEntry, castingIssues, castingView, inventoryView, book, kit, ancestry, background, heritage, classSource, deity, feat, weaponReference, action, melee, lore, effect, condition, conditionReferences, effectReferences, npc, npcNotes, npcItemSections, specialties, deniedLore, runtime: runtime() };
}

/** PF2e-specific action8.6.1 selfEffect reference, resolved only on explicit
 * relationships requests. Public core14.369 fromUuid(uuid,{relative:Document}):
 * https://foundryvtt.com/api/v14/functions/foundry.utils.fromUuid.html
 * Public Actor.token carries synthetic target context (no UUID construction):
 * https://foundryvtt.com/api/v14/classes/foundry.documents.Actor.html#token
 * Returns identity/status only; no effect preparation, source expansion or use.
 */
async function actionRelationship(target,selected) {
  const reference=selected.action.find(field=>field.path==='/system/selfEffect/uuid');
  const uuid=reference?.present?reference.value:null;
  if (uuid===null||uuid===undefined||uuid==='') return {status:'missing',target_uuid:null,reason:'No stored self-effect reference.',dependency:null};
  if (typeof uuid!=='string'||uuid.length>512||!uuid.trim()) return {status:'unsupported',target_uuid:null,reason:'Stored self-effect reference is not a supported bounded UUID.',dependency:null};
  let effect;
  try {effect=await foundry.utils.fromUuid(uuid,{relative:target.document});}
  catch {return {status:'unverified',target_uuid:null,reason:'Self-effect resolution failed; retry an explicit relationships read.',dependency:null};}
  if (!effect) return {status:'missing',target_uuid:null,reason:'Stored self-effect target was not found.',dependency:null};
  const owner=effect.parent?.documentName==='Actor'?effect.parent:null;
  const pack=effect.compendium??owner?.compendium??null;
  if (!permitted(effect)||(owner&&!permitted(owner))||(pack&&!permitted(pack))) return {status:'denied',target_uuid:null,reason:'Self-effect target or owner/pack is not readable.',dependency:null};
  if (effect.documentName!=='Item'||effect.type!=='effect'||(owner&&!ACTOR_TYPES.includes(owner.type))||typeof effect.uuid!=='string'||!effect.uuid.length||effect.uuid.length>512) return {status:'unsupported',target_uuid:null,reason:'Self-effect target is outside the supported effect Item context.',dependency:null};
  let tokenUuid=null;
  if (effect.uuid.startsWith('Scene.')) {
    const token=owner?.token;
    if (!token?.uuid) return {status:'unverified',target_uuid:null,reason:'Synthetic self-effect target has no available token context.',dependency:null};
    let instance;
    try {instance=await actorTarget({token_uuid:token.uuid});}
    catch (error) {return {status:error?.rpcError?.code==='PermissionDenied'?'denied':'unverified',target_uuid:null,reason:'Synthetic self-effect token context is inaccessible or unavailable.',dependency:null};}
    if (instance.document.uuid!==owner.uuid||![...instance.document.items.values()].some(item=>item.uuid===effect.uuid)) return {status:'unverified',target_uuid:null,reason:'Synthetic self-effect no longer belongs to its current token Actor.',dependency:null};
    tokenUuid=token.uuid;
  }
  return {status:'resolved',target_uuid:effect.uuid,...(tokenUuid?{token_uuid:tokenUuid}:{}),reason:null,dependency:{uuid:effect.uuid,type:effect.type,parent_uuid:owner?.uuid??null,pack_id:pack?.collection??null}};
}

/** PF2e-specific detached source+immediate action relationship snapshot. */
async function snapshot(target,sections) {
  const selected=selection(target,sections);
  if (target.document.type==='action'&&sections.includes('relationships')) selected.relationship=await actionRelationship(target,selected);
  if(target.document.type==='effect'&&sections.includes('relationships'))selected.effectRelationships=await effectRelationships(selected.effectReferences);
  if(target.document.type==='condition'&&sections.includes('relationships'))selected.conditionRelationships=conditionRelationships(target,selected.conditionReferences);
  if(target.document.type==='spell'&&sections.includes('relationships'))selected.spellRelationship=spellEntryRelationship(target,selected.spellReference);
  if(target.document.type==='weapon'&&sections.includes('relationships'))selected.weaponRelationship=weaponAmmoRelationship(target,selected.weaponReference);
  if(target.document.type==='feat'&&sections.includes('relationships')){
    try{selected.featRelationships=await featRelationships(target,selected.feat);}
    catch{fail('ReadFailed','Feat references exceed the supported resolution bound or could not be read.','Read source first; relationships admit at most200 immediate claims.');}
  }
  if(target.document.type==='deity'&&sections.includes('relationships')){
    try{selected.deityRelationships=await deityRelationships(target,selected.deity);}
    catch{fail('ReadFailed','Deity spell references exceed the supported resolution bound.','Read source first; relationships admit at most200 immediate claims.');}
  }
  if(target.document.type==='class'&&sections.includes('relationships')){
    try{selected.classRelationships=await classRelationships(target,selected.classSource);}
    catch{fail('ReadFailed','Class feature references exceed the supported resolution bound.','Read source first and follow selected UUIDs with read_item; explicit relationships admit at most200 immediate claims.');}
  }
  if(target.document.type==='heritage'&&sections.includes('relationships'))selected.heritageRelationship=await heritageRelationship(target,selected.heritage);
  if(target.document.type==='background'&&sections.includes('relationships')){
    try{selected.backgroundRelationships=await backgroundRelationships(target,selected.background);}
    catch{fail('ReadFailed','Background feature references exceed the supported resolution bound.','Read source first and follow selected UUIDs with read_item; explicit relationships admit at most200 immediate claims.');}
  }
  if(target.document.type==='ancestry'&&sections.includes('relationships')){
    try{selected.ancestryRelationships=await ancestryRelationships(target,selected.ancestry);}
    catch{fail('ReadFailed','Ancestry feature references exceed the supported resolution bound.','Read source first and follow selected UUIDs with read_item; explicit relationships admit at most200 immediate claims.');}
  }
  if(target.document.type==='kit'&&sections.includes('relationships')){
    try{selected.kitRelationships=await kitRelationships(target,selected.kit);}
    catch{fail('ReadFailed','Kit component references exceed the supported resolution bound.','Read source first and follow selected UUIDs with read_item; explicit relationships admit at most200 immediate claims.');}
  }
  if(target.document.type==='book'&&sections.includes('relationships')){
    try{selected.bookRelationships=await bookRelationships(target,selected.book);}
    catch{fail('ReadFailed','Book content references exceed the supported resolution bound.','Read source first and follow selected UUIDs with read_item; explicit relationships admit at most200 immediate claims.');}
  }
  return selected;
}

/** JSON Pointer source record; values are detached selected document data. */
function record(uuid,path,present,value,section,concept) {
  return {key:`${section}:${path}`,section,kind:'field',raw:[{document_uuid:uuid,path,present,...(present?{value}:{}),basis:'source'}],
    mapped:{concept,value:present?value:null,unit:null},provenance:{contributors:[{document_uuid:uuid,path,basis:'source'}],mapping:'core.selected_source.v1',limitations:[]}};
}

/** Normalize request bounds before resolving any documents. */
function bounds(params, allowed, sectionNames) {
  validateParams(params,allowed);
  integer(params.limit,50,1,100,'limit'); integer(params.max_bytes,48000,8000,48000,'max_bytes');
  if (params.cursor !== undefined && params.cursor !== null && (typeof params.cursor!=='string' || !params.cursor.length || params.cursor.length>4096 || /[^\x00-\x7f]/.test(params.cursor))) fail('InvalidCursor','Use the returned ASCII continuation, unchanged.','Restart without cursor.');
  return sectionNames ? selectSections(params.sections,sectionNames,['identity','source']) : null;
}

/**
 * PF2e-specific capability registry for character/npc/familiar and 24 Item types.
 * Core14.369/PF2e8.6.1 schema scope: only common core metadata and explicit Item
 * system.description.value and shared physical source fields are delivered;
 * action and NPC attack Items have selected type mappings and named references;
 * other concrete types and all derived/effective values remain gated.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/base/data/model.ts
 */
export async function getActorTypes(params = {}) {
  validateParams(params,[]); const current = ready(false);
  const supported = current.core_version==='14.369' && current.system_id==='pf2e' && current.system_version==='8.6.1';
  const make = (name, allowed, inScope, sections=false) => ({...(sections?{name}:{type:name,name}),allowed,in_scope:inScope,
    source_supported:supported&&inScope&&(!sections||['identity','source','description'].includes(name)),mapped_supported:false,effective_supported:false,
    limitations:inScope?['Foundation selects core metadata, explicit descriptions and shared physical source fields where applicable; type-specific mappings and effective sections are pending.']:['Type is outside initial Actor/Item scope.'],verification:structuredClone(VERIFICATION)});
  const actorAllowed = globalThis.foundry?.documents?.Actor?.TYPES ?? globalThis.Actor?.TYPES ?? [];
  const itemAllowed = globalThis.foundry?.documents?.Item?.TYPES ?? globalThis.Item?.TYPES ?? [];
  const result = {contract_version:1,runtime:current,availability:{supported,reason:supported?null:'Supported pairing: Foundry14.369/PF2e8.6.1.'},
    actor_types:[...new Set([...ACTOR_TYPES,...actorAllowed])].map(type=>make(type,actorAllowed.includes(type),ACTOR_TYPES.includes(type))),
    item_types:[...new Set([...ITEM_TYPES,...itemAllowed])].map(type=>make(type,itemAllowed.includes(type),ITEM_TYPES.includes(type))),
    actor_sections:ACTOR_SECTIONS.map(name=>make(name,true,true,true)),item_sections:ITEM_SECTIONS.map(name=>make(name,true,true,true)),limits:{...LIMITS},
    limitations:['No complete effective statistics or exhaustive ability list is claimed.']};
  // PF2e-specific action8.6.1 source milestone; section flags are conditional on
  // this per-type registry, never a promise for every other Item type.
  if (supported) {
    const action=result.item_types.find(entry=>entry.type==='action');
    action.mapped_supported=true;
    action.limitations=['Selected action activation/frequency/traits/publication source and explicit self-effect references; no effective usability or automatic application.'];
    action.verification={deterministic:{status:'passed',evidence:['tests/js/actor-action.test.js','tests/js/actor-action-readers.test.js','tests/test_actor_action.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/action-fields.md','scripts/actor-live-check.py']}};
    const melee=result.item_types.find(entry=>entry.type==='melee');
    melee.mapped_supported=true;
    melee.limitations=['Authored NPC attack modes, bonus/damage/range source and named effect labels; no effective elite/weak/MAP/target math. Null source range does not exclude thrown traits. Live checks cover Strikes; other modes have schema/fixture coverage.'];
    melee.verification={deterministic:{status:'passed',evidence:['tests/js/actor-melee.test.js','tests/js/actor-melee-readers.test.js','tests/test_actor_melee.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/melee-fields.md','scripts/actor-live-check.py']}};
    const treasure=result.item_types.find(entry=>entry.type==='treasure');
    treasure.mapped_supported=true;
    treasure.limitations=['Stored valuables category, traits/publication and shared physical quantity, denomination price/per, material/carry/container source. No stack value, coin conversion or sale proceeds are inferred. Loot Actors remain excluded; treasure Items on supported Actors remain included.'];
    treasure.verification={deterministic:{status:'passed',evidence:['tests/js/actor-treasure.test.js','tests/js/actor-treasure-readers.test.js','tests/test_actor_treasure.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/treasure-verification.md','scripts/actor-live-check.py']}};
    const container=result.item_types.find(entry=>entry.type==='backpack');
    container.mapped_supported=true;
    container.limitations=['Container source and explicitly requested same-owner containment graph only; nested contents appear once, cycles/missing/denied/unsupported parents remain explicit. Capacity/ignored Bulk do not establish current contents or Actor Bulk. Unowned containers have unverified contents scope. Live verification covers compendium containers only; owned/token graphs have deterministic coverage.'];
    container.verification={deterministic:{status:'passed',evidence:['tests/js/actor-container.test.js','tests/js/actor-container-readers.test.js','tests/test_actor_container.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/container-verification.md','scripts/actor-live-check.py']}};
    // PF2e-specific feat8.6.1 source milestone; persisted-grant joins remain pending.
    const feat=result.item_types.find(entry=>entry.type==='feat');
    feat.mapped_supported=true;
    feat.limitations=['Selected feat/feature category, nominal/taken level, activation, prerequisite prose, frequency and subfeature source only; no eligibility, reciprocal grant causality or effective benefits. Explicit references resolve actual same-owner grant IDs and immediate self-effect/suppressed-feature UUIDs only.'];
    feat.verification={deterministic:{status:'passed',evidence:['tests/js/actor-feat.test.js','tests/js/actor-feat-readers.test.js','tests/js/actor-feat-grants.test.js','tests/js/actor-feat-relationships.test.js','tests/test_actor_feat.py','tests/test_actor_feat_grants.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/feat-verification.md','scripts/actor-live-check.py']}};
    // PF2e-specific deity8.6.1 source options, verified on the recorded runtime.
    const deity=result.item_types.find(entry=>entry.type==='deity');
    deity.mapped_supported=true;
    deity.limitations=['Deity source options and immediate spell identity links only; no acquired spells, ownership, worship benefits or current casting options are inferred.'];
    deity.verification={deterministic:{status:'passed',evidence:['tests/js/actor-deity.test.js','tests/js/actor-deity-readers.test.js','tests/test_actor_deity.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/deity-verification.md','scripts/actor-live-check.py']}};
    const classType=result.item_types.find(entry=>entry.type==='class');
    classType.mapped_supported=true;
    classType.limitations=['Class source key-attribute choices, HP contribution, labelled starting ranks, training and progression with explicit immediate feature definitions. No current Actor totals, acquired future features or advancement are inferred.'];
    classType.verification={deterministic:{status:'passed',evidence:['tests/js/actor-class.test.js','tests/js/actor-class-readers.test.js','tests/test_actor_class.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/class-verification.md','scripts/actor-live-check.py']}};
    const heritage=result.item_types.find(entry=>entry.type==='heritage');
    heritage.mapped_supported=true;
    heritage.limitations=['Heritage source metadata and explicit immediate nullable ancestry association only; no owner ancestry, exclusivity, eligibility or effective benefits are inferred.'];
    heritage.verification={deterministic:{status:'passed',evidence:['tests/js/actor-heritage.test.js','tests/js/actor-heritage-readers.test.js','tests/test_actor_heritage.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/heritage-verification.md','scripts/actor-live-check.py']}};
    const background=result.item_types.find(entry=>entry.type==='background');
    background.mapped_supported=true;
    background.limitations=['Background source choices, training/Lore labels and explicit immediate feature definition identities only; no duplicate-training resolution or acquired feat/Lore joins. CORE-build owns acquired multi-contributor integration.'];
    background.verification={deterministic:{status:'passed',evidence:['tests/js/actor-background.test.js','tests/js/actor-background-readers.test.js','tests/test_actor_background.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/background-verification.md','scripts/actor-live-check.py']}};
    const ancestry=result.item_types.find(entry=>entry.type==='ancestry');
    ancestry.mapped_supported=true;
    ancestry.limitations=['Ancestry source choices/contributions and explicit immediate feature definition identities only. Default/offered/selected/alternate/legacy choices remain distinct; no current character totals or acquired features are inferred.'];
    ancestry.verification={deterministic:{status:'passed',evidence:['tests/js/actor-ancestry.test.js','tests/js/actor-ancestry-readers.test.js','tests/test_actor_ancestry.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/ancestry-verification.md','scripts/actor-live-check.py']}};
    const kit=result.item_types.find(entry=>entry.type==='kit');
    kit.mapped_supported=true;
    kit.limitations=['Serialized nested bundle definitions, source price and explicit immediate component identities only; no imported inventory, generated possession UUIDs or recursive target expansion.'];
    kit.verification={deterministic:{status:'passed',evidence:['tests/js/actor-kit.test.js','tests/js/actor-kit-readers.test.js','tests/test_actor_kit.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/kit-verification.md','scripts/actor-live-check.py']}};
    const book=result.item_types.find(entry=>entry.type==='book');
    book.mapped_supported=true;
    book.limitations=['Book category/capacity/contents and explicit immediate named content links only; no formula ownership, preparation, castability or recursive expansion. Deterministic coverage only: no representative live book Item exists in the existing runtime.'];
    book.verification={deterministic:{status:'passed',evidence:['tests/js/actor-book.test.js','tests/js/actor-book-readers.test.js','tests/test_actor_book.py']},live:{status:'not_run',evidence:['docs/actor-item-story-map/book-verification.md']}};
    const inventory=result.actor_sections.find(entry=>entry.name==='inventory');
    inventory.source_supported=true;inventory.mapped_supported=true;
    inventory.limitations=['Owned physical possessions and persisted container/selected-ammunition links, preserving distinct quantities, price/per, carry/investment and serialized attachment metadata. No total Bulk, sale proceeds or effective benefits. Book/kit specialty expansion remains partial.'];
    inventory.verification={deterministic:{status:'passed',evidence:['tests/js/actor-inventory.test.js','tests/js/actor-inventory-readers.test.js','tests/test_actor_inventory.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/inventory-verification.md','scripts/actor-live-check.py']}};
    const casting=result.actor_sections.find(entry=>entry.name==='spellcasting');
    casting.source_supported=true;casting.mapped_supported=true;
    casting.limitations=['Partial Actor casting source join with actual owned group/spell identities, preparations and persisted focus fields. Availability, effective cast ranks, ritual/flexible/item execution and resource expenditure remain unevaluated.'];
    casting.verification={deterministic:{status:'passed',evidence:['tests/js/actor-casting.test.js','tests/js/actor-casting-readers.test.js','tests/test_actor_casting.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/casting-verification.md','scripts/actor-live-check.py']}};
    const castingEntry=result.item_types.find(entry=>entry.type==='spellcastingEntry');
    castingEntry.mapped_supported=true;
    castingEntry.limitations=['Stored casting mode and per-slot/preparation resource source only; malformed or legacy preparations remain explicitly partial. No slot exhaustion, focus/innate resources, effective DC/attack or castability is inferred. Spell joins belong to CORE-casting.'];
    castingEntry.verification={deterministic:{status:'passed',evidence:['tests/js/actor-spellcasting-entry.test.js','tests/js/actor-spellcasting-entry-readers.test.js','tests/test_actor_spellcasting_entry.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/spellcasting-entry-verification.md','scripts/actor-live-check.py']}};
    const spell=result.item_types.find(entry=>entry.type==='spell');
    spell.mapped_supported=true;
    spell.limitations=['Stored spell definition, base rank, heightening/overlay source and immediate casting-entry assignment only. No evaluated variants, cast rank, spell slot availability or castability.'];
    spell.verification={deterministic:{status:'passed',evidence:['tests/js/actor-spell.test.js','tests/js/actor-spell-readers.test.js','tests/js/actor-spell-relationships.test.js','tests/test_actor_spell.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/spell-verification.md','scripts/actor-live-check.py']}};
    const consumable=result.item_types.find(entry=>entry.type==='consumable');
    consumable.mapped_supported=true;
    consumable.limitations=['Selected consumable stock, uses and damage/healing plus contained spell definitions and explicit prose. Nested spell source retains this Item UUID and source paths; no independent spell UUID, resolved nested entry, consumption, activation, castability or frequency expenditure.'];
    consumable.verification={deterministic:{status:'passed',evidence:['tests/js/actor-consumable.test.js','tests/js/actor-consumable-readers.test.js','tests/test_actor_consumable.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/consumable-verification.md','scripts/actor-live-check.py']}};
    const equipment=result.item_types.find(entry=>entry.type==='equipment');
    equipment.mapped_supported=true;
    equipment.limitations=['Stored equipment usage, investment, traits and attachments only; explicit description preserves prose abilities. No effective benefits, activation, frequency use or rule application is inferred.'];
    equipment.verification={deterministic:{status:'passed',evidence:['tests/js/actor-equipment.test.js','tests/js/actor-equipment-readers.test.js','tests/test_actor_equipment.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/equipment-verification.md','scripts/actor-live-check.py']}};
    const shield=result.item_types.find(entry=>entry.type==='shield');
    shield.mapped_supported=true;
    shield.limitations=['Stored shield/rune/integrated configuration and source durability only. Source HP max may differ from effective reinforced max; no clamping, raised state, Shield Block access, class reinforcement or generated attacks are inferred. Live checks cover compendium sources only.'];
    shield.verification={deterministic:{status:'passed',evidence:['tests/js/actor-shield.test.js','tests/js/actor-shield-readers.test.js','tests/test_actor_shield.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/shield-verification.md','scripts/actor-live-check.py']}};
    const armor=result.item_types.find(entry=>entry.type==='armor');
    armor.mapped_supported=true;
    armor.limitations=['Stored armor properties, source runes and carrying/investment state only. Source AC bonus is not Actor AC; worn benefits, saves, Speed and automatic rune effects are unsupported.'];
    armor.verification={deterministic:{status:'passed',evidence:['tests/js/actor-armor.test.js','tests/js/actor-armor-readers.test.js','tests/test_actor_armor.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/armor-verification.md','scripts/actor-live-check.py']}};
    const ammo=result.item_types.find(entry=>entry.type==='ammo');
    ammo.mapped_supported=true;
    ammo.limitations=['Stored stock/use and crafting categories only; counts do not establish compatibility or a usable attack. Only explicit weapon selection follows an ammo stack; carried rules/effects are not automatically applied.'];
    ammo.verification={deterministic:{status:'passed',evidence:['tests/js/actor-ammo.test.js','tests/js/actor-ammo-readers.test.js','tests/test_actor_ammo.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/ammo-verification.md','scripts/actor-live-check.py']}};
    const weapon=result.item_types.find(entry=>entry.type==='weapon');
    weapon.mapped_supported=true;
    weapon.limitations=['Persisted weapon definition/configuration and shared physical source only. No final Strike or NPC authored attack is generated; carried gear is not proof of usability. Explicit stored selectedAmmoId resolves actual owner-local ammo/weapon Items; loaded/compatible ammunition and effective alternate-use calculations remain unsupported.'];
    weapon.verification={deterministic:{status:'passed',evidence:['tests/js/actor-weapon.test.js','tests/js/actor-weapon-readers.test.js','tests/js/actor-weapon-relationships.test.js','tests/test_actor_weapon.py','tests/test_actor_weapon_relationships.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/weapon-verification.md','scripts/actor-live-check.py']}};
    const affliction=result.item_types.find(entry=>entry.type==='affliction');
    affliction.source_supported=false;affliction.mapped_supported=false;
    affliction.limitations=['PF2e8.6.1 production disables affliction Item construction. Offline schema selectors exist but runtime reading is unsupported; use original poison/disease/curse descriptions.'];
    affliction.verification={deterministic:{status:'passed',evidence:['tests/js/actor-affliction.test.js','tests/js/actor-affliction-support.test.js']},live:{status:'not_run',evidence:['docs/actor-item-story-map/affliction-verification.md']}};
    const condition=result.item_types.find(entry=>entry.type==='condition');
    condition.mapped_supported=true;
    condition.limitations=['Persisted condition/value, persistent damage, local references and override slugs only. Activity, suppression, effective duration and damage dominance are unsupported. Explicit relationships resolve actual owner-local Item IDs; override slugs remain unverified.'];
    condition.verification={deterministic:{status:'passed',evidence:['tests/js/actor-condition.test.js','tests/js/actor-condition-readers.test.js','tests/js/actor-condition-relationships.test.js','tests/test_actor_condition.py','tests/test_actor_condition_relationships.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/condition-verification.md','scripts/actor-live-check.py']}};
    const effect=result.item_types.find(entry=>entry.type==='effect');
    effect.mapped_supported=true;
    effect.limitations=['Persisted duration/start, badge discriminator and context source only; formulas are not evaluated, source UUID references are unverified until explicit immediate context resolution; expiry/current application remain unsupported.'];
    effect.verification={deterministic:{status:'passed',evidence:['tests/js/actor-effect.test.js','tests/js/actor-effect-readers.test.js','tests/js/actor-effect-relationships.test.js','tests/test_actor_effect.py','tests/test_actor_effect_relationships.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/effect-verification.md','scripts/actor-live-check.py']}};
    const lore=result.item_types.find(entry=>entry.type==='lore');
    lore.mapped_supported=true;
    lore.limitations=['Stored Lore modifier and labelled rank use actual owner type; no character or NPC effective check total. Standalone Items retain neutral stored semantics.'];
    lore.verification={deterministic:{status:'passed',evidence:['tests/js/actor-lore.test.js','tests/js/actor-lore-readers.test.js','tests/test_actor_lore.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/lore-fields.md','scripts/actor-live-check.py']}};
    const skills=result.actor_sections.find(entry=>entry.name==='skills');
    skills.source_supported=true;skills.mapped_supported=true;
    skills.verification=structuredClone(lore.verification);
    skills.limitations=['Lore specialty Item references only; all other Skills and effective totals remain pending.'];
    for (const actor of result.actor_types.filter(entry=>entry.in_scope)) {
      actor.mapped_supported=true;
      actor.limitations=['Only Lore specialty references in skills are mapped so far; full type-specific source/statistics and effective views remain pending.'];
    }
    for(const name of ['strikes','abilities']) {
      const section=result.actor_sections.find(entry=>entry.name===name);
      section.source_supported=true;section.mapped_supported=true;
      section.verification={deterministic:{status:'passed',evidence:['tests/js/actor-npc-readers.test.js','tests/test_actor_npc_references.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/npc-fields.md','scripts/actor-live-check.py']}};
      section.limitations=['NPC actual owned melee/action Item references only; sections remain partial. Other Actor types and effective attack/ability lists remain unsupported.'];
    }
    const description=result.actor_sections.find(entry=>entry.name==='description');
    description.limitations=['NPC biography only: blurb, publicNotes and GM-private privateNotes; explicit selection required. Character/familiar biography remains unsupported.'];
    const npc=result.actor_types.find(entry=>entry.type==='npc');
    npc.limitations=['Authored NPC source statistics and Lore references are delivered. Explicit description exposes separate bounded biography notes; integrated sections and effective/current statistics remain pending; elite/weak math is not applied.'];
    npc.verification={deterministic:{status:'passed',evidence:['tests/js/actor-npc.test.js','tests/js/actor-npc-readers.test.js','tests/test_actor_npc.py']},live:{status:'passed',evidence:['docs/actor-item-story-map/npc-fields.md','scripts/actor-live-check.py']}};
    for (const section of result.item_sections.filter(entry=>['source','relationships'].includes(entry.name))) {
      section.source_supported=true;section.mapped_supported=true;
      section.limitations=['Action, NPC attack and Lore Items have delivered source mappings; relationships currently cover action self-effects and named attack effects. Inspect individual type entries.'];
    }
  }
  if (new TextEncoder().encode(JSON.stringify(result)).length>48000) fail('ResponseTooLarge','Runtime type declarations exceed the registry response budget.','Inspect custom type declarations with the GM; this registry cannot be returned safely.');
  return result;
}

/**
 * PF2e-specific read boundary: selected Item descriptions and shared physical
 * source schema8.6.1; character/npc/familiar metadata has no effective meaning.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/base/data/model.ts
 */
async function read(target,params,sections,tool) {
  const selected = await snapshot(target,sections); const revision = await digest(selected);
  const records = [];
  if (sections.includes('source')) {
    for (const field of ['name','type']) records.push(record(target.identity.uuid,`/${field}`,Object.hasOwn(selected.selected,`/${field}`),selected.selected[`/${field}`],'source',`document_${field}`));
    // PF2e-specific descriptors retain persisted fields. Source mappings never
    // substitute carried gear, prepared statistics, effective usage or Bulk.
    for (const [fields,mapping] of [[selected.physical,'pf2e.physical.source.v1'],[selected.book,'pf2e.book.source.v1'],[selected.kit,'pf2e.kit.source.v1'],[selected.ancestry,'pf2e.ancestry.source.v1'],[selected.background,'pf2e.background.source.v1'],[selected.heritage,'pf2e.heritage.source.v1'],[selected.classSource,'pf2e.class.source.v1'],[selected.deity,'pf2e.deity.source.v1'],[selected.feat,'pf2e.feat.source.v1'],[selected.weapon,'pf2e.weapon.source.v1'],[selected.ammo,'pf2e.ammo.source.v1'],[selected.armor,'pf2e.armor.source.v1'],[selected.container,'pf2e.container.source.v1'],[selected.treasure,'pf2e.treasure.source.v1'],[selected.shield,'pf2e.shield.source.v1'],[selected.equipment,'pf2e.equipment.source.v1'],[selected.consumable,'pf2e.consumable.source.v1'],[selected.spell,'pf2e.spell.source.v1'],[selected.castingEntry,'pf2e.spellcasting-entry.source.v1'],[selected.containedSpell,'pf2e.spell.source.v1'],[selected.action,'pf2e.action.source.v1'],[selected.melee,'pf2e.melee.source.v1'],[selected.lore,'pf2e.lore.source.v1'],[selected.npc,'pf2e.npc.source.v1'],[selected.effect,'pf2e.effect.source.v1'],[selected.condition,'pf2e.condition.source.v1']]) {
    for (const field of fields) {
      const entry=record(target.identity.uuid,field.path,field.present,field.value,'source',field.concept);
      if (Object.hasOwn(field,'mapped_value')) entry.mapped.value=field.mapped_value;
      entry.provenance.mapping=mapping;entry.provenance.limitations=[...field.limitations];records.push(entry);
    }
    }
  }
  if(target.document.documentName==='Actor'&&sections.includes('spellcasting'))records.push(...selected.castingView.records);
  if(target.document.documentName==='Actor'&&sections.includes('inventory'))records.push(...selected.inventoryView.records);
  if (target.document.documentName==='Actor'&&sections.includes('skills')) {
    for (const specialty of selected.specialties) {
      const raw=[['/name',specialty.name],['/type',specialty.type]].map(([path,value])=>({document_uuid:specialty.identity.uuid,path,present:true,value,basis:'source'}));
      records.push({key:`skills:lore:${specialty.identity.uuid}`,section:'skills',kind:'relationship',raw,
        mapped:{concept:'lore_specialty',value:{target_uuid:specialty.identity.uuid,status:'resolved',...(target.token?{token_uuid:target.token.uuid}:{})},unit:null},
        provenance:{contributors:raw.map(({document_uuid,path,basis})=>({document_uuid,path,basis})),mapping:'pf2e.lore.specialty.v1',limitations:['Lore Item reference only; read_item returns owner-aware source, not an effective skill total.']}});
    }
    if (selected.deniedLore.length) records.push({key:'skills:lore:denied',section:'skills',kind:'relationship',raw:[],
      mapped:{concept:'lore_specialty',value:{target_uuid:null,status:'denied'},unit:null},
      provenance:{contributors:[],mapping:'pf2e.lore.specialty.v1',limitations:['One or more owned Lore Items are unreadable; have the authorized GM grant document access and retry.']}});
  }
  for(const [section,{entries,denied}] of Object.entries(selected.npcItemSections)) {
    const concept=section==='strikes'?'npc_attack_item':'npc_ability_item';
    for(const item of entries) {
      const raw=[['/name',item.name],['/type',item.type]].map(([path,value])=>({document_uuid:item.identity.uuid,path,present:true,value,basis:'source'}));
      records.push({key:`${section}:item:${item.identity.uuid}`,section,kind:'relationship',raw,
        mapped:{concept,value:{target_uuid:item.identity.uuid,status:'resolved',...(target.token?{token_uuid:target.token.uuid}:{})},unit:null},
        provenance:{contributors:raw.map(({document_uuid,path,basis})=>({document_uuid,path,basis})),mapping:'pf2e.npc.item-reference.v1',limitations:['Actual owned Item reference only; follow target_uuid with read_item and supplied token_uuid. Not a complete effective attack or ability list.']}});
    }
    if(denied.length)records.push({key:`${section}:items:denied`,section,kind:'relationship',raw:[],
      mapped:{concept,value:{target_uuid:null,status:'denied'},unit:null},
      provenance:{contributors:[],mapping:'pf2e.npc.item-reference.v1',limitations:['One or more owned Items are unreadable; have the authorized GM grant access and retry.']}});
  }
  records.push(...selected.containment.records);
  if(selected.bookRelationships)records.push(...selected.bookRelationships);
  if(selected.kitRelationships)records.push(...selected.kitRelationships);
  if(selected.ancestryRelationships)records.push(...selected.ancestryRelationships);
  if(selected.backgroundRelationships)records.push(...selected.backgroundRelationships);
  if(selected.heritageRelationship)records.push(selected.heritageRelationship);
  if(selected.featRelationships)records.push(...selected.featRelationships);
  if(selected.deityRelationships)records.push(...selected.deityRelationships);
  if(selected.classRelationships)records.push(...selected.classRelationships);
  if(selected.spellRelationship){
    const {path,present,value}=selected.spellReference;
    const raw=[{document_uuid:target.identity.uuid,path,present,...(present?{value}:{}),basis:'source'}];
    records.push({key:'relationships:spell:location',section:'relationships',kind:'relationship',raw,
      mapped:{concept:'stored_spellcasting_entry_reference',value:selected.spellRelationship,unit:null},
      provenance:{contributors:raw.map(({document_uuid,path,basis})=>({document_uuid,path,basis})),mapping:'pf2e.spell.casting-entry.v1',limitations:['stored_assignment_not_castability']}});
  }
  if(selected.weaponRelationship){
    const {path,present,value}=selected.weaponReference;
    const raw=[{document_uuid:target.identity.uuid,path,present,...(present?{value}:{}),basis:'source'}];
    records.push({key:'relationships:weapon:selectedAmmoId',section:'relationships',kind:'relationship',raw,
      mapped:{concept:'stored_selected_ammunition_reference',value:selected.weaponRelationship,unit:null},
      provenance:{contributors:raw.map(({document_uuid,path,basis})=>({document_uuid,path,basis})),mapping:'pf2e.weapon.selected-ammo.v1',limitations:['Stored selection only; not loaded ammunition, compatibility, usability, quantity or a final Strike. No target source or prepared ammunition getter is read.']}});
  }
  if(selected.conditionRelationships)for(const reference of selected.conditionRelationships){
    const raw=reference.raw.map(({path,present,value})=>({document_uuid:target.identity.uuid,path,present,...(present?{value}:{}),basis:'source'}));
    records.push({key:`relationships:condition:${reference.path}`,section:'relationships',kind:'relationship',raw,
      mapped:{concept:reference.concept,value:reference.result,unit:null},
      provenance:{contributors:raw.map(({document_uuid,path,basis})=>({document_uuid,path,basis})),mapping:'pf2e.condition.reference.v1',limitations:['Stored local reference or override slug only; no active/suppressed state or persistent-damage dominance is inferred. Unresolved targets disclose no resolved metadata.']}});
  }
  if(selected.effectRelationships){
    const raw=selected.effectReferences.map(({path,present,value})=>({document_uuid:target.identity.uuid,path,present,...(present?{value}:{}),basis:'source'}));
    for(const reference of selected.effectRelationships)records.push({key:`relationships:effect:${reference.role}`,section:'relationships',kind:'relationship',raw,
      mapped:{concept:`effect_${reference.role}_reference`,value:reference.result,unit:null},
      provenance:{contributors:raw.map(({document_uuid,path,basis})=>({document_uuid,path,basis})),mapping:'pf2e.effect.context-reference.v1',limitations:['Immediate stored context only; no acquired ability, learned spell, current application or recursive provenance is inferred. Unresolved targets disclose no identity.']}});
  }
  if (target.document.type==='melee'&&sections.includes('relationships')) {
    for (const field of selected.melee.filter(entry=>entry.path.startsWith('/system/attackEffects/value'))) {
      const indexed=field.path.startsWith('/system/attackEffects/value/');
      const entry=record(target.identity.uuid,field.path,field.present,field.value,'relationships','additional_effect');
      entry.kind='relationship';entry.key=`relationships:attackEffects${indexed?`:${field.path.split('/').at(-1)}`:''}`;
      entry.mapped.value={target_uuid:null,status:indexed?'unverified':'missing'};
      entry.provenance.mapping='pf2e.melee.attack_effect.v1';
      entry.provenance.limitations=indexed?['Stored additional-effect label is not a UUID; discover its definition separately.']:['No stored additional-effect labels; source presence distinguishes an absent array from an empty array.'];
      records.push(entry);
    }
  }
  if (selected.relationship) {
    const paths=['/system/selfEffect/uuid','/system/selfEffect/name'];
    const raw=paths.map(path=>{const field=selected.action.find(entry=>entry.path===path);return {document_uuid:target.identity.uuid,path,present:field?.present===true,...(field?.present?{value:field.value}:{}),basis:'source'};});
    records.push({key:'relationships:selfEffect',section:'relationships',kind:'relationship',raw,
      mapped:{concept:'self_effect',value:{target_uuid:selected.relationship.target_uuid,status:selected.relationship.status,...(selected.relationship.token_uuid?{token_uuid:selected.relationship.token_uuid}:{})},unit:null},
      provenance:{contributors:raw.map(({document_uuid,path,basis})=>({document_uuid,path,basis})),mapping:'pf2e.action.self_effect.v1',limitations:selected.relationship.reason?[selected.relationship.reason]:[]}});
  }
  if (sections.includes('description')) {
    let fields=target.document.documentName==='Actor'?selected.npcNotes:target.document.type==='spell'?selected.spellDescriptions:
      ['/system/description/value',...(PHYSICAL_TYPES.includes(target.document.type)?['/system/identification/unidentified/data/description/value']:[])].map(path=>({path,present:Object.hasOwn(selected.selected,path),value:selected.selected[path],concept:path==='/system/description/value'?'description':'unidentified_description'}));
    if(target.document.documentName==='Item'&&target.document.type==='consumable')fields.push(...selected.containedDescriptions);
    for (const field of fields) {
      const {path,present,value,concept}=field;
      if (present && typeof value!=='string') fail('ReadFailed','Stored description has an unexpected type.','Inspect the selected document source in Foundry.');
      const make=(present,value)=>{
        const entry=record(target.identity.uuid,path,present,value,'description',concept);
        if(target.document.documentName==='Item'&&(target.document.type==='spell'||(target.document.type==='consumable'&&path.startsWith('/system/spell/system/')))){entry.provenance.mapping='pf2e.spell.source.v1';entry.provenance.limitations=['source_only_no_spell_casting_or_variant_application'];}
        if(target.document.documentName==='Actor') {
          entry.provenance.mapping='pf2e.npc.notes.v1';
          entry.provenance.limitations=['Exact stored NPC biography; public and GM-private notes remain separate source paths. No enrichment is executed.'];
        }
        return entry;
      };
      if (present) for (const [index,fragment] of textFragments(value).entries()) {
        const entry=make(true,fragment.value);
        entry.kind='text';entry.key+=`:${index}`;entry.mapped.value=null;entry.text={path,...fragment.text};records.push(entry);
      }
      else records.push(make(false,null));
    }
  }
  const isAction=target.document.documentName==='Item'&&target.document.type==='action';
  const isMelee=target.document.documentName==='Item'&&target.document.type==='melee';
  const isLore=target.document.documentName==='Item'&&target.document.type==='lore';
  const isTreasure=target.document.documentName==='Item'&&target.document.type==='treasure';
  const isBook=target.document.documentName==='Item'&&target.document.type==='book';
  const isKit=target.document.documentName==='Item'&&target.document.type==='kit';
  const isAncestry=target.document.documentName==='Item'&&target.document.type==='ancestry';
  const isBackground=target.document.documentName==='Item'&&target.document.type==='background';
  const isHeritage=target.document.documentName==='Item'&&target.document.type==='heritage';
  const isFeat=target.document.documentName==='Item'&&target.document.type==='feat';
  const isDeity=target.document.documentName==='Item'&&target.document.type==='deity';
  const isClass=target.document.documentName==='Item'&&target.document.type==='class';
  const isContainer=target.document.documentName==='Item'&&target.document.type==='backpack';
  const isCastingEntry=target.document.documentName==='Item'&&target.document.type==='spellcastingEntry';
  const isSpell=target.document.documentName==='Item'&&target.document.type==='spell';
  const isConsumable=target.document.documentName==='Item'&&target.document.type==='consumable';
  const isEquipment=target.document.documentName==='Item'&&target.document.type==='equipment';
  const isShield=target.document.documentName==='Item'&&target.document.type==='shield';
  const isArmor=target.document.documentName==='Item'&&target.document.type==='armor';
  const isAmmo=target.document.documentName==='Item'&&target.document.type==='ammo';
  const isWeapon=target.document.documentName==='Item'&&target.document.type==='weapon';
  const isCondition=target.document.documentName==='Item'&&target.document.type==='condition';
  const isEffect=target.document.documentName==='Item'&&target.document.type==='effect';
  const castingSection=target.document.documentName==='Actor'&&sections.includes('spellcasting');
  const inventorySection=target.document.documentName==='Actor'&&sections.includes('inventory');
  const loreSkills=target.document.documentName==='Actor'&&sections.includes('skills');
  const complete=name=>(isFeat&&['source','relationships'].includes(name))||(isDeity&&['source','relationships'].includes(name))||(isClass&&['source','relationships'].includes(name))||(isHeritage&&['source','relationships'].includes(name))||(isBackground&&['source','relationships'].includes(name))||(isAncestry&&['source','relationships'].includes(name))||(isKit&&['source','relationships'].includes(name))||(isBook&&['source','relationships'].includes(name))||(inventorySection&&name==='inventory'&&!selected.inventoryView.reasons.length)||(isContainer&&(name==='source'||(name==='relationships'&&!selected.containment.reasons.length)))||(isCastingEntry&&name==='source'&&!selected.castingIssues.length)||name==='identity'||(name==='description'&&(target.document.documentName==='Item'||target.document.type==='npc'))||((isLore||isAmmo||isArmor||isShield||isEquipment||isConsumable||isTreasure)&&name==='source')||((isEffect||isCondition||isWeapon||isSpell)&&['source','relationships'].includes(name))||((isAction||isMelee)&&['source','relationships'].includes(name));
  const base={contract_version:1,runtime:selected.runtime,identity:target.identity,revision,
    sections:sections.map(name=>({name,status:complete(name)?'complete':(isContainer&&name==='relationships')||name==='source'||(castingSection&&name==='spellcasting')||(inventorySection&&name==='inventory')||Object.hasOwn(selected.npcItemSections,name)||(loreSkills&&name==='skills')?'partial':'unsupported',
      reasons:complete(name)?[]:inventorySection&&name==='inventory'?selected.inventoryView.reasons:isContainer&&name==='relationships'?selected.containment.reasons:castingSection&&name==='spellcasting'?selected.castingView.reasons:Object.hasOwn(selected.npcItemSections,name)?[name==='strikes'?'other_attacks_pending':'other_abilities_pending',...(selected.npcItemSections[name].denied.length?['related_items_denied']:[])]:loreSkills&&name==='skills'?['other_skills_pending',...(selected.deniedLore.length?['related_items_denied']:[])]:name==='source'?(isCastingEntry?[...new Set(selected.castingIssues.map(issue=>issue.reason))]:[PENDING]):['section_not_implemented']})),limitations:[target.document.documentName==='Actor'&&target.document.type==='npc'?'Authored NPC source fields only; biography requires explicit description; integrated sections remain pending. Elite/weak and effective/current statistics are not calculated.':(isFeat||isDeity||isClass||isHeritage||isBackground||isAncestry||isKit||isBook)?'Selected source and explicit immediate definition links only; effective Actor statistics, acquired contributions and gameplay execution remain unsupported.':isTreasure?'Stored treasure category, quantity and denomination price/per basis only. Valuables on supported Actors remain readable despite loot-Actor exclusion. No coin conversion, doubled stack value, sale proceeds, usage or investment state is inferred.':isContainer?'Stored container Bulk and containment claims only; capacity is not current contents Bulk, ignored Bulk is conditional and no Actor total is calculated. Explicit relationships use actual owner scope, retain each descendant once and report cycles or unresolved parents.':isCastingEntry?'Stored casting mode, proficiency, attack/DC and per-slot/preparation source only. Prepared slot value zero does not establish exhaustion; repeated preparations stay separate. Focus pools and innate uses are not inferred from slot counters. No final PC statistics, usable casts or resource expenditure is calculated.':isSpell?'Stored spell definition and base rank only; authored heightening, overlays and location resource configuration are not evaluated cast options or proof of castability. Explicit relationships follow only the immediate assigned entry.':isConsumable?'Stored consumable stock, uses and damage/healing plus contained spell definitions only. Nested spells retain source-path identity on this Item; no independent spell UUID, consumption, frequency expenditure, castability or effective benefits are inferred.':isEquipment?'Stored equipment usage, investment and metadata only; read description for prose activation, frequency and constant benefits. Uninvested does not erase mundane uses; magical benefits are not assumed active.':isShield?'Stored shield properties and durability only; held is not raised, possession does not grant Shield Block, and source reinforcing runes are not class-granted effective reinforcement.':isArmor?'Stored armor properties and carrying/investment configuration only; armor bonus is not total AC and no worn rune benefits, actor saves or Speed are calculated.':isAmmo?'Stored ammunition stock/use configuration only; counts and categories do not prove compatibility or a usable attack, and carried effects are not automatically applied.':isWeapon?'Persisted weapon definition and configuration only; carry state is not proof of wielding/usability. No final Strike, NPC authored attack or alternate-use result is calculated.':isCondition?'Stored condition source only; presence and override references do not establish active or suppressed state. Persistent damage formulas are not rolled and dominance is not calculated.':isEffect?'Persisted effect source only; formulas are not evaluated, origins are not acquired spells/abilities. Immediate context relationships require explicit selection; expiry/current application remains unsupported.':isLore?'Selected Lore source uses actual owner type; no effective check total or proficiency bonus is calculated.':isMelee?'Authored NPC attack source and named effect labels only; no effective elite/weak/MAP/target calculation or weapon substitution.':isAction?'Selected action source and immediate self-effect reference only; no current usability or effective benefits are claimed.':loreSkills?'Skills currently includes only actual Lore Item references; other Skills and all effective totals remain pending.':'Type-specific system fields and effective mappings are pending their stories.']};
  if(isClass)base.limitations.push('Stored class key-attribute options/selections, HP contribution, starting proficiency ranks and progression only. Ranks are not bonuses or totals; future feature references are not acquired abilities. No advancement, HP recomputation or automatic grants occur.');
  if(isHeritage)base.limitations.push('Stored heritage identity and nullable ancestry association only. Null association does not establish exclusivity or owner membership; named ancestry links are definitions, not proof of current ancestry. Read exact description for benefits; no eligibility or effective benefits are evaluated.');
  if(isBackground)base.limitations.push('Stored background offers/selections, skill codes, Lore labels and feature definitions only. Definition references are not acquired grants; Lore labels are not Item UUIDs. Empty structured training or feature entries do not prove no benefit; read description for choices and exceptions. No duplicate-training resolution, missing feat/Lore creation or effective Actor totals occur. Acquired multi-contributor joins remain CORE-build work.');
  if(isAncestry)base.limitations.push('Stored ancestry offers, selected/alternate/voluntary choices and source HP, size, movement, senses, language and feature contributions only. A null stored selection is not an unused fixed boost. Feature references do not prove acquisition; no final character statistics or automatic grants are evaluated.');
  if(isKit)base.limitations.push('Serialized bundle definition and explicit immediate component links only. Nested entry keys remain source paths, not document identities or additional owned possessions. No kit import, component multiplication, recursive target expansion or inventory mutation occurs.');
  if(isBook)base.limitations.push('Book category, capacity and stored content UUIDs only. Explicit relationships resolve immediate identities, preserving duplicate indexes. Referenced content is not formula ownership, a prepared spell or castability. No recursive expansion; representative live book fixtures are unavailable.');
  if(inventorySection)base.limitations.push('Stored possessions and same-owner containment/ammunition claims only. Each owned physical Item appears once; serialized attachments and kit definitions are separate. No total Bulk, sale proceeds, effective benefits or activation eligibility is calculated. Follow read_item for concrete source and exact activation prose.');
  if(castingSection)base.limitations.push('Actor casting is a source join only. Availability remains not_evaluated; ritual, flexible and item-casting semantics remain partial. Follow canonical group/spell selectors with read_item for exact definition/prose.');
  if(isCastingEntry)base.limitations.push(...selected.castingIssues.map(issue=>`Uninterpreted casting source at ${issue.path}: ${issue.reason}.`));
  const result=await paginate(records,base,params,{tool,actor_uuid:params.actor_uuid??null,item_uuid:params.item_uuid??null,token_uuid:params.token_uuid??null,sections});
  // Recheck permission, resolution, identity and selected snapshot after await points.
  const fresh=tool==='read_actor'?await actorTarget(params):await itemTarget(params);
  if (await digest(await snapshot(fresh,sections))!==revision) fail('ContentChanged','Selected data changed during the read.','Discard accumulated pages and restart without cursor.');
  return result;
}

/** PF2e-specific character/npc/familiar admission; only source metadata here. */
export async function readActor(params={}) {
  const sections=bounds(params,['actor_uuid','token_uuid','sections','limit','max_bytes','cursor'],ACTOR_SECTIONS);ready();
  return read(await actorTarget(params),params,sections,'read_actor');
}

/** PF2e-specific 8.6.1 Item boundary; selected source and explicit relationships,
 * never prepared/effective math. Schema contracts live in imported type helpers. */
export async function readItem(params={}) {
  const sections=bounds(params,['item_uuid','token_uuid','sections','limit','max_bytes','cursor'],ITEM_SECTIONS);ready();
  return read(await itemTarget(params),params,sections,'read_item');
}

/**
 * PF2e-specific embedded Item boundary for the 24 in-scope source types on
 * character/npc/familiar Actors. Source relationships beyond canonical parent
 * identity remain pending; do not infer complete actions or acquired benefits.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/static/template.json
 */
export async function listActorItems(params={}) {
  bounds(params,['actor_uuid','token_uuid','types','query','limit','max_bytes','cursor']);ready();
  let types=ITEM_TYPES;
  if (params.types!==undefined && params.types!==null) {
    if (!Array.isArray(params.types)||!params.types.length||params.types.length>ITEM_TYPES.length||new Set(params.types).size!==params.types.length||params.types.some(type=>!ITEM_TYPES.includes(type))) fail('InvalidRequest','types must be a nonempty unique list of in-scope Item types.');
    types=params.types;
  }
  let query='';
  if (params.query!==undefined && params.query!==null) {
    if (typeof params.query!=='string'||!params.query.trim()||[...params.query.trim()].length>200) fail('InvalidRequest','query must contain 1–200 characters after trim.');
    query=params.query.trim().toLowerCase();
  }
  const build=async()=>{
    const owner=await actorTarget(params); const nodes=[];let unsupported_count=0;
    for (const item of owner.document.items.values()) {
      if (!ITEM_TYPES.includes(item.type)||item.type==='affliction') {unsupported_count++;continue;}
      if (!types.includes(item.type)||!String(item.name).toLowerCase().includes(query)) continue;
      const identity=embeddedIdentity(item,owner);
      nodes.push({kind:'item',identity,parent_uuid:owner.document.uuid,relationships:[],next_call:{tool:'read_item',arguments:{item_uuid:identity.uuid,...(owner.token?{token_uuid:owner.token.uuid}:{})}}});
    }
    const compare=(a,b)=>a<b?-1:a>b?1:0;
    nodes.sort((a,b)=>compare(a.identity.type,b.identity.type)||compare(a.identity.name.toLowerCase(),b.identity.name.toLowerCase())||compare(a.identity.uuid,b.identity.uuid));
    return {owner:owner.identity,nodes,unsupported_count,runtime:runtime()};
  };
  const snapshot=await build();const revision=await digest(snapshot);
  const base={contract_version:1,runtime:snapshot.runtime,revision,scopes:[{id:snapshot.owner.uuid,status:'searched',reason:null}],unsupported_count:snapshot.unsupported_count,limitations:['Embedded Items do not enumerate all possible actions.']};
  const result=await paginate(snapshot.nodes,base,params,{tool:'list_actor_items',actor_uuid:params.actor_uuid??null,token_uuid:params.token_uuid??null,types,query});
  if (await digest(await build())!==revision) fail('ContentChanged','Owned Item membership or identity changed.','Restart list_actor_items without cursor.');
  const {records,...rest}=result;return {...rest,nodes:records};
}
