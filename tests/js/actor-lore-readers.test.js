import test from 'node:test';
import assert from 'node:assert/strict';
import {readItem,readActor} from '../../foundry-module/scripts/actors.js';

function fixture(ownerType='npc') {
 const docs=new Map();
 const owner={documentName:'Actor',uuid:'Actor.a',id:'a',name:'Owner',type:ownerType,items:new Map(),folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>({name:'Owner',type:ownerType})};
 const make=(id,name='Sailing Lore')=>{
  const source={name,type:'lore',system:{mod:{value:99},proficient:{value:2},variants:{'a/~':{label:'Recall',options:'source-option'}},traits:{otherTags:[]},description:{value:'<p>Exact Lore 🙂</p>'}}};
  const item={documentName:'Item',uuid:`${owner.uuid}.Item.${id}`,id,name,type:'lore',parent:owner,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
  owner.items.set(id,item);docs.set(item.uuid,item);return {source,item};
 };
 const first=make('first'),second=make('second');docs.set(owner.uuid,owner);
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map([['a',owner]]),items:new Map()};
 globalThis.foundry={utils:{fromUuid:async uuid=>docs.get(uuid)}};
 return {owner,docs,make,first,second};
}

test('Lore owner semantics retain rank labels and never invent a calculated modifier',async()=>{
 for(const ownerType of ['npc','character','familiar']) {
  const f=fixture(ownerType);const page=await readItem({item_uuid:f.first.item.uuid,limit:100});
  assert.equal(page.identity.actor.type,ownerType);
  const modifier=page.records.find(r=>r.raw[0].path==='/system/mod/value');
  assert.equal(modifier.raw[0].value,99);assert.equal(modifier.mapped.concept,ownerType==='npc'?'npc_lore_authored_modifier':'stored_lore_modifier');
  const rank=page.records.find(r=>r.raw[0].path==='/system/proficient/value');
  assert.equal(rank.raw[0].value,2);assert.deepEqual(rank.mapped.value,{rank:2,label:'Expert'});
  assert.equal(rank.mapped.concept,ownerType==='character'?'character_lore_proficiency_rank':'stored_lore_proficiency_rank');
  assert.equal(page.sections[1].status,'complete');
 }
});

test('duplicate Lore specialties remain separate partial Skills references with usable selectors',async()=>{
 const f=fixture();const page=await readActor({actor_uuid:f.owner.uuid,sections:['skills','effective']});
 assert.equal(page.sections[0].status,'partial');assert.ok(page.sections[0].reasons.includes('other_skills_pending'));
 assert.equal(page.sections[1].status,'unsupported');assert.equal(page.records.length,2);
 const uuids=page.records.map(row=>row.mapped.value.target_uuid);assert.equal(new Set(uuids).size,2);
 for(const row of page.records) {
  assert.equal(row.raw[0].value,'Sailing Lore');assert.equal(row.raw[1].value,'lore');
  const item=await readItem({item_uuid:row.mapped.value.target_uuid});assert.equal(item.identity.actor.uuid,f.owner.uuid);
 }
 const first=await readActor({actor_uuid:f.owner.uuid,sections:['skills'],limit:1});
 f.owner.items.delete('second');
 await assert.rejects(readActor({actor_uuid:f.owner.uuid,sections:['skills'],limit:1,cursor:first.pagination.next_cursor}),error=>error.rpcError.code==='ContentChanged');
});

test('linked and synthetic Skills references preserve the selected token instance',async()=>{
 for(const linked of [true,false]) {
  const f=fixture('character');
  if(!linked) {
   f.owner.uuid='Scene.s.Token.t.Actor.a';
   for(const item of f.owner.items.values())item.uuid=`${f.owner.uuid}.Item.${item.id}`;
  }
  const scene={documentName:'Scene',uuid:'Scene.s',name:'Inactive',testUserPermission:()=>true};
  const token={documentName:'Token',uuid:'Scene.s.Token.t',name:'Placed',parent:scene,isLinked:linked,actor:f.owner,baseActor:null,testUserPermission:()=>true};
  f.docs.set(token.uuid,token);
  const page=await readActor({token_uuid:token.uuid,sections:['skills']});
  for(const row of page.records) {
   assert.equal(row.mapped.value.token_uuid,token.uuid);
   const followed=await readItem({item_uuid:row.mapped.value.target_uuid,token_uuid:row.mapped.value.token_uuid});
   assert.equal(followed.identity.instance.token_uuid,token.uuid);assert.equal(followed.identity.actor.type,'character');
  }
 }
});

test('unreadable Lore stays private and source fields keep independent limits and errors',async()=>{
 const f=fixture();f.second.item.name='Private specialty';f.second.item.testUserPermission=()=>false;
 f.second.item.toObject=()=>{throw Error('Denied source must not be touched');};
 let page=await readActor({actor_uuid:f.owner.uuid,sections:['skills']});
 const marker=page.records.find(row=>row.mapped.value.status==='denied');assert.ok(marker);
 assert.deepEqual(marker.raw,[]);assert.ok(!JSON.stringify(page).includes(f.second.item.uuid));assert.ok(!JSON.stringify(page).includes('Private specialty'));
 f.first.source.system.variants['a/~'].options='🙂'.repeat(10000);
 await assert.rejects(async()=>{let cursor;do {
  const part=await readItem({item_uuid:f.first.item.uuid,max_bytes:8000,limit:100,cursor});cursor=part.pagination.next_cursor;
 }while(cursor);},error=>error.rpcError.code==='ResponseTooLarge'&&error.rpcError.message.includes('/system/variants/a~1~0/options'));
 const description=await readItem({item_uuid:f.first.item.uuid,sections:['description']});assert.equal(description.records[0].raw[0].value,f.first.source.system.description.value);
 game.system.id='other';await assert.rejects(readActor({actor_uuid:f.owner.uuid,sections:['skills']}),error=>error.rpcError.code==='UnsupportedSystem');
});
