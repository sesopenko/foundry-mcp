import test from 'node:test';
import assert from 'node:assert/strict';
import {inventoryMetrics} from '../../foundry-module/scripts/actorInventoryMetrics.js';
import {readActorSelected} from '../../foundry-module/scripts/actors.js';

function fixture(){
 const actor={documentName:'Actor',uuid:'Actor.a',id:'a',name:'Metric PC',type:'character',folder:null,compendium:null,items:new Map(),testUserPermission:()=>true,toObject:()=>({name:'Metric PC',type:'character',system:{}}),inventory:{currency:{copperValue:0},totalWealth:{copperValue:2500},bulk:{value:{normal:5,light:9},encumberedAfter:5,max:10,isEncumbered:false,isOverMax:false}}};
 globalThis.game={version:'14.369',system:{id:'pf2e',version:'8.6.1'},ready:true,user:{isGM:true},actors:new Map([['a',actor]]),items:new Map()};
 globalThis.foundry={utils:{fromUuid:async()=>actor}};
 return {document:actor,identity:{uuid:actor.uuid},token:null};
}
const values=result=>Object.fromEntries(result.records.map(r=>[r.mapped.concept,r.mapped.value]));
test('character source disclaimer appears only when source fields are requested',async()=>{
 fixture();
 for(const details of [[],['wealth'],['bulk'],['wealth','bulk'],['source'],['source','wealth']]){
  const {result}=await readActorSelected({actor_uuid:'Actor.a',select:{details}});
  assert.equal(result.limitations.some(text=>text.startsWith('Character selected persisted source only:')),details.includes('source'),JSON.stringify(details));
 }
});
test('guarded summaries preserve zero/false and exact strict encumbrance crossing',()=>{
 const f=fixture(),v=values(inventoryMetrics(f,['wealth','bulk']));
 assert.equal(v.total_currency.value,0);assert.equal(v.non_currency_value.value,2500);
 assert.equal(v.carried_bulk.value,59);assert.equal(v.until_encumbered.value,1);assert.equal(v.is_encumbered.value,false);
 f.document.inventory.bulk.value={normal:6,light:0};f.document.inventory.bulk.isEncumbered=true;
 assert.equal(values(inventoryMetrics(f,['bulk'])).until_encumbered.value,0);
});
test('throwing, absent and malformed getters stay isolated; exception text never escapes',()=>{
 const f=fixture();Object.defineProperty(f.document.inventory,'totalWealth',{get(){throw Error('SECRET');}});
 let result=inventoryMetrics(f,['wealth','bulk']),v=values(result);
 assert.equal(v.total_wealth.reason,'getter_failed');assert.equal(v.total_currency.value,0);assert.equal(v.carried_bulk.value,59);assert.ok(!JSON.stringify(result).includes('SECRET'));
 delete f.document.inventory.bulk.value;assert.equal(values(inventoryMetrics(f,['bulk'])).carried_bulk.reason,'missing_api');
 f.document.inventory.bulk.encumberedAfter=NaN;assert.equal(values(inventoryMetrics(f,['bulk'])).encumbered_after.reason,'invalid_value');
 Object.defineProperty(f.document,'inventory',{get(){throw Error('SECRET');}});
 assert.ok(inventoryMetrics(f,['wealth','bulk']).records.every(r=>r.mapped.value.availability==='potentially_missing'));
});
test('denied inventory withholds totals without invoking getters; unsupported types explicit',()=>{
 const f=fixture();f.document.items.set('x',{testUserPermission:()=>false});
 Object.defineProperty(f.document,'inventory',{get(){assert.fail('denied getter read');}});
 assert.ok(inventoryMetrics(f,['wealth','bulk']).records.every(r=>r.mapped.value.reason==='items_denied'||r.mapped.value.reason==='dependency_unavailable'));
 f.document.type='npc';assert.equal(inventoryMetrics(f,['wealth']).sections[0].status,'unsupported');
});
test('actual selective reader paginates summaries, rejects stale values and other systems',async()=>{
 const f=fixture(),args={actor_uuid:'Actor.a',select:{details:['wealth','bulk']},limit:1};
 const first=await readActorSelected(args);
 assert.equal(first.result.entries[0].values[0].availability,'available');assert.ok(first.result.pagination.next_cursor);
 const next=await readActorSelected({...args,cursor:first.result.pagination.next_cursor});assert.equal(next.result.entries[0].section,'bulk');assert.equal(next.result.pagination.complete,true);
 f.document.inventory.currency.copperValue=1;
 await assert.rejects(readActorSelected({...args,cursor:first.result.pagination.next_cursor}),e=>e.rpcError.code==='ContentChanged');
 game.system.id='other';await assert.rejects(readActorSelected(args),e=>e.rpcError.code==='UnsupportedSystem');
});
test('optional item details are selected independently and failures do not erase siblings',()=>{
 const f=fixture();for(const id of ['x','y'])f.document.items.set(id,{uuid:'Actor.a.Item.'+id,name:id,type:'equipment',quantity:1,assetValue:{copperValue:100},bulk:{normal:0,light:1},testUserPermission:()=>true});
 const item=f.document.items.get('x');Object.defineProperty(item,'assetValue',{get(){throw Error('private');}});
 const result=inventoryMetrics(f,['wealth'],{details:['wealth','wealth.items'],item_uuids:[item.uuid]});
 assert.equal(values(result).asset_value.reason,'getter_failed');assert.equal(values(result).total_wealth.value,2500);
 assert.ok(!result.records.some(r=>r.key.includes('.y')));
 assert.equal(inventoryMetrics(f,['wealth'],{details:['wealth']}).records.length,3);
});
