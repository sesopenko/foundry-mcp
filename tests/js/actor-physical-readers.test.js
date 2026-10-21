import test from 'node:test';
import assert from 'node:assert/strict';
import {readItem} from '../../foundry-module/scripts/actors.js';

function fixture(type='weapon') {
 const source={name:'Stored Item',type,flags:{secret:'omit-me'},system:{quantity:0,price:{value:{gp:3},per:10},equipped:{invested:false},usage:{value:'unknown-code'},subitems:[{_id:'local',name:'Attachment',type:'weapon',system:{secret:'omit-me'}}],identification:{status:'unidentified',unidentified:{name:'Unknown',data:{description:{value:'<p>🙂\\\"</p>'.repeat(1000)}}}}}};
 const item={documentName:'Item',id:'i',uuid:'Item.i',name:source.name,type,folder:null,parent:null,compendium:null,testUserPermission:()=>true,toObject:sourceOnly=>{assert.equal(sourceOnly,true);return structuredClone(source);}};
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map(),items:new Map([['i',item]])};
 globalThis.foundry={utils:{fromUuid:async uuid=>uuid===item.uuid?item:null}};
 return {source,item};
}

test('physical source reads retain exact values, absent fields and attachment provenance',async()=>{
 fixture();let cursor=null;const records=[];
 do {
  const page=await readItem({item_uuid:'Item.i',max_bytes:8000,limit:3,cursor});
  assert.ok(Buffer.byteLength(JSON.stringify(page))<=8000);records.push(...page.records);cursor=page.pagination.next_cursor;
  assert.equal(page.sections.find(s=>s.name==='source').status,page.pagination.complete?'complete':'partial');
 }while(cursor);
 const raw=path=>records.find(r=>r.raw[0].path===path)?.raw[0];
 assert.equal(raw('/system/quantity').value,0);assert.equal(raw('/system/price/per').value,10);
 assert.equal(raw('/system/equipped/invested').value,false);
 assert.equal(raw('/system/material/type').present,false);assert.equal('value' in raw('/system/material/type'),false);
 assert.equal(raw('/system/subitems/0/_id').value,'local');
 assert.ok(!JSON.stringify(records).includes('omit-me'));
 assert.ok(!raw('/system/identification/unidentified/data/description/value'));
});

test('explicit unidentified descriptions reconstruct exactly and source changes invalidate pages',async()=>{
 const {source}=fixture();let cursor=null;const records=[];
 do {
  const page=await readItem({item_uuid:'Item.i',sections:['description'],limit:2,max_bytes:8000,cursor});
  records.push(...page.records);cursor=page.pagination.next_cursor;
 }while(cursor);
 assert.equal(records.filter(r=>r.kind==='text').map(r=>r.raw[0].value).join(''),source.system.identification.unidentified.data.description.value);
 const first=await readItem({item_uuid:'Item.i',limit:1});source.system.price.per=5;
 await assert.rejects(readItem({item_uuid:'Item.i',limit:1,cursor:first.pagination.next_cursor}),error=>error.rpcError.code==='ContentChanged');
 source.system.quantity={unexpected:true};
 await assert.rejects(readItem({item_uuid:'Item.i'}),error=>error.rpcError.code==='ReadFailed'&&error.rpcError.message.includes('/system/quantity'));
});

test('concrete physical omissions and empty attachments remain distinct',async()=>{
 const {source}=fixture('armor');
 let page=await readItem({item_uuid:'Item.i',limit:100});
 assert.ok(!page.records.some(r=>r.raw[0].path==='/system/usage/value'));
 source.system.subitems=[];page=await readItem({item_uuid:'Item.i',limit:100});
 assert.deepEqual(page.records.find(r=>r.raw[0].path==='/system/subitems').raw[0].value,[]);
});
