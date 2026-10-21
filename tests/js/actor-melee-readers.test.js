import test from 'node:test';
import assert from 'node:assert/strict';
import {readItem} from '../../foundry-module/scripts/actors.js';

function fixture() {
 const source={name:'Authored attack',type:'melee',flags:{pf2e:{linkedWeapon:'not-a-selector'},secret:'omit-me'},system:{action:'strike',bonus:{value:17},subjectToMAP:true,range:{increment:30,max:null},area:null,traits:{value:['thrown-20'],otherTags:[]},damageRolls:{'acid/~':{damage:'2d6+8',damageType:'acid',category:null},fire:{damage:'1d4',damageType:'fire',category:'persistent'}},attackEffects:{value:['Knockdown','Item.looks-like-a-uuid','']},description:{value:'<p>Authored attack 🙂</p>'.repeat(1000)}}};
 const owner={documentName:'Actor',uuid:'Actor.npc',name:'NPC',type:'npc',testUserPermission:()=>true};
 const item={documentName:'Item',uuid:'Actor.npc.Item.attack',id:'attack',name:source.name,type:'melee',parent:owner,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
 owner.items=new Map([['attack',item],['weapon',{type:'weapon',name:source.name,system:{damage:{dice:999}}}]]);
 let extraResolutions=0;
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map([['npc',owner]]),items:new Map()};
 globalThis.foundry={utils:{fromUuid:async uuid=>{if(uuid===item.uuid)return item;extraResolutions++;return null;}}};
 return {source,item,owner,resolutions:()=>extraResolutions};
}

test('authored ranged attack components survive bounded pages independently of carried gear',async()=>{
 const f=fixture();const before=structuredClone(f.source);const records=[];let cursor=null;
 do {const page=await readItem({item_uuid:f.item.uuid,limit:3,max_bytes:8000,cursor});
  assert.ok(Buffer.byteLength(JSON.stringify(page))<=8000);records.push(...page.records);cursor=page.pagination.next_cursor;
 }while(cursor);
 const row=path=>records.find(r=>r.raw[0].path===path);
 assert.equal(row('/system/action').mapped.value,'Strike');assert.equal(row('/system/bonus/value').raw[0].value,17);
 assert.equal(row('/system/range/increment').mapped.concept,'ranged_increment_feet');
 assert.equal(row('/system/damageRolls/acid~1~0/damage').raw[0].value,'2d6+8');
 assert.equal(row('/system/damageRolls/fire/category').raw[0].value,'persistent');
 assert.ok(!JSON.stringify(records).includes('999'));assert.ok(!JSON.stringify(records).includes('omit-me'));
 assert.deepEqual(f.source,before);assert.equal(f.resolutions(),0);
});

test('null range and non-Strike modes never become exclusive melee Strikes',async()=>{
 const f=fixture();f.source.system.range=null;
 for(const mode of ['area-fire','auto-fire','custom-mode']) {
  f.source.system.action=mode;
  const page=await readItem({item_uuid:f.item.uuid,limit:100});
  assert.notEqual(page.records.find(r=>r.raw[0].path==='/system/action').mapped.value,'Strike');
  const range=page.records.find(r=>r.raw[0].path==='/system/range');
  assert.equal(range.raw[0].value,null);assert.equal(range.mapped.value,'no_explicit_range');
  assert.ok(range.provenance.limitations.includes('source_null_range_does_not_exclude_trait_derived_ranged_attacks'));
 }
});

test('effect relationships retain labels without UUID guessing and preserve missing versus empty',async()=>{
 const f=fixture();let page=await readItem({item_uuid:f.item.uuid,sections:['relationships']});
 assert.equal(page.records.length,3);assert.equal(page.records[1].raw[0].value,'Item.looks-like-a-uuid');
 assert.deepEqual(page.records[1].mapped.value,{target_uuid:null,status:'unverified'});assert.equal(f.resolutions(),0);
 f.source.system.bonus.value={unrequested:'invalid'};
 page=await readItem({item_uuid:f.item.uuid,sections:['relationships']});assert.equal(page.records.length,3);
 f.source.system.attackEffects.value=[];page=await readItem({item_uuid:f.item.uuid,sections:['relationships']});
 assert.deepEqual(page.records[0].raw[0].value,[]);assert.equal(page.records[0].mapped.value.status,'missing');
 delete f.source.system.attackEffects.value;page=await readItem({item_uuid:f.item.uuid,sections:['relationships']});
 assert.equal(page.records[0].raw[0].present,false);assert.equal('value' in page.records[0].raw[0],false);
});

test('exact descriptions, effective exclusion, revision changes and metadata overflow stay explicit',async()=>{
 const f=fixture();let cursor=null;const rows=[];
 do {const page=await readItem({item_uuid:f.item.uuid,sections:['description','effective'],limit:2,max_bytes:8000,cursor});
  assert.equal(page.sections[1].status,'unsupported');rows.push(...page.records);cursor=page.pagination.next_cursor;
 }while(cursor);
 assert.equal(rows.map(row=>row.raw[0].value).join(''),f.source.system.description.value);
 const first=await readItem({item_uuid:f.item.uuid,limit:1});f.source.system.damageRolls.fire.damage='9d6';
 await assert.rejects(readItem({item_uuid:f.item.uuid,limit:1,cursor:first.pagination.next_cursor}),error=>error.rpcError.code==='ContentChanged');
 f.source.system.attackEffects.value=['🙂'.repeat(5000)];
 await assert.rejects(readItem({item_uuid:f.item.uuid,sections:['relationships'],max_bytes:8000}),error=>error.rpcError.code==='ResponseTooLarge'&&error.rpcError.message.includes('/system/attackEffects/value/0'));
 game.system.id='other';await assert.rejects(readItem({item_uuid:f.item.uuid}),error=>error.rpcError.code==='UnsupportedSystem');
});
