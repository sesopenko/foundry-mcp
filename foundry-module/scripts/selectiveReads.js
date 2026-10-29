/** Pure selection/presentation over validated reader records; no Foundry APIs.
 * PF2e-specific concepts originate in the existing core14.369/PF2e8.6.1
 * selectors (actorCurrent/Skills/Casting/Inventory and Item source helpers).
 * Source and transformed bases remain separate; no derived maths occurs here.
 * PF2e8.6.1 Actor/Item schema boundary (same revision as those selectors):
 * https://github.com/foundryvtt/pf2e/tree/28d9d156f252d084371d994dc359509b49eadf18/src/module
 * Selection and grouping below use only the existing validated record paths;
 * they introduce no dependency on runtime getters, sheets or internal members.
 */
import {digest, fail, integer} from './actorReadUtils.js';
const bytes = value => new TextEncoder().encode(JSON.stringify(value)).length;
/** Select metadata before pagination; canonical identity remains usable alone. */
export function compactNode(node,select) {
  if(node.kind==='item'){
    const id=node.identity;
    const result={kind:'item',identity:select.context?id:{uuid:id.uuid,name:id.name,name_truncated:id.name_truncated,type:id.type,...(id.instance?{token_uuid:id.instance.token_uuid}:{})}};
    if(select.context)result.parent_uuid=node.parent_uuid;
    if(select.relationships)result.relationships=node.relationships??[];
    if(select.follow_up)result.next_call=node.next_call;
    if(select.limitations&&node.limitations)result.limitations=node.limitations;
    return result;
  }
  const result={kind:'pack',id:node.id,title:node.title,title_truncated:node.title_truncated,document_type:node.document_type,searchable:true};
  if(select.context)Object.assign(result,{visible:node.visible,folder:node.folder,parent_uuid:node.parent_uuid});
  if(select.follow_up)Object.assign(result,{search_scope:node.search_scope,next_call:node.next_call});
  if(select.limitations)result.limitations=node.limitations;
  return result;
}
const statistic = path => {
  if (path.includes('/abilities/')) return 'attributes';
  if (path.includes('/attributes/ac/')) return 'armor_class';
  if (path.includes('/attributes/hp/')) return 'hit_points';
  if (path.includes('/saves/')) return 'saves';
  if (path.includes('/senses')) return 'senses';
  if (path.includes('/perception/')) return 'perception';
  if (path.includes('/movement/') || path.includes('/speed')) return 'movement';
  if (path.includes('/languages')) return 'languages';
  return 'iwr';
};

/** PF2e-specific named Item source groups. Unknown groups never read raw paths. */
export function itemGroup(row) {
  const path=row.raw[0]?.path??'', concept=row.mapped.concept;
  if (path.includes('/prepared/') || path.includes('/slots/')) return 'preparations';
  if (/damage|healing/.test(path)) return 'damage';
  if (/actionType|actions\/value|frequency/.test(path)) return 'activation';
  if (/bonus|range|subjectToMAP|attackEffects/.test(path)) return 'attack';
  if (/traits/.test(path)) return 'traits';
  if (/publication/.test(path)) return 'publication';
  if (/armor|acBonus|dexCap|checkPenalty|speedPenalty|hardness|\/hp\//.test(path)) return 'defenses';
  if (/spell|casting|tradition|prepared|proficiency/.test(concept)) return 'casting';
  if (/quantity|bulk|price|equipped|containerId|material|identification|usage/.test(path)) return 'physical';
  return 'definition';
}

/** PF2e-specific selection BEFORE pagination, retaining diagnostics and witnesses. */
export function selectRecords(records, selection) {
  const details=selection.details??[];
  return records.filter(row=>{
    const section=row.section, path=row.raw[0]?.path??'', concept=row.mapped.concept;
    let included=details.includes(section);
    if(section==='statistics') included ||= details.includes('statistics.'+statistic(path));
    if(section==='source') included ||= details.includes('source.'+itemGroup(row));
    if(section==='inventory' && details.includes('inventory.summary')) included ||= ['inventory_item','quantity','inventory_container','inventory_kit_definition','inventory_scope'].includes(concept);
    if(section==='spellcasting' && details.includes('spellcasting.prepared')) included ||= concept==='casting_contextual_option' && row.mapped.value.context==='prepared_use' || concept==='casting_preparation' && row.mapped.value.status!=='resolved' || concept==='casting_item';
    if(section==='spellcasting' && details.includes('spellcasting.options')) included ||= ['casting_contextual_option','casting_preparation','casting_item'].includes(concept);
    if(!included) return false;
    if(selection.item_uuids?.length && ['inventory','abilities','build'].includes(section) && row.raw.length && !row.raw.some(r=>selection.item_uuids.includes(r.document_uuid)))return false;
    if(selection.entry_uuids?.length && section==='spellcasting' && row.raw.length && !row.raw.some(r=>selection.entry_uuids.includes(r.document_uuid)))return false;
    if(selection.skill_names?.length && section==='skills') {
      const skill=path.match(/^\/system\/skills\/([^/]+)/)?.[1];
      if(skill && !selection.skill_names.includes(skill))return false;
    }
    return true;
  });
}

/** PF2e-specific semantic page unit: statistic, skill, Strike, Item or preparation. */
export function groupKey(row) {
  const path=row.raw[0]?.path??'', section=row.section;
  if(row.kind==='text')return row.key;
  if(section==='statistics')return section+':'+statistic(path);
  if(section==='skills')return section+':'+(path.match(/^\/system\/skills\/([^/]+)/)?.[1]??row.key);
  if(section==='strikes')return section+':'+(path.match(/^\/system\/actions\/\d+(?:\/altUsages\/\d+)*/)?.[0]??row.key);
  if(section==='inventory')return section+':'+(row.raw[0]?.document_uuid??row.key);
  // A casting option already includes the individual preparation and its witnesses.
  if(section==='spellcasting')return row.key;
  if(section==='source')return section+':'+itemGroup(row)+((path.match(/^(\/system\/slots\/slot\d+(?:\/prepared\/\d+)?)/)?.[1])??'');
  return row.key;
}

/** Compact projection is mirrored and checked by Python before MCP delivery. */
export function compactRead(proof, groups, evidence=false) {
  const entries=groups.map(rows=>({section:rows[0].section,key:groupKey(rows[0]),values:rows.map(row=>{
    const bases=[...new Set(row.raw.map(r=>r.basis))];
    const value={concept:row.mapped.concept,value:row.kind==='text'?(row.raw[0].value??null):row.mapped.value,basis:bases.length===1?bases[0]:bases.length?'mixed':'none'};
    if(row.raw.length===1)value.present=row.raw[0].present;
    if(row.text)value.text=row.text;
    if(row.mapped.unit!==null)value.unit=row.mapped.unit;
    if(evidence)value.evidence=row;
    return value;
  })}));
  return {contract_version:2,runtime:proof.runtime,identity:proof.identity,revision:proof.revision,
    sections:proof.sections,entries,pagination:{...proof.pagination,returned:entries.length},
    limitations:[...new Set([...proof.limitations,...proof.records.flatMap(r=>r.provenance.limitations)])]};
}

/** Bound selected semantic units and their private validation witnesses separately. */
export async function selectivePage(records,base,params,scope) {
  const selected=selectRecords(records,params.select), grouped=new Map();
  for(const row of selected){const key=groupKey(row);if(!grouped.has(key))grouped.set(key,[]);grouped.get(key).push(row);}
  const groups=[...grouped.values()],limit=integer(params.limit,10,1,100,'limit'),budget=integer(params.max_bytes,8000,8000,48000,'max_bytes');
  const binding=await digest({scope,select:params.select,limit,budget});let start=0;
  if(params.cursor){let c;try{c=JSON.parse(atob(params.cursor));}catch{fail('InvalidCursor','Malformed continuation.','Restart without cursor.');}
    if(c.binding!==binding)fail('CursorMismatch','Selections or bounds changed.','Restore original inputs or restart.');
    if(c.revision!==base.revision)fail('ContentChanged','Selected data changed.','Discard prior pages and restart.');
    if(!Number.isInteger(c.position)||c.position<0||c.position>groups.length)fail('InvalidCursor','Invalid position.');start=c.position;}
  const make=end=>{
    const pageGroups=groups.slice(start,end),flat=pageGroups.flat(),complete=end===groups.length;
    const next=complete?null:btoa(JSON.stringify({binding,revision:base.revision,position:end}));
    const proof={...base,records:flat,pagination:{complete,next_cursor:next,returned:flat.length}};
    proof.sections=base.sections.map(s=>groups.slice(end).some(g=>g[0].section===s.name)&&['complete','partial'].includes(s.status)?{...s,status:'partial',reasons:[...new Set([...s.reasons,'pagination'])]}:s);
    const result=compactRead(proof,pageGroups,params.select.evidence===true);
    return {proof,group_lengths:pageGroups.map(g=>g.length),result};
  };
  let end=start,packet=make(end);
  while(end<groups.length&&end-start<limit){const next=make(end+1);if(bytes(next.result)>budget||bytes(next)>60000)break;packet=next;end++;}
  if(bytes(packet.result)>budget||bytes(packet)>60000||end===start&&start<groups.length)fail('ResponseTooLarge','One selected semantic unit exceeds the byte budget.','Select fewer details or increase max_bytes up to 48000; request descriptions separately.');
  return packet;
}
