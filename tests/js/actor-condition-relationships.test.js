import test from 'node:test';
import assert from 'node:assert/strict';
import {readItem} from '../../foundry-module/scripts/actors.js';
function fixture(synthetic=false){
 const docs=new Map();const actor={documentName:'Actor',uuid:synthetic?'Scene.s.Token.t.Actor.a':'Actor.a',id:'a',type:'npc',name:'Owner',items:new Map(),folder:null,compendium:null,testUserPermission:()=>true};
 const source={name:'Condition',type:'condition',system:{references:{parent:{id:'parent'},children:[{id:'child',type:'condition'},{id:'second',type:'condition'}],overrides:[],overriddenBy:[]},overrides:['frightened']}};
 const make=(id,type)=>{const item={documentName:'Item',uuid:actor.uuid+'.Item.'+id,id,type,name:'Duplicate',parent:actor,folder:null,compendium:null,testUserPermission:()=>true,toObject(){if(id==='selected')return structuredClone(source);throw Error('target source forbidden');}};docs.set(item.uuid,item);actor.items.set(id,item);return item;};
 const item=make('selected','condition'),parent=make('parent','effect'),child=make('child','condition'),second=make('second','condition');
 const scene={documentName:'Scene',uuid:'Scene.s',name:'Scene',testUserPermission:()=>true};
 const token={documentName:'Token',uuid:'Scene.s.Token.t',id:'t',name:'Token',actor,baseActor:actor,parent:scene,isLinked:!synthetic,testUserPermission:()=>true};docs.set(token.uuid,token);docs.set(actor.uuid,actor);
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},items:new Map(),actors:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>docs.get(uuid)}};
 return {actor,item,parent,child,second,source,token,docs};
}
test('condition local references resolve actual owned Items with linked and synthetic token follow-up',async()=>{
 for(const synthetic of [false,true]){
  const f=fixture(synthetic);let cursor,rows=[];
  do{const page=await readItem({item_uuid:f.item.uuid,token_uuid:f.token.uuid,sections:['relationships'],limit:2,...(cursor?{cursor}:{})});rows.push(...page.records);cursor=page.pagination.next_cursor;}while(cursor);
  const resolved=rows.filter(r=>r.mapped.value.status==='resolved');assert.equal(resolved.length,3);
  assert.equal(new Set(resolved.map(r=>r.mapped.value.target_uuid)).size,3);
  for(const row of resolved){assert.equal(row.mapped.value.token_uuid,f.token.uuid);assert.equal(row.mapped.value.name,'Duplicate');assert.equal(row.provenance.mapping,'pf2e.condition.reference.v1');}
  assert.equal(resolved[0].mapped.value.type,'effect');
  for(const target of [f.parent,f.child,f.second])target.toObject=()=>({name:target.name,type:target.type});
  for(const row of resolved){const value=row.mapped.value;assert.equal((await readItem({item_uuid:value.target_uuid,token_uuid:value.token_uuid,sections:['identity']})).identity.uuid,value.target_uuid);}
  assert.ok(rows.some(r=>r.mapped.concept==='condition_override_slug'&&r.mapped.value.status==='unverified'&&r.raw[0].value==='frightened'));
  assert.ok(rows.filter(r=>r.mapped.concept==='condition_child_reference').every(r=>r.raw.length===2));
 }
});
test('condition absent denied and unsupported local references remain separate without target source reads',async()=>{
 const f=fixture();f.parent.testUserPermission=()=>false;f.child.type='weapon';f.actor.items.delete('second');
 const page=await readItem({item_uuid:f.item.uuid,sections:['relationships']});
 const values=page.records.map(r=>r.mapped.value);assert.ok(values.some(v=>v.status==='denied'));assert.ok(values.some(v=>v.status==='unsupported'));assert.ok(values.some(v=>v.status==='missing'));
 assert.ok(values.every(v=>v.status==='resolved'||Object.keys(v).length===2));
 f.item.parent=null;f.item.uuid='Item.selected';f.docs.set(f.item.uuid,f.item);
 const standalone=await readItem({item_uuid:f.item.uuid,sections:['relationships']});assert.ok(standalone.records.filter(r=>r.raw[0].path.endsWith('/id')).every(r=>r.mapped.value.status==='unverified'));
});
test('condition relationship cursors detect changes in target identity permissions and membership',async()=>{
 for(const mutate of [f=>f.child.name='Changed',f=>f.parent.testUserPermission=()=>false,f=>f.actor.items.delete('child')]){
  const f=fixture();const first=await readItem({item_uuid:f.item.uuid,sections:['relationships'],limit:1});mutate(f);
  await assert.rejects(readItem({item_uuid:f.item.uuid,sections:['relationships'],limit:1,cursor:first.pagination.next_cursor}),e=>e.rpcError.code==='ContentChanged');
 }
});
test('condition source reads do not inspect related Items and retain no resolved state',async()=>{
 const f=fixture();f.actor.items={values(){throw Error('no related collection access');}};
 const page=await readItem({item_uuid:f.item.uuid,sections:['source']});
 assert.ok(page.records.every(row=>row.section==='source'));assert.ok(!page.records.some(row=>row.mapped.value?.status==='resolved'));
});
