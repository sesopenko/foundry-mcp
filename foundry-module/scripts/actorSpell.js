/**
 * PF2e-specific SpellSystemSource selector, 8.6.1 only; detached source, never
 * prepared variants, cast ranks or evaluated formulas. Schema contract:
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/spell/data.ts
 */
const LIMIT=['source_only_no_spell_casting_or_variant_application'];
/** PF2e-specific spell primitive source descriptor; no derived values. */
const leaf=(type,concept,nullable=false)=>({type,concept:'spell_'+concept,nullable});
/** PF2e-specific spell stored string descriptor; no parsing or enrichment. */
const str=(name,nullable=false)=>leaf('string',name,nullable);
/** PF2e-specific spell stored numeric descriptor; no cast calculations. */
const num=name=>leaf('number',name);
/** PF2e-specific spell stored boolean descriptor; no availability inference. */
const bool=name=>leaf('boolean',name);
/** PF2e-specific spell ordered source code-list descriptor. */
const list=(concept)=>({array:str(concept),concept:'spell_'+concept});
/** PF2e-specific spell explicit schema-object descriptor; no arbitrary object dumps. */
const object=(children,concept,nullable=false)=>({children,concept:'spell_'+concept,nullable});
/** PF2e-specific spell keyed source-component descriptor; keys retain source identity. */
const record=(entry,concept)=>({record:entry,concept:'spell_'+concept});
const damage=object({formula:str('damage_formula'),kinds:list('damage_kind_code'),applyMod:bool('damage_apply_mod'),type:str('damage_type_code'),category:str('damage_category_code',true),materials:list('damage_material_code')},'damage_component');
const schema={
 level:object({value:num('base_rank')},'level'),
 traits:object({traditions:list('tradition_code'),value:list('trait_code'),otherTags:list('other_tag_code'),rarity:str('rarity_code')},'traits'),
 time:object({value:str('casting_time_text')},'time'),requirements:str('requirements_text'),
 cost:object({value:str('cost_text')},'cost'),range:object({value:str('range_text')},'range'),target:object({value:str('target_text')},'target'),
 area:object({type:str('area_shape_code'),value:num('area_value'),details:str('area_details_text')},'area',true),
 duration:object({value:str('duration_text'),sustained:bool('duration_sustained')},'duration'),
 damage:record(damage,'damage_components'),
 defense:object({passive:object({statistic:str('passive_defense_statistic_code')},'passive_defense',true),save:object({statistic:str('save_statistic_code'),basic:bool('save_basic')},'save',true)},'defense',true),
 counteraction:bool('counteraction'),
 ritual:object({primary:object({check:str('ritual_primary_check_text')},'ritual_primary'),secondary:object({checks:str('ritual_secondary_checks_text'),casters:num('ritual_secondary_casters')},'ritual_secondary')},'ritual',true),
 location:object({value:str('casting_entry_local_id',true),signature:bool('signature'),heightenedLevel:num('configured_heightened_rank'),autoHeightenLevel:{...num('configured_auto_heighten_rank'),nullable:true},uses:object({value:num('innate_uses_value'),max:num('innate_uses_max')},'innate_uses')},'location'),
 slug:str('source_slug',true),publication:object({title:str('publication_title'),authors:str('publication_authors'),license:str('publication_license'),remaster:bool('publication_remaster')},'publication'),
};
for(const spec of [schema.area.children.details,damage.children.kinds,damage.children.applyMod,...['signature','heightenedLevel','autoHeightenLevel','uses'].map(k=>schema.location.children[k])])spec.optional=true;
/** PF2e-specific spell source-key JSON Pointer encoding; never document identity. */
const escape=key=>key.replaceAll('~','~0').replaceAll('/','~1');
/** PF2e-specific explicit spell schema walk. Partial layers omit missing members;
 * full source reports missing leaves. Finite depth 12 and 12000 descriptors reject
 * oversized/cyclic source with an actionable path; no source is truncated silently.
 */
function select(source,prose=false){
 const rows=[];let count=0;
 /** PF2e-specific spell bounded source descriptor emission; no defaults or evaluation. */
const emit=(path,spec,present,value)=>{
  if(++count>12000)throw new TypeError(`Spell source ${path} exceeds 12000 selected fields; reduce malformed source complexity.`);
  rows.push({path,present,...(present?{value}:{}),concept:spec.concept,limitations:[...LIMIT]});
 };
 /** PF2e-specific spell malformed selected-source rejection without source-content disclosure. */
const error=path=>{throw new TypeError(`Spell source ${path} has an unexpected type or exceeds nesting depth 12.`);};
 /** PF2e-specific spell explicit schema traversal preserving source versus absent values. */
const walk=(value,present,spec,path,depth,partial=false)=>{
  if(depth>12)error(path);
  if(!present||(value===undefined&&(spec.optional||partial))){if(!partial)emit(path,spec,false);return;}
  if(value===undefined)error(path);
  if(value===null){if(!spec.nullable)error(path);emit(path,spec,true,null);return;}
  if(spec.type){if(typeof value!==spec.type||(spec.type==='number'&&!Number.isFinite(value)))error(path);emit(path,spec,true,value);return;}
  if(spec.array){if(!Array.isArray(value))error(path);if(!value.length)emit(path,spec,true,[]);for(let i=0;i<value.length;i++)walk(value[i],true,spec.array,path+'/'+i,depth+1,partial);return;}
  if(typeof value!=='object'||Array.isArray(value))error(path);
  if(spec.record){const keys=Object.keys(value).sort();if(!keys.length)emit(path,spec,true,{});for(const key of keys)walk(value[key],true,spec.record,path+'/'+escape(key),depth+1,partial);return;}
  if(partial&&!Object.keys(value).length)emit(path,spec,true,{});
  for(const [key,child]of Object.entries(spec.children))walk(value[key],Object.hasOwn(value,key),child,path+'/'+escape(key),depth+1,partial);
 };
 /** PF2e-specific spell recursive selected spell source patches; no variant application. */
const system=(value,path,depth,partial=false,allowOverlays=true)=>{
  if(depth>12||!value||typeof value!=='object'||Array.isArray(value))error(path);
  if(partial&&!Object.keys(value).length&&!prose)emit(path,{concept:'spell_system_patch'},true,{});
  if(prose){if(value.description&&Object.hasOwn(value.description,'value'))walk(value.description.value,true,str('description_text'),path+'/description/value',depth+1,partial);else if(!partial)emit(path+'/description/value',str('description_text'),false);}
  else for(const [key,spec]of Object.entries(schema))walk(value[key],Object.hasOwn(value,key),spec,path+'/'+key,depth+1,partial);
  if(Object.hasOwn(value,'heightening')&&value.heightening!==undefined){
   const h=value.heightening,p=path+'/heightening';if(!h||typeof h!=='object'||Array.isArray(h))error(p);
   if(partial&&!Object.keys(h).length&&!prose)emit(p,{concept:'spell_heightening'},true,{});
   if(!prose)walk(h.type,Object.hasOwn(h,'type'),str('heightening_type'),p+'/type',depth+1,partial);
   if(h.type==='interval'||(partial&&!Object.hasOwn(h,'type')&&!Object.hasOwn(h,'levels'))){
    if(!prose)for(const [key,spec]of Object.entries({interval:num('heightening_interval'),area:num('heightening_area_increment'),damage:record(str('heightening_damage_formula'),'heightening_damage')}))walk(h[key],Object.hasOwn(h,key),spec,p+'/'+key,depth+1,partial);
   }else if(h.type==='fixed'||(partial&&!Object.hasOwn(h,'type')&&Object.hasOwn(h,'levels'))){
    if(!h.levels||typeof h.levels!=='object'||Array.isArray(h.levels))error(p+'/levels');
    const keys=Object.keys(h.levels).sort();if(!keys.length&&!prose)emit(p+'/levels',{concept:'spell_fixed_heightening_levels'},true,{});
    for(const key of keys){if(!/^(?:[1-9]|10)$/.test(key))error(p+'/levels/'+escape(key));system(h.levels[key],p+'/levels/'+key,depth+1,true,allowOverlays);}
   }else error(p+'/type');
  }else if(!partial&&!prose)emit(path+'/heightening',{concept:'spell_heightening'},false);
  if(allowOverlays&&Object.hasOwn(value,'overlays')&&value.overlays!==undefined){
   const overlays=value.overlays,p=path+'/overlays';if(!overlays||typeof overlays!=='object'||Array.isArray(overlays))error(p);
   const keys=Object.keys(overlays).sort();if(!keys.length&&!prose)emit(p,{concept:'spell_overlays'},true,{});
   for(const key of keys){const o=overlays[key],q=p+'/'+escape(key);if(!o||typeof o!=='object'||Array.isArray(o))error(q);
    if(!prose)for(const [field,spec]of Object.entries({name:str('overlay_name'),overlayType:str('overlay_type'),sort:num('overlay_sort')}))walk(o[field],Object.hasOwn(o,field),spec,q+'/'+field,depth+1,field==='name');
    if(Object.hasOwn(o,'system')&&o.system!==undefined)system(o.system,q+'/system',depth+1,true,false);
   }
  }else if(allowOverlays&&!partial&&!prose)emit(path+'/overlays',{concept:'spell_overlays'},false);
 };
 system(source.system??{},'/system',0);return rows;
}
/** PF2e-specific spell source fields; base rank and stored configuration only.
 * Unknown codes/text survive unchanged; absent optional members stay absent.
 * Nested fixed layers/overlays use source-path provenance, never synthetic UUIDs.
 */
export function spellFields(source){return source?.type==='spell'?select(source):null;}
/** PF2e-specific nested spell description selector for explicit description reads.
 * Does not enrich HTML or execute overlays. Returns exact stored root and nested
 * description.value strings only.
 */
export function spellDescriptionFields(source){return source?.type==='spell'?select(source,true):null;}
