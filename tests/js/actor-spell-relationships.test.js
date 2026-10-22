import test from 'node:test';
import assert from 'node:assert/strict';
import {readItem} from '../../foundry-module/scripts/actors.js';
function fixture(synthetic=false){
 const docs=new Map();const actor={documentName:'Actor',uuid:synthetic?'Scene.s.Token.t.Actor.a':'Actor.a',id:'a',name:'Owner',type:'npc',folder:null,compendium:null,items:new Map(),testUserPermission:()=>true};
 const source={name:'Spell',type:'spell',system:{location:{value:'entry'}}};
 const spell={documentName:'Item',uuid:actor.uuid+'.Item.spell',id:'spell',name:'Spell',type:'spell',parent:actor,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
 const entry={...spell,uuid:actor.uuid+'.Item.entry',id:'entry',name:'Assigned entry',type:'spellcastingEntry',toObject(){throw Error('target source forbidden');}};
 for(const item of [spell,entry]){actor.items.set(item.id,item);docs.set(item.uuid,item);}docs.set(actor.uuid,actor);
 const scene={documentName:'Scene',uuid:'Scene.s',name:'Scene',testUserPermission:()=>true};
 const token={documentName:'Token',uuid:'Scene.s.Token.t',id:'t',name:'Token',actor,baseActor:actor,parent:scene,isLinked:!synthetic,testUserPermission:()=>true};docs.set(token.uuid,token);
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map(),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>docs.get(uuid)}};
 return {actor,spell,entry,token,source,docs};
}
test('stored spell entry selection resolves actual casting-entry identity with token follow-up',async()=>{
 for(const synthetic of [false,true])for(const type of ['spellcastingEntry']){
  const f=fixture(synthetic);f.entry.type=type;
  const page=await readItem({item_uuid:f.spell.uuid,token_uuid:f.token.uuid,sections:['relationships']});
  const row=page.records[0],value=row.mapped.value;assert.equal(value.status,'resolved');assert.equal(value.target_uuid,f.entry.uuid);assert.equal(value.token_uuid,f.token.uuid);assert.equal(value.type,type);assert.equal(row.provenance.mapping,'pf2e.spell.casting-entry.v1');
  assert.equal(row.raw[0].value,'entry');assert.equal(page.sections[0].status,'complete');
  f.entry.toObject=()=>({name:f.entry.name,type});assert.equal((await readItem({item_uuid:value.target_uuid,token_uuid:value.token_uuid,sections:['identity']})).identity.uuid,f.entry.uuid);
 }
});
test('stored spell entry missing denied unsupported and standalone states do not expose target metadata',async()=>{
 for(const [change,status]of [[f=>f.source.system.location.value=null,'missing'],[f=>delete f.source.system.location.value,'missing'],[f=>f.actor.items.delete('entry'),'missing'],[f=>f.entry.testUserPermission=()=>false,'denied'],[f=>f.entry.type='consumable','unsupported']]){
  const f=fixture();change(f);const row=(await readItem({item_uuid:f.spell.uuid,sections:['relationships']})).records[0];assert.deepEqual(row.mapped.value,{status,target_uuid:null});
 }
 const f=fixture();f.spell.parent=null;f.spell.uuid='Item.spell';f.docs.set(f.spell.uuid,f.spell);
 assert.deepEqual((await readItem({item_uuid:f.spell.uuid,sections:['relationships']})).records[0].mapped.value,{status:'unverified',target_uuid:null});
});
test('spell source reads do not inspect assigned entry and relationship snapshots detect concurrent target changes',async()=>{
 const f=fixture();const items=f.actor.items;f.actor.items={values(){throw Error('source-only must not inspect owner Items');}};
 await readItem({item_uuid:f.spell.uuid,sections:['source']});f.actor.items=items;
 let reads=0;const original=f.spell.toObject;f.spell.toObject=()=>{if(++reads===2)f.entry.name='Changed';return original();};
 await assert.rejects(readItem({item_uuid:f.spell.uuid,sections:['relationships']}),e=>e.rpcError.code==='ContentChanged');
 f.source.system.location.value={secret:'hidden'};
 await assert.rejects(readItem({item_uuid:f.spell.uuid,sections:['relationships']}),e=>e.rpcError.code==='ReadFailed'&&!e.message.includes('hidden'));
});
