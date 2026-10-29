/** PF2e-specific character inventory runtime adapter, PF2e8.6.1/core14.369.
 * Scoped user-authorized exception (2026-10-28) to public-API evidence policy:
 * inventory.currency/totalWealth/bulk and physical Item.assetValue/bulk getters.
 * https://github.com/foundryvtt/pf2e/tree/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/inventory
 * https://github.com/foundryvtt/pf2e/tree/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/physical
 * These are current system calculations, not persisted source or sale proceeds.
 * No preparation, sheet access, mutation or locally reconstructed item totals.
 */
import {permitted} from './actorDocuments.js';
import {PHYSICAL_TYPES} from './actorPhysical.js';

const missing=reason=>({availability:'potentially_missing',value:null,reason});
const available=value=>({availability:'available',value});
const number=value=>typeof value==='number'&&Number.isFinite(value)&&value>=0&&value<=Number.MAX_SAFE_INTEGER;
const integer=value=>number(value)&&Number.isSafeInteger(value);
/** Catch each PF2e-specific getter independently; never expose exception text. */
function probe(get,valid){try{const value=get();return value===undefined||value===null?missing('missing_api'):valid(value)?available(value):missing('invalid_value');}catch{return missing('getter_failed');}}
/** PF2e-specific Bulk uses normal units plus tenths (light), never float sums. */
function bulk(get){return probe(()=>{const value=get();if(value==null)return undefined;const normal=value.normal,light=value.light;return integer(normal)&&Number.isInteger(light)&&light>=0&&light<=9&&Number.isSafeInteger(normal*10+light)?normal*10+light:NaN;},integer);}
/** PF2e-specific bounded detached metric witness; no fake document-data path. */
function record(section,group,concept,reading,unit=null){return {key:`${section}:${group}:${concept}`,section,kind:'field',raw:[],mapped:{concept,value:reading,unit},provenance:{contributors:[],mapping:'pf2e.actor.inventory-metrics.v1',limitations:['version_specific_guarded_runtime_getters']}};}

/** PF2e-specific character summary/item reads. Every unavailable value is
 * potentially_missing, never zero. Owner-wide totals require all owned Items
 * readable; item selection never narrows totals. Item Bulk is non-additive
 * because aggregate Bulk includes stacking, size and container adjustments.
 */
export function inventoryMetrics(target,sections,selection=null){
 const result={records:[],sections:[]};
 const wanted=sections.filter(s=>['wealth','bulk'].includes(s));
 if(!wanted.length)return result;
 if(target.document.type!=='character')return {...result,sections:wanted.map(name=>({name,status:'unsupported',reasons:['character_only']}))};
 let items=[],scopeError=null;
 try{items=[...target.document.items.values()];if(items.length>12000)scopeError='item_limit';else if(items.some(item=>!permitted(item)))scopeError='items_denied';}
 catch{scopeError='getter_failed';}
 const safe=(get,valid)=>scopeError?missing(scopeError):probe(get,valid);
 const money=get=>safe(()=>get()?.copperValue,integer);
 const itemRows=selection?.item_uuids??[];
 for(const section of wanted){
  const add=(group,concept,reading,unit)=>result.records.push(record(section,group,concept,reading,unit));
  if(!selection||selection.details.includes(section)){
   if(section==='wealth'){
    const currency=money(()=>target.document.inventory?.currency),wealth=money(()=>target.document.inventory?.totalWealth);
    add('summary','total_currency',currency,'cp');add('summary','total_wealth',wealth,'cp');
    add('summary','non_currency_value',currency.availability==='available'&&wealth.availability==='available'?wealth.value>=currency.value?available(wealth.value-currency.value):missing('inconsistent_value'):missing('dependency_unavailable'),'cp');
   }else{
    const carried=scopeError?missing(scopeError):bulk(()=>target.document.inventory?.bulk?.value);
    const threshold=safe(()=>target.document.inventory?.bulk?.encumberedAfter,integer);
    const maximum=safe(()=>target.document.inventory?.bulk?.max,integer);
    const encumbered=safe(()=>target.document.inventory?.bulk?.isEncumbered,v=>typeof v==='boolean');
    add('summary','carried_bulk',carried,'light_bulk');
    add('summary','encumbered_after',threshold,'bulk');add('summary','maximum_bulk',maximum,'bulk');
    add('summary','is_encumbered',encumbered);add('summary','is_over_max',safe(()=>target.document.inventory?.bulk?.isOverMax,v=>typeof v==='boolean'));
    let until=missing('dependency_unavailable');
    if([carried,threshold,encumbered].every(v=>v.availability==='available')){
     const crossing=(threshold.value+1)*10;
     until=Number.isSafeInteger(crossing)&&encumbered.value===(carried.value>=crossing)?available(Math.max(0,crossing-carried.value)):missing('inconsistent_value');
    }
    add('summary','until_encumbered',until,'light_bulk');
   }
  }
  if(selection?.details.includes(section+'.items')){
   if(scopeError)add('items','item_count',missing(scopeError));
   else{
    let physical;
    try{physical=items.filter(item=>PHYSICAL_TYPES.includes(item.type)).map(item=>({item,uuid:item.uuid}));if(physical.some(({uuid})=>typeof uuid!=='string'||uuid.length>512))physical=null;else physical=physical.filter(({uuid})=>!itemRows.length||itemRows.includes(uuid)).sort((a,b)=>a.uuid.localeCompare(b.uuid));}
    catch{physical=null;}
    if(!physical)add('items','item_count',missing('getter_failed'));
    else{
     add('items','item_count',available(physical.length));
     for(const {item,uuid} of physical){
      const group='item:'+uuid;
      add(group,'item_uuid',available(uuid));
      add(group,'item_name',probe(()=>item.name,v=>typeof v==='string'&&v.length<=256));
      add(group,'quantity',probe(()=>item.quantity,integer));
      if(section==='wealth')add(group,'asset_value',money(()=>item.assetValue),'cp');
      else add(group,'item_bulk',bulk(()=>item.bulk),'light_bulk');
     }
    }
   }
  }
  const incomplete=result.records.some(r=>r.section===section&&r.mapped.value.availability==='potentially_missing');
  result.sections.push({name:section,status:incomplete?'partial':'complete',reasons:incomplete?['potentially_missing']:[]});
 }
 return result;
}
