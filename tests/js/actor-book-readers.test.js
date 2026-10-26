import test from 'node:test';
import assert from 'node:assert/strict';
import {readItem,getActorTypes} from '../../foundry-module/scripts/actors.js';
function fixture(type='book',category='spell'){
 const source={name:'Stored book',type,system:{category,capacity:100,contents:['Item.spell','Item.spell','Item.missing','Actor.wrong','relative','Item.denied'],description:{value:'Original activation prose'}}};
 const sourceReads={book:0,target:0};
 const item={documentName:'Item',uuid:'Item.book',id:'book',name:'Book',type,folder:null,compendium:null,parent:null,testUserPermission:()=>true,toObject:basis=>{assert.equal(basis,true);sourceReads.book++;return structuredClone(source);}};
 const spell={documentName:'Item',uuid:'Item.spell',id:'spell',name:'Definition',type:'spell',folder:null,compendium:null,parent:null,testUserPermission:()=>true,toObject:()=>{sourceReads.target++;throw Error('no target source expansion');}};
 const denied={...spell,id:'denied',uuid:'Item.denied',name:'secret target',testUserPermission:()=>false};
 const docs=new Map([[item.uuid,item],[spell.uuid,spell],[denied.uuid,denied],['Actor.wrong',{...spell,documentName:'Actor',uuid:'Actor.wrong'}]]);let lookups=0;const lookupUUIDs=[];
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map(),items:new Map([['book',item]])};globalThis.foundry={utils:{fromUuid:async uuid=>{lookups++;lookupUUIDs.push(uuid);return docs.get(uuid);}}};
 return {source,item,spell,docs,sourceReads,lookupUUIDs,get lookups(){return lookups;}};
}
async function all(sections,limit=5){let cursor,rows=[],last;do{last=await readItem({item_uuid:'Item.book',sections,limit,max_bytes:8000,...(cursor?{cursor}:{})});rows.push(...last.records);cursor=last.pagination.next_cursor;}while(cursor);return {rows,last};}
test('book category capacity ordered repeated content and exact prose remain definition source, not learned or prepared',async()=>{
 for(const category of ['formula','spell']){const f=fixture('book',category),before=JSON.stringify(f.source),{rows,last}=await all(['source','description','effective']);assert.equal(last.sections[0].status,'complete');assert.equal(last.sections[1].status,'complete');assert.equal(last.sections[2].status,'unsupported');assert.equal(rows.find(r=>r.raw[0]?.path==='/system/category').raw[0].value,category);assert.equal(rows.filter(r=>r.mapped.concept==='book_content_uuid').length,6);assert.equal(rows.find(r=>r.raw[0]?.path==='/system/description/value').raw[0].value,'Original activation prose');assert.equal(f.sourceReads.target,0);assert.equal(JSON.stringify(f.source),before);}
});
test('explicit book links name immediate targets with duplicate index identities and unresolved privacy',async()=>{
 const f=fixture(),{rows,last}=await all(['relationships'],100);assert.equal(rows.length,6);assert.equal(new Set(rows.map(r=>r.key)).size,6);assert.deepEqual(rows.map(r=>r.mapped.value.status),['resolved','resolved','missing','unsupported','unsupported','denied']);assert.equal(rows[0].mapped.value.target_uuid,'Item.spell');assert.equal(rows[0].mapped.value.name,'Definition');assert.ok(!JSON.stringify(rows).includes('secret target'));assert.equal(f.sourceReads.target,0);assert.equal(last.sections[0].status,'complete');
 // Initial/final snapshot each resolves repeated claims once; selected book resolution twice.
 assert.equal(f.lookups,10);
});
test('book empty versus absent, malformed contents and relationship bound remain explicit',async()=>{
 const f=fixture();for(const present of [false,true]){if(present)f.source.system.contents=[];else delete f.source.system.contents;const {rows}=await all(['relationships']);assert.equal(rows.length,1);assert.equal(rows[0].raw[0].present,present);assert.equal(rows[0].mapped.value.status,present?'empty':'missing');}
 f.source.system.contents=[42];await assert.rejects(readItem({item_uuid:f.item.uuid,sections:['source']}),e=>e.rpcError.code==='ReadFailed');f.source.system.contents=Array(201).fill('Item.spell');await assert.rejects(readItem({item_uuid:f.item.uuid,sections:['relationships']}),e=>e.rpcError.code==='ReadFailed');assert.equal((await all(['source'],100)).last.sections[0].status,'complete');
});
test('book continuation rechecks source claims target names and permissions, and rejects other systems',async()=>{
 for(const change of ['source','name','permission']){const f=fixture(),first=await readItem({item_uuid:f.item.uuid,sections:['relationships'],limit:1});if(change==='source')f.source.system.contents.reverse();if(change==='name')f.spell.name='Changed';if(change==='permission')f.spell.testUserPermission=()=>false;await assert.rejects(readItem({item_uuid:f.item.uuid,sections:['relationships'],limit:1,cursor:first.pagination.next_cursor}),e=>e.rpcError.code==='ContentChanged');}
 fixture();game.system.id='other';await assert.rejects(readItem({item_uuid:'Item.book',sections:['source']}),e=>e.rpcError.code==='UnsupportedSystem');fixture();const row=(await getActorTypes()).item_types.find(r=>r.type==='book');assert.equal(row.mapped_supported,true);assert.equal(row.effective_supported,false);assert.equal(row.verification.live.status,'passed');
});
test('book synthetic content retains actual token selector and source-only reading never resolves claims',async()=>{
 const f=fixture(),actor={documentName:'Actor',uuid:'Scene.s.Token.t.Actor.a',id:'a',name:'Owner',type:'npc',items:new Map(),testUserPermission:()=>true};const scene={documentName:'Scene',uuid:'Scene.s',name:'Scene',testUserPermission:()=>true};const token={documentName:'Token',uuid:'Scene.s.Token.t',name:'Token',parent:scene,actor,baseActor:null,isLinked:false,testUserPermission:()=>true};actor.token=token;const spell={...f.spell,uuid:actor.uuid+'.Item.spell',parent:actor};actor.items.set('spell',spell);f.docs.set(spell.uuid,spell);f.docs.set(token.uuid,token);f.source.system.contents=[spell.uuid];
 await all(['source']);assert.ok(f.lookupUUIDs.every(uuid=>uuid==='Item.book'));const {rows}=await all(['relationships']);assert.equal(rows[0].mapped.value.token_uuid,token.uuid);assert.equal(rows[0].mapped.value.target_uuid,spell.uuid);spell.toObject=()=>({name:'Definition',type:'spell',system:{}});const follow=await readItem({item_uuid:spell.uuid,token_uuid:token.uuid,sections:['identity']});assert.equal(follow.identity.uuid,spell.uuid);
});
