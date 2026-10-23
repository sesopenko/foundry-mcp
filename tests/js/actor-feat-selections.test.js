import test from 'node:test';
import assert from 'node:assert/strict';
import {featSelectionFields} from '../../foundry-module/scripts/actorFeatSelections.js';
import {readItem} from '../../foundry-module/scripts/actors.js';
test('recorded selections preserve opaque keys and exact scalar source with unsupported values withheld',()=>{
 assert.equal(featSelectionFields({type:'other'}),null);
 assert.equal(featSelectionFields({type:'feat'}).fields[0].present,false);
 assert.deepEqual(featSelectionFields({type:'feat',flags:{pf2e:{rulesSelections:{}}}}).fields[0].value,{});
 const selections={'a/~':'Item.possible', '':2.5, complex:{private:'selection_private_sentinel'},bool:true,null:null};
 const result=featSelectionFields({type:'feat',flags:{pf2e:{rulesSelections:selections}}});assert.equal(result.fields.length,2);assert.equal(result.fields[0].path,'/flags/pf2e/rulesSelections/a~1~0');assert.equal(result.fields[1].path,'/flags/pf2e/rulesSelections/');assert.equal(result.fields[1].value,2.5);assert.equal(result.issues.length,3);assert.ok(!JSON.stringify(result).includes('selection_private_sentinel'));
 for(const value of [null,[],false,'x'])assert.throws(()=>featSelectionFields({type:'feat',flags:{pf2e:{rulesSelections:value}}}));
 const map=Object.fromEntries(Array.from({length:12000},(_,i)=>[String(i),'x']));assert.equal(featSelectionFields({type:'feat',flags:{pf2e:{rulesSelections:map}}}).fields.length,12000);map.extra='x';assert.throws(()=>featSelectionFields({type:'feat',flags:{pf2e:{rulesSelections:map}}}));
});
test('unsupported recorded selections produce partial paginated source without leaking content',async()=>{
 const source={name:'Feat',type:'feat',system:{},flags:{pf2e:{rulesSelections:{choice:'selected',unread:{private:'selection_private_sentinel'}}}}};
 const item={documentName:'Item',id:'a',uuid:'Item.a',name:'Feat',type:'feat',parent:null,compendium:null,folder:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map(),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>uuid==='Item.a'?item:null}};
 let cursor,rows=[];do{const page=await readItem({item_uuid:'Item.a',sections:['source'],limit:3,...(cursor?{cursor}:{})});assert.equal(page.sections[0].status,'partial');assert.ok(page.sections[0].reasons.includes('unsupported_selection_values'));rows.push(...page.records);cursor=page.pagination.next_cursor;}while(cursor);
 assert.equal(rows.find(r=>r.raw[0].path==='/flags/pf2e/rulesSelections/choice').raw[0].value,'selected');assert.ok(!JSON.stringify(rows).includes('selection_private_sentinel'));assert.ok(!rows.some(r=>r.raw[0].path.endsWith('/unread')));
});
