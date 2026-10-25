import test from 'node:test';
import assert from 'node:assert/strict';
import {readActor,getActorTypes} from '../../foundry-module/scripts/actors.js';
function fixture(synthetic=false,type='npc'){
 const source={name:'Caster',type,system:{resources:{focus:{value:1,max:2}}}};
 const actor={documentName:'Actor',uuid:synthetic?'Scene.s.Token.t.Actor.a':'Actor.a',id:'a',name:source.name,type,folder:null,compendium:null,items:new Map(),testUserPermission:()=>true,toObject:basis=>{assert.equal(typeof basis,'boolean');return structuredClone(source);}};
 const docs=new Map([[actor.uuid,actor]]),sources=new Map();
 for(const [id,itemType,system]of [['entry','spellcastingEntry',{prepared:{value:'prepared'},tradition:{value:'arcane'},slots:{slot1:{value:0,max:2,prepared:[{id:'spell',expended:false},{id:'spell',expended:true}]}}}],['spell','spell',{level:{value:1},traits:{value:['cantrip']},location:{value:'entry',signature:true,heightenedLevel:5,uses:{value:1,max:1}}}],['unassigned','spell',{level:{value:2},traits:{value:[]},location:{value:null}}]]){
  const data={name:'Same name',type:itemType,system};sources.set(id,data);const item={documentName:'Item',uuid:actor.uuid+'.Item.'+id,id,name:data.name,type:itemType,parent:actor,folder:null,compendium:null,testUserPermission:()=>true,toObject:basis=>{assert.equal(typeof basis,'boolean');return structuredClone(data);}};actor.items.set(id,item);docs.set(item.uuid,item);
 }
 const scene={documentName:'Scene',uuid:'Scene.s',name:'Scene',testUserPermission:()=>true},token={documentName:'Token',uuid:'Scene.s.Token.t',id:'t',name:'Token',parent:scene,actor,baseActor:actor,isLinked:!synthetic,testUserPermission:()=>true};docs.set(token.uuid,token);
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map([['a',actor]]),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>docs.get(uuid)}};return {source,actor,sources,token};
}
async function all(f,token=false){let cursor,rows=[],last;do{last=await readActor({...(token?{token_uuid:f.token.uuid}:{actor_uuid:f.actor.uuid}),sections:['spellcasting','effective'],limit:7,max_bytes:8000,...(cursor?{cursor}:{})});assert.equal(last.sections[0].status,'partial');assert.ok(last.sections[0].reasons.includes('availability_not_evaluated'));assert.equal(last.sections[1].status,'unsupported');rows.push(...last.records);cursor=last.pagination.next_cursor;}while(cursor);return {rows,last};}
test('Actor casting preserves source joins duplicate names preparations and distinct ranks without claiming availability',async()=>{
 for(const synthetic of [false,true]){const f=fixture(synthetic),before=JSON.stringify([...f.sources]),{rows}=await all(f,true);assert.equal(new Set(rows.map(r=>r.key)).size,rows.length);
 const preps=rows.filter(r=>r.mapped.concept==='casting_preparation');assert.equal(preps.length,2);assert.ok(preps.every(r=>r.mapped.value.target_uuid===f.actor.items.get('spell').uuid&&r.mapped.value.token_uuid===f.token.uuid));
 const assignments=rows.filter(r=>r.mapped.concept==='casting_spell_assignment');assert.deepEqual(assignments.map(r=>r.mapped.value.status),['resolved','missing']);
 assert.equal(rows.find(r=>r.raw[0]?.path==='/system/level/value'&&r.raw[0].document_uuid.endsWith('.spell')).raw[0].value,1);assert.equal(rows.find(r=>r.raw[0]?.path==='/system/location/heightenedLevel'&&r.raw[0].document_uuid.endsWith('.spell')).raw[0].value,5);
 assert.equal(rows.find(r=>r.key==='spellcasting:focus:value').raw[0].value,1);assert.equal(JSON.stringify([...f.sources]),before);
 }
});
test('character focus maximum stays outside persisted casting source and denied Items expose no metadata',async()=>{
 const f=fixture(false,'character');f.actor.items.get('unassigned').testUserPermission=()=>false;f.actor.items.get('unassigned').toObject=()=>{throw Error('denied source');};const {rows,last}=await all(f);assert.ok(!rows.some(r=>r.key==='spellcasting:focus:max'));assert.ok(last.sections[0].reasons.includes('casting_items_denied'));assert.ok(!JSON.stringify(rows).includes(f.actor.items.get('unassigned').uuid));
});
test('Actor casting continuation detects changed preparation and rejects other systems',async()=>{
 const f=fixture(),first=await readActor({actor_uuid:f.actor.uuid,sections:['spellcasting'],limit:1});f.sources.get('entry').system.slots.slot1.prepared[0].expended=true;await assert.rejects(readActor({actor_uuid:f.actor.uuid,sections:['spellcasting'],limit:1,cursor:first.pagination.next_cursor}),e=>e.rpcError.code==='ContentChanged');game.system.id='other';await assert.rejects(readActor({actor_uuid:f.actor.uuid,sections:['spellcasting']}),e=>e.rpcError.code==='UnsupportedSystem');
});
test('casting discovery advertises partial source joins and unavailable effective casting',async()=>{
 fixture();const row=(await getActorTypes()).actor_sections.find(r=>r.name==='spellcasting');assert.equal(row.source_supported,true);assert.equal(row.mapped_supported,true);assert.equal(row.effective_supported,false);assert.match(row.limitations.join(' '),/Partial Actor casting/);
});
