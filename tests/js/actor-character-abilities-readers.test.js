import test from 'node:test';
import assert from 'node:assert/strict';
import {readActor,readItem} from '../../foundry-module/scripts/actors.js';

function fixture(context='world'){
 const docs=new Map(),source={name:'Character',type:'character',system:{}};let reads=0;
 const actor={id:'a',uuid:'Actor.a',documentName:'Actor',type:'character',name:'Character',folder:null,compendium:null,items:new Map(),testUserPermission:()=>true,toObject(flag){reads++;assert.equal(flag,true);return structuredClone(source);}};
 if(context==='pack'){actor.uuid='Compendium.test.actors.Actor.a';actor.compendium={collection:'test.actors',title:'Actors',testUserPermission:()=>true};}
 let selector={actor_uuid:actor.uuid};
 if(context==='token'){const scene={uuid:'Scene.s',documentName:'Scene',name:'Scene',testUserPermission:()=>true};const base={...actor};actor.uuid='Scene.s.Token.t.Actor.a';const token={uuid:'Scene.s.Token.t',documentName:'Token',id:'t',name:'Token',parent:scene,actor,baseActor:base,isLinked:false,testUserPermission:()=>true};docs.set(token.uuid,token);actor.token=token;selector={token_uuid:token.uuid};}
 docs.set(actor.uuid,actor);
 function add(id,type='action',name='Same ability',category=null){const stored={name,type,system:{description:{value:'<p>Exact ability prose</p>'},...(type==='feat'?{category}:{}),rules:[]}};const item={id,uuid:actor.uuid+'.Item.'+id,documentName:'Item',type,name:'Decorated display',parent:actor,folder:null,compendium:null,testUserPermission:()=>true,toObject(flag){assert.equal(flag,true);return structuredClone(stored);}};actor.items.set(id,item);docs.set(item.uuid,item);return {item,stored};}
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map([['a',actor]]),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>docs.get(uuid)}};
 return {actor,selector,add,get reads(){return reads;}};
}
async function all(f){const rows=[],pages=[];let cursor;do{const page=await readActor({...f.selector,sections:['abilities'],limit:1,max_bytes:8000,...(cursor?{cursor}:{})});assert.ok(Buffer.byteLength(JSON.stringify(page))<=8000);rows.push(...page.records);pages.push(page);cursor=page.pagination.next_cursor;assert.ok(pages.length<20);}while(cursor);return {rows,pages};}
const code=value=>error=>error.rpcError?.code===value;

test('actual character ability reader preserves duplicate action feat and classfeature origins in every context',async()=>{
 for(const context of ['world','pack','token']){const f=fixture(context),items=[f.add('action'),f.add('feat','feat','Same ability','general'),f.add('feature','feat','Same ability','classfeature')];f.add('equipment','equipment');const {rows,pages}=await all(f);assert.equal(rows.length,3);assert.equal(new Set(rows.map(row=>row.mapped.value.target_uuid)).size,3);assert.ok(pages.every(page=>page.sections[0].status==='partial'&&page.sections[0].reasons.includes('other_abilities_not_enumerated')));
  for(const {item,stored}of items){const row=rows.find(row=>row.key==='abilities:item:'+item.uuid);assert.equal(row.provenance.mapping,'pf2e.character.ability-reference.v1');assert.deepEqual(row.provenance.limitations,['owned_item_reference_not_complete_or_active_ability']);assert.equal(row.mapped.concept,'character_ability_item');assert.equal(row.mapped.value.type,item.type);assert.equal(row.mapped.value.name,stored.name);assert.deepEqual(row.raw.map(raw=>raw.path),['/name','/type']);assert.ok(row.raw.every(raw=>raw.document_uuid===item.uuid&&raw.basis==='source'&&raw.present));assert.equal(row.raw[0].value,stored.name);if(context==='token')assert.equal(row.mapped.value.token_uuid,f.selector.token_uuid);const follow=await readItem({item_uuid:item.uuid,...(context==='token'?{token_uuid:f.selector.token_uuid}:{}),sections:['identity']});assert.equal(follow.identity.actor.uuid,f.actor.uuid);}
 }
});
test('denied abilities aggregate before name/source reads and empty remains partial',async()=>{
 const f=fixture(),denied=f.add('denied','feat');denied.item.testUserPermission=()=>false;denied.item.toObject=()=>{throw Error('denied source');};Object.defineProperty(denied.item,'name',{get(){throw Error('denied name');}});const {rows,pages}=await all(f);assert.equal(rows.length,1);assert.equal(rows[0].key,'abilities:items:denied');assert.deepEqual(rows[0].raw,[]);assert.deepEqual(rows[0].mapped.value,{status:'denied',target_uuid:null});assert.ok(pages[0].sections[0].reasons.includes('ability_items_denied'));assert.ok(!JSON.stringify(rows).includes('.Item.denied'));f.actor.items.clear();assert.equal((await all(f)).rows.length,0);
});
test('Unicode names retain exact source with bounded codepoint label and continuations stale on relevant changes',async()=>{
 const f=fixture(),first=f.add('first','action','😀'.repeat(300)),second=f.add('second','feat');const {rows}=await all(f),row=rows.find(row=>row.key.endsWith('.first'));assert.equal(row.raw[0].value,'😀'.repeat(300));assert.equal([...row.mapped.value.name].length,256);assert.equal(row.mapped.value.name_truncated,true);
 for(const mutate of [()=>first.stored.name='Changed',()=>second.item.testUserPermission=()=>false,()=>f.actor.items.delete('second')]){second.item.testUserPermission=()=>true;f.actor.items.set('second',second.item);const params={...f.selector,sections:['abilities'],limit:1},page=await readActor(params);assert.ok(page.pagination.next_cursor);mutate();await assert.rejects(readActor({...params,cursor:page.pagination.next_cursor}),code('ContentChanged'));}
});
test('default/source never serialize owned abilities and nonPF2e rejects before Actor source',async()=>{
 const f=fixture(),ability=f.add('a');ability.item.toObject=()=>{throw Error('unselected ability');};await readActor(f.selector);await readActor({...f.selector,sections:['source']});const before=f.reads;game.system.id='other';await assert.rejects(readActor({...f.selector,sections:['abilities']}),code('UnsupportedSystem'));assert.equal(f.reads,before);
});
