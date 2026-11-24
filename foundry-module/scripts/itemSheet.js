/** PF2e-specific physical Item forms and edits, qualified on Foundry 14.370/PF2e 8.7.0.
 * https://github.com/foundryvtt/pf2e/tree/52dfeee703b887237f5e454747bcae45b136f9af/src/module/item
 * Public Document.toObject(true/false), name and exact owner membership. Never prepare a sheet.
 */
import {digest, fail, integer, paginate, textFragments, validateParams} from './actorReadUtils.js';
import {sheetTarget} from './itemSheetTarget.js';
import {children, choices, controls, definition, get, groupIds, groupLabel, isCommon, label} from './itemSheetFields.js';
import {capacity, classificationIssue, equal, proposal, sorted, unavailable, variant} from './itemSheetProposal.js';

const propertyId = 'material_and_runes.property_runes';
const pageKeys = ['item_uuid','token_uuid','limit','max_bytes','cursor'];
const selectors = params => ({item_uuid:params.item_uuid,...(params.token_uuid ? {token_uuid:params.token_uuid} : {})});
const locale = () => game.i18n.lang;

/** PF2e-specific 8.7.0 detached physical Item context. No derived field is used for persistence. */
async function context(params) {
  const target = await sheetTarget(params);
  return {target, source:target.document.toObject(true), current:target.document.toObject(false),
    variant:variant(target), world:game.world.id, user:game.user.id, locale:locale()};
}

function bounds(params) {
  return {...params,limit:integer(params.limit,10,1,100,'limit'),max_bytes:integer(params.max_bytes,8000,8000,48000,'max_bytes')};
}

async function page(ctx,params,scope,metadata,records) {
  const identity = ctx.target.identity;
  const revision = await digest(sorted([ctx.world, ctx.user, identity, ctx.source,ctx.locale,metadata,records]));
  return paginate(records,{...metadata, runtime:ctx.target.runtime,identity,revision},bounds(params),
    {world:ctx.world, user:ctx.user,locale:ctx.locale,...selectors(params),...scope});
}

/** PF2e-specific 8.7.0 single-control option lookup on current or prospective source state. */
export async function getItemFieldOptions(params={}) {
  validateParams(params,[...pageKeys,'field','slot','query','proposed_changes']);
  const {field,slot,query} = params;
  if (typeof field !== 'string') fail('InvalidRequest','Supply a qualified sheet field.');
  const [,fallback,,kind] = definition(field);
  if (field === propertyId) integer(slot,undefined,1,5,'slot');
  else if (slot !== undefined) fail('InvalidRequest','slot applies only to property_runes.');
  if (query !== undefined && (typeof query !== 'string' || !query.length || query.length>200)) fail('InvalidRequest','query needs 1–200 characters.');
  const ctx = await context(params);
  const sys = params.proposed_changes ? (await proposal(ctx,params.proposed_changes)).after.system : ctx.source.system;
  const reason = unavailable(ctx,field,sys,slot);
  let domain = choices(kind,sys);
  if (kind === 'material') {
    domain = [[null,'None']];
    for (const [type,material] of choices('materialType',sys).filter(([v])=>v!==null)) {
      for (const [grade,text] of choices('grade',{...sys,material:{type}}).filter(([v])=>v!==null)) {
        domain.push([{type,grade},material+' ('+text+')']);
      }
    }
  }
  const needle = query?.toLocaleLowerCase(ctx.locale);
  const records = (domain??[]).filter(([value,name]) => !needle ||
    (JSON.stringify(value)+' '+name).toLocaleLowerCase(ctx.locale).includes(needle))
    .map(([value,label])=>{
      const occupied=sys.runes?.property??[];
      // PF2e-specific ordered source slots cannot introduce a duplicate or leave a hole.
      let blocked=kind==='property' && (value===null?occupied.length>slot:occupied.some((v,i)=>i!==slot-1 && v===value));
      if (['potency','material','materialType'].includes(kind)) {
        const candidate=kind==='potency' ? {...sys,runes:{...sys.runes,potency:value}} :
          {...sys,material:kind==='materialType'?{...sys.material,type:value}:value};
        const slots=capacity(candidate,ctx);
        blocked=slots===null || occupied.length>slots;
      }
      if (['weaponGroups','range','weaponTraits'].includes(kind)) {
        const candidate={...sys};
        if (kind==='weaponGroups') candidate.group=value;
        if (kind==='range') candidate.range=value;
        if (kind==='weaponTraits') candidate.traits={...sys.traits,value:[...new Set([...(sys.traits?.value??[]),value])]};
        blocked=Boolean(classificationIssue(ctx.source.system,candidate));
      }
      if (kind==='hands' && value!=='held-in-one-hand' && sys.traits?.otherTags?.includes('implement')) blocked=true;
      return {value,label,available:!reason && !blocked};
    });
  const why = reason ?? (domain === null ? fallback+' uses typed input. Inspect edit_item or select a compound leaf.' : null);
  return page(ctx,params,{field,slot,query,proposal:sorted(params.proposed_changes??{})},
    {field,label:label(field,slot),available:!why,...(why ? {reason:why} : {})},records);
}

/** PF2e-specific select only semantic leaves of the source or transformed weapon schema.
 * A null damage/material record differs from a missing leaf. Price retains its per-quantity basis.
 */
function fieldValue(data,id) {
  const [path,,,kind] = definition(id);
  const raw = get(data,path);
  if (raw == null) return raw;
  if (kind === 'boolean' && id.endsWith('specific_magic_weapon')) return true;
  if (!Object.hasOwn(children,id)) return raw;
  const leaves = {};
  for (const [name,[p]] of Object.entries(children[id])) {
    const value = get(raw,p);
    if (value !== undefined) leaves[name] = value;
  }
  if (kind === 'price' && Object.hasOwn(raw,'per')) leaves.per = raw.per;
  return leaves;
}

/** PF2e-specific physical Item applicability and weapon sheet order for requested source fields. */
function selectedIds(sheet,type) {
  validateParams(sheet,['groups','fields']);
  const {groups=[],fields=[]} = sheet;
  for (const [values,max] of [[groups,9],[fields,64]]) {
    if (!Array.isArray(values) || values.length>max || new Set(values).size!==values.length ||
        values.some(v=>typeof v!=='string')) fail('InvalidRequest','Use distinct sheet groups and qualified fields.');
  }
  if (groups.some(g=>!groupIds.includes(g))) fail('InvalidRequest','Unknown sheet group.');
  for (const id of fields) {
    definition(id);
    if (groups.length && !groups.includes(id.split('.')[0])) fail('InvalidRequest','Field outside selected groups.');
  }
  const unsupported = new Set();
  const selected = [];
  for (const parent of Object.keys(controls)) {
    const group = parent.split('.')[0];
    if (groups.length && !groups.includes(group)) continue;
    const filtered = fields.filter(id=>id===parent||id.startsWith(parent+'.'));
    if (fields.length && !filtered.length) continue;
    if (!groups.length && !fields.length && definition(parent)[3]==='text') continue;
    if (type !== 'weapon' && !isCommon(parent)) {
      if (!Object.keys(controls).some(id=>id.startsWith(group+'.') && isCommon(id)) || filtered.length) unsupported.add(group);
      continue;
    }
    selected.push(...(filtered.length ? filtered : [parent]));
  }
  return {selected,unsupported_groups:[...unsupported]};
}

/** PF2e-specific GM controls. Transformed serialization is a display witness when present.
 * Repeated slots separate authored and granted values. Display name comes from public Item.name.
 */
function controlRecords(ctx,params,id) {
  const sys = ctx.source.system;
  const [, , ,kind] = definition(id);
  let source = fieldValue(ctx.source,id);
  let display = fieldValue(ctx.current,id);
  if (id === 'header.display_name') { source=undefined; display=ctx.target.document.name; }
  if (id === 'header.name') display=source; // GM's stored name input; the sheet title is a separate control.
  if (id.endsWith('specific_magic_weapon')) {
    if (source === null) source=false;
    if (display === null) display=false;
  }
  const group = id.split('.')[0];
  const lookup = slot => ({tool:'get_item_field_options',arguments:{...selectors(params),field:id,...(slot?{slot}:{})}});
  const make = (value,presentation,slot) => {
    const reason = unavailable(ctx,id,sys,slot);
    const domain = choices(kind,sys);
    const hasDisplay = presentation!==undefined;
    const row = {group,group_label:groupLabel(group),field:id,label:label(id,slot),present:value!==undefined,...(value!==undefined?{source:value}:{}),
      editable:!reason,...(reason?{reason}:{}),display_basis:!hasDisplay?'unavailable':id==='header.display_name'?'document':
        id==='header.name'?'source':'transformed',
      ...(hasDisplay?{display:presentation}:{display_reason:'No transformed value available for this control.'})};
    if (slot) {
      row.slot=slot;
      row.slot_state=presentation!=null && presentation!==value?'derived':value!=null?'occupied':'free';
    }
    if (domain || kind==='material') row.options=lookup(slot);
    if (domain && hasDisplay) {
      const text = v=>domain.find(([value])=>value===v)?.[1] ?? String(v);
      row.display_label=Array.isArray(presentation)?presentation.map(text).join(', '):text(presentation);
    }
    return row;
  };
  if (id === propertyId) {
    const max = Math.max(sys.specific ? 0 : capacity(sys,ctx)??0,source?.length??0,display?.length??0);
    if (max>100) fail('ReadFailed','Rune slot count exceeds 100. Inspect the source with read_item.');
    if (!max) return [{...make(source,display),options:undefined,editable:false,reason:'No property rune slots are available.'}];
    return Array.from({length:max},(_,i)=>make(source?.[i],display?.[i],i+1));
  }
  if (kind === 'text' && (typeof source==='string'||typeof display==='string')) {
    // Each stream carries its own exact offsets. Differences can span additional pages.
    const sourceParts=typeof source==='string'?textFragments(source):[];
    const displayParts=typeof display==='string'?textFragments(display):[];
    return Array.from({length:Math.max(sourceParts.length,displayParts.length)},(_,i)=>{
      const a=sourceParts[i], b=displayParts[i];
      const row=make(a?.value??(i===0?source:undefined),b?.value??(i===0?display:undefined));
      if (a) row.text=a.text;
      if (b) row.display_text=b.text;
      return row;
    });
  }
  const row=make(source,display);
  if (id==='material_and_runes.specific_magic_weapon' && Object.hasOwn(sys,'specific')) {
    const snapshot=sys.specific;
    row.specific_baseline=snapshot===null ? null : {
      material:{type:snapshot.material?.type,grade:snapshot.material?.grade},
      runes:{potency:snapshot.runes?.potency,striking:snapshot.runes?.striking,property:snapshot.runes?.property},
    };
  }
  if (children[id]) {
    row.choice_fields=Object.keys(children[id]).map(leaf=>id+'.'+leaf)
      .filter(key=>choices(definition(key)[3],sys)!==null);
  }
  return [row];
}

/** PF2e-specific 8.7.0 selective physical Item form. Page by fields, slots and exact prose fragments. */
export async function readItemSheet(params={}) {
  validateParams(params,[...pageKeys,'sheet']);
  const ctx = await context(params);
  const {selected,unsupported_groups} = selectedIds(params.sheet,ctx.target.document.type);
  const records = selected.flatMap(id=>controlRecords(ctx,params,id));
  return page(ctx,params,{sheet:params.sheet},{contract_version:3,unsupported_groups},records);
}

const locks = new Map();
const encodedSize = value => new TextEncoder().encode(JSON.stringify(value)).length;
function excerpt(value) {
  if (typeof value !== 'string') return {value:value??null,short:false};
  const chars = [...value];
  return {value:chars.slice(0,180).join(''),short:chars.length>180};
}
/** PF2e-specific 8.7.0 choice evidence for the proposed weapon source fields. */
function domainWitness(sys,fields) {
  return fields.flatMap(id=>{
    const ids = Object.hasOwn(children,id) ? Object.keys(children[id]).map(k=>id+'.'+k) : [id];
    return ids.map(key=>[key,choices(definition(key)[3],sys)]);
  });
}
/** PF2e-specific physical Item preview. Bind source, choice and transformed capacity dependencies. */
async function prepare(params) {
  const ctx = await context(params);
  if (ctx.target.reason) fail('TargetUnavailable',ctx.target.reason,'Rediscover an editable world or inventory Item.');
  const change = await proposal(ctx,params.changes);
  const {fields,after} = change;
  const domains=domainWitness(after.system,fields);
  const revision = await digest(sorted([ctx.world,ctx.user,ctx.locale,ctx.target.identity,ctx.source,
    ctx.variant,ctx.current.system?.runes,ctx.current.system?.material,ctx.current.system?.grade,domains,params.changes]));
  const changes = fields.map(id=>{
    const old = fieldValue(ctx.source,id), proposed = fieldValue(after,id);
    const before=excerpt(old), next=excerpt(proposed);
    return {field:id,label:label(id),present:old!==undefined,before:before.value,after:next.value,excerpt:before.short||next.short};
  });
  const receipt = {status:'preview',identity:ctx.target.identity,revision,changes,
    next_call:{tool:'read_item',arguments:{...selectors(params),sheet:{fields}}}};
  if (encodedSize({...receipt,status:'unchanged'})>8000) fail('ResponseTooLarge','Edit receipt exceeds 8000 bytes.','Split the proposal into smaller independently valid edits.');
  return {ctx,...change,domains,receipt};
}

/** PF2e-specific 8.7.0 authoring via public Item.update / Actor.updateEmbeddedDocuments.
 * Optimistic concurrency is serialized per local owner. External Foundry clients may write
 * after the last comparison. Verify selected persisted paths, never replay a dispatched update.
 * https://foundryvtt.com/api/v14/classes/foundry.abstract.Document.html
 */
export async function editItem(params={},isCurrent=()=>true) {
  validateParams(params,['item_uuid','token_uuid','changes','mode','expected_revision']);
  const mode=params.mode===undefined?'preview':params.mode;
  if (!['preview','apply'].includes(mode) || (mode==='apply')!==Object.hasOwn(params,'expected_revision') ||
      (mode==='apply' && (typeof params.expected_revision!=='string'||!params.expected_revision.length||params.expected_revision.length>512))) {
    fail('InvalidRequest','Preview first. Apply requires its expected_revision.');
  }
  const initial=await sheetTarget(params);
  if (initial.reason) fail('TargetUnavailable',initial.reason);
  const key=JSON.stringify([game.world.id,initial.actor?.uuid ?? initial.document.uuid]);
  const prior=locks.get(key);
  let unlock;
  const lock=new Promise(resolve=>{unlock=resolve;});
  locks.set(key,lock);
  try {
    if (prior) await prior;
    const {ctx,patch,receipt,domains,after,fields}=await prepare(params);
    if (mode==='preview') return receipt;
    if (receipt.revision!==params.expected_revision) fail('ContentChanged','Target, choices or proposal changed.','Read the Item and preview again.');
    const target=await sheetTarget(params);
    const item=target.document, actor=target.actor;
    const current=item.toObject(false).system;
    if (!isCurrent() || ctx.world!==game.world.id || ctx.user!==game.user.id || target.reason ||
        item!==ctx.target.document || actor!==ctx.target.actor || !equal(ctx.source,item.toObject(true)) ||
        ctx.locale!==locale() || !equal(domains,domainWitness(after.system,fields)) ||
        !equal(ctx.current.system?.runes,current?.runes) || !equal(ctx.current.system?.material,current?.material) ||
        ctx.current.system?.grade!==current?.grade ||
        !equal(ctx.variant,variant(target)) || !item.canUserModify(game.user,'update',patch) ||
        (actor && !actor.canUserModify(game.user,'update'))) {
      fail('ContentChanged','Target or permission changed during validation.','Read the Item and preview again.');
    }
    if (!Object.keys(patch).length) return {...receipt,status:'unchanged'};
    try {
      const updated = actor ? await actor.updateEmbeddedDocuments('Item',[{_id:item.id,...patch}]) : await item.update(patch);
      if (actor ? updated?.length!==1 || updated[0]?.uuid!==item.uuid : updated?.uuid!==item.uuid) throw Error('unconfirmed');
      const fresh=await sheetTarget(params);
      if (fresh.reason || ctx.world!==game.world.id || ctx.user!==game.user.id || !isCurrent()) throw Error('context');
      const persisted=fresh.document.toObject(true);
      if (!Object.entries(patch).every(([path,value])=>equal(get(persisted,path),value))) throw Error('unverified');
      return {...receipt,status:'applied'};
    } catch {
      fail('WriteOutcomeUnknown','The update was dispatched and persisted fields could not be confirmed.',
        'Read the Item with the original selectors and requested sheet fields before another preview or apply.');
    }
  } finally {
    unlock();
    if (locks.get(key)===lock) locks.delete(key);
  }
}
