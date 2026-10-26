import test from 'node:test';
import assert from 'node:assert/strict';
import {readActor} from '../../foundry-module/scripts/actors.js';
import {creatureSupplementFields} from '../../foundry-module/scripts/actorCreatureCurrent.js';

function fixture(context='world',type='npc'){
 const source={name:'Creature',type,system:{attributes:{ac:{value:15},hp:{value:3,max:20,temp:0}}}};
 const current={name:'Creature',type,system:{attributes:{ac:{value:20,breakdown:'Current AC',details:''},hp:{value:5,max:25,temp:1},immunities:[{type:'custom',source:null,label:'Custom immunity',definition:[],exceptions:[]}],weaknesses:[],resistances:[{type:'fire',source:'Feature',label:'Fire resistance',value:7,exceptions:[{label:'Custom exception',definition:[{and:['a',{not:'b'}]}]}],doubleVs:['cold']}]},perception:{senses:[{type:'darkvision',acuity:'precise',range:Infinity,source:null,label:'Darkvision'}]},details:{languages:{value:['common','custom-language'],details:'Cannot speak while transformed'}}}};
 const docs=new Map(),calls=[];
 const actor={documentName:'Actor',uuid:'Actor.a',id:'a',name:'Creature',type,items:new Map(),folder:null,compendium:null,testUserPermission:()=>true,toObject(flag){calls.push(flag);return flag?structuredClone(source):current;},prepareData(){throw Error('preparation prohibited');},update(){throw Error('writes prohibited');}};
 if(context==='pack'){actor.uuid='Compendium.pf2e.example.Actor.a';actor.compendium={collection:'pf2e.example',title:'Examples',testUserPermission:()=>true};}
 let selector={actor_uuid:actor.uuid};
 if(context==='token'){const scene={documentName:'Scene',uuid:'Scene.s',name:'Scene',testUserPermission:()=>true};const token={documentName:'Token',uuid:'Scene.s.Token.t',name:'Token',parent:scene,actor,baseActor:null,isLinked:false,testUserPermission:()=>true};actor.uuid='Scene.s.Token.t.Actor.a';docs.set(token.uuid,token);selector={token_uuid:token.uuid};}
 docs.set(actor.uuid,actor);globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map([['a',actor]]),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>docs.get(uuid)}};
 return {actor,source,current,selector,calls};
}
async function all(f){const rows=[],pages=[];let cursor;do{const page=await readActor({...f.selector,sections:['statistics'],limit:3,max_bytes:8000,...(cursor?{cursor}:{})});rows.push(...page.records);pages.push(page);assert.ok(Buffer.byteLength(JSON.stringify(page))<=8000);cursor=page.pagination.next_cursor;assert.ok(pages.length<150);}while(cursor);return {rows,pages};}
const code=expected=>error=>error.rpcError?.code===expected;

test('world/pack/token actual current pages preserve encoded senses, language notes and clean IWR predicates',async()=>{
 for(const context of ['world','pack','token'])for(const type of ['character','npc']){const f=fixture(context,type),before=JSON.stringify(f.source),result=await all(f),rows=result.rows.filter(row=>row.provenance.mapping==='pf2e.actor.creature-current.v1');assert.ok(result.pages.length>1);assert.ok(rows.length>20);assert.equal(new Set(result.rows.map(row=>row.key)).size,result.rows.length);
  const range=rows.find(row=>row.raw[0].path==='/system/perception/senses/0/range');assert.deepEqual(range.raw[0].value,{'$number':'Infinity'});assert.deepEqual(range.mapped.value,{'$number':'Infinity'});assert.equal(range.raw[0].basis,'transformed');assert.equal(range.raw[0].document_uuid,f.actor.uuid);assert.deepEqual(range.provenance.limitations,['serialized_creature_details_not_target_context']);
  const predicate=rows.find(row=>row.raw[0].path==='/system/attributes/resistances/0/exceptions/0/definition');assert.deepEqual(predicate.mapped.value,[{and:['a',{not:'b'}]}]);const emptyPredicate=rows.find(row=>row.raw[0].path==='/system/attributes/immunities/0/definition');assert.deepEqual(emptyPredicate.mapped.value,[]);const emptyCollection=rows.find(row=>row.raw[0].path==='/system/attributes/immunities/0/exceptions');assert.deepEqual(emptyCollection.raw[0].value,[]);assert.equal(emptyCollection.mapped.value,null);
  assert.equal(rows.find(row=>row.raw[0].path==='/system/details/languages/details').mapped.value,'Cannot speak while transformed');assert.ok(result.pages.every(page=>page.sections[0].reasons.includes('conditional_iwr_not_evaluated')));assert.equal(JSON.stringify(f.source),before);assert.equal(f.calls.filter(flag=>flag===false).length,result.pages.length*2);if(context==='token')assert.ok(result.pages.every(page=>page.identity.instance.token_uuid===f.selector.token_uuid));
 }
});
test('current-only senses, language notes and IWR definitions invalidate continued reads',async()=>{
 for(const change of [f=>f.current.system.perception.senses[0].range=60,f=>f.current.system.details.languages.details+=' changed',f=>f.current.system.attributes.resistances[0].value++,f=>f.current.system.attributes.immunities[0].definition.push('new-atom')]){const f=fixture(),before=JSON.stringify(f.source),params={...f.selector,sections:['statistics'],limit:1},first=await readActor(params);assert.ok(first.pagination.next_cursor);change(f);assert.equal(JSON.stringify(f.source),before);await assert.rejects(readActor({...params,cursor:first.pagination.next_cursor}),code('ContentChanged'));}
});
test('default/source never serialize supplements and missing custom definitions remain explicit',async()=>{
 for(const sections of [undefined,['source']]){const f=fixture();await readActor({...f.selector,...(sections?{sections}:{})});assert.ok(f.calls.every(flag=>flag===true));}
 const f=fixture();delete f.current.system.attributes.immunities[0].definition;const result=await all(f);const definition=result.rows.find(row=>row.raw[0]?.path==='/system/attributes/immunities/0/definition');assert.equal(definition.raw[0].present,false);assert.equal(definition.mapped.value,null);assert.ok(result.pages.every(page=>page.sections[0].reasons.includes('custom_iwr_definition_unavailable')));
});
test('actual supplements reject malformed arrays/null ranges/predicates and selected accessors without invocation',async()=>{
 for(const change of [f=>f.current.system.details.languages=Object.assign([],{value:[],details:'bad'}),f=>f.current.system.perception.senses[0].range=null,f=>f.current.system.attributes.immunities[0].definition=[{unknown:'a'}]]){const f=fixture();change(f);await assert.rejects(readActor({...f.selector,sections:['statistics']}),code('ReadFailed'));}
 const f=fixture();let calls=0;Object.defineProperty(f.current.system.perception.senses[0],'range',{get(){calls++;return Infinity;}});await assert.rejects(readActor({...f.selector,sections:['statistics']}),code('ReadFailed'));assert.equal(calls,0);
});
test('the combined core and supplement field budget rejects snapshots that individually fit',async()=>{
 const f=fixture();f.current.system.perception.senses=[];f.current.system.details.languages={value:[],details:''};f.current.system.attributes.immunities=Array.from({length:118},()=>({type:'fire',source:null,label:'Fire',exceptions:Array(200).fill('cold')}));f.current.system.attributes.weaknesses=[];f.current.system.attributes.resistances=[];assert.ok(creatureSupplementFields(f.current).fields.length<24000);await assert.rejects(readActor({...f.selector,sections:['statistics']}),code('ReadFailed'));
});
