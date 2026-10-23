/**
 * PF2e-specific feat8.6.1 recorded selection source; Foundry14.369 boundary.
 * https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/base/data/system.ts
 * rulesSelections permits arbitrary objects. Only exact string/finite-number
 * leaves are selected; unsupported values are withheld with partial diagnostics.
 * Recorded selections establish neither acquisition nor evaluated eligibility.
 */
/** PF2e-specific recorded selection source-key JSON Pointer escaping. */
function pointer(key){return '/flags/pf2e/rulesSelections/'+key.replaceAll('~','~0').replaceAll('/','~1');}
/**
 * PF2e-specific feat recorded rulesSelections from detached toObject(true).
 * Returns {fields,issues}, null for non-feat. Missing/undefined and empty maps
 * remain distinct. Unsupported values never enter raw rows or recursive reads.
 * The caller must mark source partial when issues exist. Maximum12000 keys.
 */
export function featSelectionFields(source){
 if(source?.type!=='feat')return null;
 const fields=[],issues=[],path='/flags/pf2e/rulesSelections';
 let value=source;let present=true;
 for(const key of ['flags','pf2e','rulesSelections']){if(value===null||typeof value!=='object'||!Object.hasOwn(value,key)){present=false;break;}value=value[key];}
 if(value===undefined)present=false;
 if(!present){fields.push({path,present:false,concept:'feat_selection_entries',limitations:['feat_source_not_effective_benefit']});return {fields,issues};}
 if(!value||typeof value!=='object'||Array.isArray(value))throw new TypeError('Feat recorded selections must be a source map.');
 const keys=Object.keys(value);if(keys.length>12000)throw new TypeError('Feat recorded selections exceed12000 keys.');
 if(!keys.length)fields.push({path,present:true,value:{},concept:'feat_selection_entries',limitations:['feat_source_not_effective_benefit']});
 for(const key of keys){const selected=value[key];if(typeof selected==='string'||typeof selected==='number'&&Number.isFinite(selected))fields.push({path:pointer(key),present:true,value:selected,concept:'feat_recorded_selection',limitations:['feat_source_not_effective_benefit']});else issues.push({path:pointer(key),reason:'unsupported_selection_value'});}
 return {fields,issues};
}
