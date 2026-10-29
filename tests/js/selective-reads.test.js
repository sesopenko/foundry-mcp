import test from 'node:test';
import assert from 'node:assert/strict';
import {selectRecords,selectivePage} from '../../foundry-module/scripts/selectiveReads.js';
const field=(path,concept,value=1)=>({key:'statistics:'+path,section:'statistics',kind:'field',raw:[{document_uuid:'Actor.a',path,present:true,value,basis:'transformed'}],mapped:{concept,value,unit:null},provenance:{contributors:[],mapping:'test',limitations:['not_target_context']}});
const records=[...Array.from({length:12},(_,i)=>field('/system/abilities/'+i+'/mod','attribute_'+i)),field('/system/attributes/ac/value','current_armor_class',20),field('/system/attributes/ac/breakdown','current_armor_class_breakdown','Base 10 + 10'),field('/system/attributes/ac/details','current_armor_class_exception_notes',''),field('/system/attributes/hp/value','current_hit_points',30)];
const base={contract_version:1,runtime:{core_version:'14.369',system_id:'pf2e',system_version:'8.6.1'},identity:{uuid:'Actor.a'},revision:'r1',sections:[{name:'statistics',status:'partial',reasons:['other_statistics_pending']}],limitations:[]};
test('selection reaches AC directly and preserves all related values in one unit',async()=>{
 const result=await selectivePage(records,base,{select:{details:['statistics.armor_class']},limit:1},{});
 assert.equal(result.result.entries.length,1);assert.equal(result.result.entries[0].values.length,3);
 assert.equal(result.result.entries[0].values[0].value,20);assert.equal(result.result.pagination.complete,true);
 assert.equal(result.proof.records.length,3);assert.ok(!JSON.stringify(result.result).includes('attribute_'));
});
test('empty selections return identity without source expansion',async()=>{
 const result=await selectivePage(records,base,{select:{details:[]}},{});
 assert.deepEqual(result.result.entries,[]);assert.equal(result.result.identity.uuid,'Actor.a');
});
test('semantic pagination binds selection, bounds and revision',async()=>{
 const params={select:{details:['statistics']},limit:1};const first=await selectivePage(records,base,params,{});
 assert.equal(first.result.pagination.complete,false);
 const cursor=first.result.pagination.next_cursor;
 const second=await selectivePage(records,base,{...params,cursor},{});
 assert.equal(second.result.entries[0].key,'statistics:armor_class');
 await assert.rejects(selectivePage(records,base,{...params,cursor,select:{details:['statistics.armor_class']}},{}),e=>e.rpcError.code==='CursorMismatch');
 await assert.rejects(selectivePage(records,{...base,revision:'r2'},{...params,cursor},{}),e=>e.rpcError.code==='ContentChanged');
});
test('source absence and transformed basis survive compact projection',async()=>{
 const row=field('/system/attributes/ac/value','current_armor_class',null);row.raw[0].present=false;delete row.raw[0].value;
 const result=await selectivePage([row],base,{select:{details:['statistics.armor_class']}},{});
 assert.equal(result.result.entries[0].values[0].present,false);assert.equal(result.result.entries[0].values[0].basis,'transformed');
});
test('prepared options retain repeated positions and unresolved preparation diagnostics',()=>{
 const row=(context,key)=>({section:'spellcasting',key,raw:[],mapped:{concept:'casting_contextual_option',value:{context}}});
 assert.equal(selectRecords([row('prepared_use','one'),row('prepared_use','two'),row('listed_spell','three')],{details:['spellcasting.prepared']}).length,2);
});
test('senses select their nested perception paths without selecting Perception',()=>{
 const rows=[field('/system/perception/senses/0/type','current_sense_type','darkvision'),field('/system/perception/value','current_perception',10)];
 assert.equal(selectRecords(rows,{details:['statistics.senses']}).length,1);
 assert.equal(selectRecords(rows,{details:['statistics.perception']}).length,1);
});
test('missing description remains an explicit missing value, not omitted JSON',async()=>{
 const row={...field('/system/description/value','description',null),key:'description',section:'description',kind:'text',text:{path:'/system/description/value',start:0,end:0,total:0,complete:true}};
 row.raw[0].present=false;delete row.raw[0].value;
 const result=await selectivePage([row],{...base,sections:[{name:'description',status:'complete',reasons:[]}]},{select:{details:['description']}},{});
 assert.equal(JSON.parse(JSON.stringify(result.result)).entries[0].values[0].value,null);
});
test('scope limitations survive even without selected records',async()=>{
 const result=await selectivePage([],{...base,limitations:['Denied data is not evidence of absence.']},{select:{details:[]}},{});
 assert.deepEqual(result.result.limitations,['Denied data is not evidence of absence.']);
});
test('large Item preparations page by slot position instead of one indivisible source group',async()=>{
 const rows=Array.from({length:100},(_,i)=>['id','expended'].map(k=>({...field(`/system/slots/slot1/prepared/${i}/${k}`,'casting_entry_prepared_'+k,k==='id'?'spell':false),section:'source'}))).flat();
 const page=await selectivePage(rows,{...base,sections:[{name:'source',status:'complete',reasons:[]}]},{select:{details:['source.preparations']},limit:2},{});
 assert.equal(page.result.entries.length,2);
 assert.equal(page.result.entries[0].values.length,2);
 assert.equal(page.result.pagination.complete,false);
});
