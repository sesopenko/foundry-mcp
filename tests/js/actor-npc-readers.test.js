import test from 'node:test';
import assert from 'node:assert/strict';
import {readActor} from '../../foundry-module/scripts/actors.js';
function fixture(){
 const source={name:'Creature',type:'npc',system:{abilities:{str:{mod:4}},attributes:{adjustment:'elite',ac:{value:22},hp:{value:17,max:70},resistances:[{type:'physical',value:5,exceptions:['silver']}]},skills:{athletics:{base:14,note:'+18 swimming'}},details:{privateNotes:'excluded secret'}}};
 const actor={documentName:'Actor',uuid:'Actor.a',id:'a',name:'Creature',type:'npc',items:new Map(),folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map([['a',actor]]),items:new Map()};
 globalThis.foundry={utils:{fromUuid:async uuid=>uuid===actor.uuid?actor:null}};return {source,actor};
}
test('NPC source pages retain authored statistics and provenance without elite arithmetic',async()=>{
 const f=fixture(),before=JSON.stringify(f.source);let cursor,rows=[];
 do{const page=await readActor({actor_uuid:f.actor.uuid,sections:['source','effective'],limit:7,max_bytes:8000,...(cursor?{cursor}:{})});
 assert.equal(page.sections[0].status,'partial');assert.equal(page.sections[1].status,'unsupported');
 rows.push(...page.records);cursor=page.pagination.next_cursor;}while(cursor);
 const ac=rows.find(r=>r.raw[0].path==='/system/attributes/ac/value');assert.equal(ac.raw[0].value,22);assert.equal(ac.mapped.value,22);assert.equal(ac.provenance.mapping,'pf2e.npc.source.v1');
 assert.ok(ac.provenance.limitations.includes('source_not_complete_effective_statistic'));
 assert.equal(rows.find(r=>r.raw[0].path==='/system/abilities/str/mod').mapped.value,4);
 assert.ok(!JSON.stringify(rows).includes('excluded secret'));assert.equal(JSON.stringify(f.source),before);
});
test('NPC source changes invalidate continuation and malformed selected values fail safely',async()=>{
 const f=fixture();const first=await readActor({actor_uuid:f.actor.uuid,sections:['source'],limit:1});
 f.source.system.attributes.hp.value=12;
 await assert.rejects(readActor({actor_uuid:f.actor.uuid,sections:['source'],limit:1,cursor:first.pagination.next_cursor}),e=>e.rpcError.code==='ContentChanged');
 f.source.system.attributes.ac.value={private:'hidden'};
 await assert.rejects(readActor({actor_uuid:f.actor.uuid,sections:['source']}),e=>e.rpcError.code==='ReadFailed'&&!e.message.includes('hidden'));
});
