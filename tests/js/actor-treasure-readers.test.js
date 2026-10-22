import test from 'node:test';
import assert from 'node:assert/strict';
import {readItem,getActorTypes} from '../../foundry-module/scripts/actors.js';
function fixture(type='character',synthetic=false){
 const source={name:'Valuables',type:'treasure',system:{category:'gem',quantity:20,price:{value:{pp:1,gp:2,sp:3,cp:4},per:10},equipped:{carryType:'worn'},containerId:null,material:{type:null,grade:null},traits:{value:['precious'],otherTags:[],rarity:'common'},description:{value:'<p>Exact gem 🙂</p>'}}};
 const actor={documentName:'Actor',uuid:synthetic?'Scene.s.Token.t.Actor.a':'Actor.a',id:'a',name:'Owner',type,items:new Map(),folder:null,compendium:null,testUserPermission:()=>true};
 const item={documentName:'Item',uuid:actor.uuid+'.Item.v',id:'v',name:source.name,type:'treasure',parent:actor,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};actor.items.set(item.id,item);
 const scene={documentName:'Scene',uuid:'Scene.s',name:'Scene',testUserPermission:()=>true},token={documentName:'Token',uuid:'Scene.s.Token.t',id:'t',name:'Token',parent:scene,actor,baseActor:actor,isLinked:!synthetic,testUserPermission:()=>true};const docs=new Map([[actor.uuid,actor],[item.uuid,item],[token.uuid,token]]);
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map(),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>docs.get(uuid)}};return {source,item,actor,token};
}
test('supported Actor valuables keep quantity denominations and price-per independent without a sale calculation',async()=>{
 for(const type of ['character','npc','familiar'])for(const synthetic of [false,true]){
  const f=fixture(type,synthetic),before=JSON.stringify(f.source);let cursor,rows=[],last;
  do{last=await readItem({item_uuid:f.item.uuid,token_uuid:f.token.uuid,sections:['source','effective','rules'],limit:7,max_bytes:8000,...(cursor?{cursor}:{})});assert.ok(last.sections.slice(1).every(s=>s.status==='unsupported'));rows.push(...last.records);cursor=last.pagination.next_cursor;}while(cursor);
  assert.equal(last.sections[0].status,'complete');assert.equal(last.identity.instance.token_uuid,f.token.uuid);assert.equal(last.identity.actor.type,type);
  for(const [path,value]of [['category','gem'],['quantity',20],['price/per',10],['price/value/pp',1],['price/value/gp',2],['price/value/sp',3],['price/value/cp',4]])assert.equal(rows.find(r=>r.raw[0].path==='/system/'+path).raw[0].value,value);
  assert.equal(rows.find(r=>r.raw[0].path==='/system/category').provenance.mapping,'pf2e.treasure.source.v1');assert.equal(rows.find(r=>r.raw[0].path==='/system/price/per').provenance.mapping,'pf2e.physical.source.v1');assert.equal(new Set(rows.map(r=>r.raw[0].path)).size,rows.length);assert.ok(!rows.some(r=>/sale|assetValue|stackGroup|usage|invested/.test(r.raw[0].path)));assert.equal(JSON.stringify(f.source),before);
 }
});
test('treasure nullable categories descriptions and source errors remain explicit',async()=>{
 const f=fixture();f.source.system.category=null;let cursor,rows=[];do{const page=await readItem({item_uuid:f.item.uuid,sections:['source'],limit:100,...(cursor?{cursor}:{})});rows.push(...page.records);cursor=page.pagination.next_cursor;}while(cursor);assert.equal(rows.find(r=>r.raw[0].path==='/system/category').raw[0].value,null);
 assert.equal((await readItem({item_uuid:f.item.uuid,sections:['description']})).records[0].raw[0].value,f.source.system.description.value);
 const first=await readItem({item_uuid:f.item.uuid,sections:['source'],limit:1});f.source.system.price.per=5;await assert.rejects(readItem({item_uuid:f.item.uuid,sections:['source'],limit:1,cursor:first.pagination.next_cursor}),e=>e.rpcError.code==='ContentChanged');f.source.system.category={secret:true};await assert.rejects(readItem({item_uuid:f.item.uuid,sections:['source']}),e=>e.rpcError.code==='ReadFailed');
 game.system.id='other';await assert.rejects(readItem({item_uuid:f.item.uuid}),e=>e.rpcError.code==='UnsupportedSystem');game.system.id='pf2e';f.item.testUserPermission=()=>false;await assert.rejects(readItem({item_uuid:f.item.uuid}),e=>e.rpcError.code==='PermissionDenied');
});
test('loot-Actor exclusion does not grant a bypass for otherwise supported treasure Items',async()=>{
 const f=fixture('loot');await assert.rejects(readItem({item_uuid:f.item.uuid}),e=>e.rpcError.code==='UnsupportedType');
});
test('treasure discovery distinguishes stored valuation basis from inferred sales',async()=>{
 fixture();const entry=(await getActorTypes()).item_types.find(r=>r.type==='treasure');assert.equal(entry.mapped_supported,true);assert.equal(entry.effective_supported,false);assert.match(entry.limitations.join(' '),/sale proceeds/);
});
