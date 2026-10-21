import test from 'node:test';
import assert from 'node:assert/strict';
import {readItem,readActor} from '../../foundry-module/scripts/actors.js';
function fixture(linked=true){
 const docs=new Map();
 const actor={documentName:'Actor',uuid:linked?'Actor.a':'Scene.s.Token.t.Actor.a',id:'a',name:'Origin',type:'npc',items:new Map(),folder:null,compendium:null,testUserPermission:()=>true,toObject(){throw Error('target source must not be read');}};
 const scene={documentName:'Scene',uuid:'Scene.s',name:'Scene',testUserPermission:()=>true};
 const token={documentName:'Token',uuid:'Scene.s.Token.t',id:'t',name:'Token',parent:scene,actor,baseActor:actor,isLinked:linked,testUserPermission:()=>true};
 const origin={documentName:'Item',uuid:actor.uuid+'.Item.origin',id:'origin',name:'Same',type:'spell',parent:actor,folder:null,compendium:null,testUserPermission:()=>true,toObject(){throw Error('target source must not be read');}};
 actor.items.set(origin.id,origin);
 const source={name:'Effect',type:'effect',system:{context:{origin:{actor:actor.uuid,token:token.uuid,item:origin.uuid},target:{actor:actor.uuid,token:token.uuid}}}};
 const effect={documentName:'Item',uuid:'Item.effect',id:'effect',name:'Effect',type:'effect',folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
 for(const doc of [actor,token,origin,effect])docs.set(doc.uuid,doc);
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map(),items:new Map()};
 globalThis.foundry={utils:{fromUuid:async uuid=>docs.get(uuid)}};
 return {actor,token,origin,effect,source,docs};
}
test('effect relationships preserve immediate linked and synthetic selectors without reading target source',async()=>{
 for(const linked of [true,false]){
  const f=fixture(linked);const page=await readItem({item_uuid:f.effect.uuid,sections:['relationships']});
  assert.equal(page.records.length,5);assert.equal(page.sections[0].status,'complete');
  for(const row of page.records){const value=row.mapped.value;assert.equal(value.status,'resolved');assert.equal(value.token_uuid,f.token.uuid);assert.equal(row.raw.length,5);assert.equal(row.provenance.mapping,'pf2e.effect.context-reference.v1');}
  f.origin.toObject=()=>({name:f.origin.name,type:f.origin.type});f.actor.toObject=()=>({name:f.actor.name,type:f.actor.type});
  const item=page.records.find(r=>r.mapped.value.document_name==='Item').mapped.value;
  assert.equal((await readItem({item_uuid:item.target_uuid,token_uuid:item.token_uuid,sections:['identity']})).identity.uuid,f.origin.uuid);
  const owner=page.records.find(r=>r.mapped.value.document_name==='Actor').mapped.value;
  assert.equal((await readActor({token_uuid:owner.token_uuid,sections:['identity']})).identity.uuid,f.actor.uuid);
 }
});
test('effect source-only and absent context never hydrate related documents',async()=>{
 const f=fixture();const calls=[];foundry.utils.fromUuid=async uuid=>{calls.push(uuid);return f.docs.get(uuid);};
 await readItem({item_uuid:f.effect.uuid,sections:['source']});assert.ok(calls.every(uuid=>uuid===f.effect.uuid));
 f.source.system.context=null;const page=await readItem({item_uuid:f.effect.uuid,sections:['relationships']});
 assert.ok(page.records.every(row=>row.mapped.value.status==='missing'&&row.mapped.value.target_uuid===null));
});
test('denied missing malformed and mismatched targets expose no resolved identity',async()=>{
 const f=fixture();f.origin.testUserPermission=()=>false;f.source.system.context.target.token='Scene.s.Token.missing';
 const page=await readItem({item_uuid:f.effect.uuid,sections:['relationships']});
 assert.equal(page.records.find(r=>r.key.endsWith('origin_item')).mapped.value.status,'denied');
 assert.ok(page.records.filter(r=>r.key.includes('target_')).every(r=>r.mapped.value.status==='missing'));
 for(const row of page.records.filter(r=>r.mapped.value.status!=='resolved'))assert.deepEqual(Object.keys(row.mapped.value).sort(),['status','target_uuid']);
 f.source.system.context.origin.actor='Actor.other';
 const mismatch=await readItem({item_uuid:f.effect.uuid,sections:['relationships']});
 assert.equal(mismatch.records[0].mapped.value.status,'unverified');
 f.source.system.context.origin.token='not a uuid';
 const invalid=await readItem({item_uuid:f.effect.uuid,sections:['relationships']});assert.equal(invalid.records[0].mapped.value.status,'unsupported');
 f.source.system.context=3;await assert.rejects(readItem({item_uuid:f.effect.uuid,sections:['relationships']}),e=>e.rpcError.code==='ReadFailed');
});
test('target identity and permission changes invalidate continuation',async()=>{
 const f=fixture();const first=await readItem({item_uuid:f.effect.uuid,sections:['relationships'],limit:1});
 f.origin.name='Changed';
 await assert.rejects(readItem({item_uuid:f.effect.uuid,sections:['relationships'],limit:1,cursor:first.pagination.next_cursor}),e=>e.rpcError.code==='ContentChanged');
});
test('standalone compendium origins resolve independently of a contextual token and retain duplicate roles',async()=>{
 const f=fixture();const pack={collection:'pf2e.spells',title:'Spells',testUserPermission:()=>true};
 const item={documentName:'Item',uuid:'Compendium.pf2e.spells.Item.spell',id:'spell',name:'Source spell',type:'spell',folder:null,compendium:pack,testUserPermission:()=>true};
 f.docs.set(item.uuid,item);f.source.system.context.origin.item=item.uuid;
 const page=await readItem({item_uuid:f.effect.uuid,sections:['relationships']});
 const origin=page.records.find(r=>r.key.endsWith('origin_item')).mapped.value;
 assert.equal(origin.status,'resolved');assert.equal(origin.target_uuid,item.uuid);assert.ok(!Object.hasOwn(origin,'token_uuid'));
 assert.equal(page.records.filter(r=>r.mapped.value.target_uuid===f.actor.uuid).length,2);
 const first=await readItem({item_uuid:f.effect.uuid,sections:['relationships'],limit:1});pack.testUserPermission=()=>false;
 await assert.rejects(readItem({item_uuid:f.effect.uuid,sections:['relationships'],limit:1,cursor:first.pagination.next_cursor}),e=>e.rpcError.code==='ContentChanged');
});
