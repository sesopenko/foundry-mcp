import test from 'node:test';
import assert from 'node:assert/strict';
import {readActor} from '../../foundry-module/scripts/actors.js';

function fixture(){
 const source={name:'Familiar',type:'familiar',system:{master:{id:'master',ability:'unknown-code'},attributes:{hp:{value:0,temp:0,max:999}},details:{creature:{value:'<p>Exact 🙂 &amp; @UUID[Actor.x]</p>'}},traits:{value:['prepared']},skills:{acrobatics:999},saves:{will:999}}};
 const docs=new Map();let masterAllowed=true,lookups=0;
 const master={documentName:'Actor',id:'master',uuid:'Actor.master',name:'Master',type:'character',items:new Map(),folder:null,compendium:null,testUserPermission:()=>masterAllowed,toObject(){throw Error('master source must not be expanded');}};
 const actor={documentName:'Actor',id:'f',uuid:'Actor.f',name:'Familiar',type:'familiar',items:new Map(),folder:null,compendium:null,testUserPermission:()=>true,toObject(flag){assert.equal(flag,true,'no transformed current fallback');return structuredClone(source);},get master(){throw Error('must not use master getter');},prepareData(){throw Error('must not prepare');},update(){throw Error('must not write');}};
 docs.set(actor.uuid,actor);docs.set(master.uuid,master);
 const actors=new Map([['f',actor],['master',master]]);const get=actors.get.bind(actors);actors.get=id=>{if(id==='master')lookups++;return get(id);};
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors,items:new Map()};
 globalThis.foundry={utils:{fromUuid:async uuid=>docs.get(uuid)}};
 function action(id,traits=[]){const data={name:'Ability '+id,type:'action',system:{traits:{value:traits}}};const item={documentName:'Item',id,uuid:`Actor.f.Item.${id}`,name:data.name,type:'action',parent:actor,folder:null,compendium:null,testUserPermission:()=>true,toObject:flag=>{assert.equal(flag,true);return structuredClone(data);}};actor.items.set(id,item);docs.set(item.uuid,item);return {item,data};}
 return {source,actor,master,action,docs,setMasterPermission(value){masterAllowed=value;},get lookups(){return lookups;}};
}
async function pages(sections,options={}){let cursor;const result=[];do{const page=await readActor({actor_uuid:'Actor.f',sections,limit:1,max_bytes:8000,...options,...(cursor?{cursor}:{})});assert.ok(Buffer.byteLength(JSON.stringify(page))<=8000);result.push(page);cursor=page.pagination.next_cursor;assert.ok(result.length<200);}while(cursor);return result;}
const byPath=(rows,path)=>rows.find(row=>row.raw[0]?.path===path);

test('familiar source pagination preserves selected source and never resolves master or current statistics',async()=>{
 const f=fixture(),before=JSON.stringify(f.source),result=await pages(['source','effective']),rows=result.flatMap(page=>page.records);
 assert.equal(f.lookups,0);assert.equal(result[0].identity.uuid,'Actor.f');
 const hp=byPath(rows,'/system/attributes/hp/value');assert.equal(hp.raw[0].value,0);assert.equal(hp.raw[0].basis,'source');assert.equal(hp.provenance.mapping,'pf2e.familiar.source.v1');
 assert.equal(byPath(rows,'/system/master/ability').mapped.value,'unknown-code');
 assert.ok(!rows.some(row=>/\/hp\/max|\/skills\/|\/saves\/|\/traits\//.test(row.raw[0]?.path??'')));
 assert.ok(result.every(page=>page.sections.filter(section=>section.name==='effective').every(section=>section.status==='unsupported')));
 assert.equal(JSON.stringify(f.source),before);
});
test('explicit familiar description fragments reconstruct exact source with stable offsets',async()=>{
 const f=fixture();f.source.system.details.creature.value='<p>🙂 &amp; exact</p>'.repeat(600);
 const rows=(await pages(['description'])).flatMap(page=>page.records);let text='';
 for(const row of rows){assert.equal(row.raw[0].path,'/system/details/creature/value');assert.equal(row.text.start,text.length);text+=row.raw[0].value;assert.equal(row.text.end,text.length);assert.equal(row.provenance.mapping,'pf2e.familiar.notes.v1');}
 assert.equal(text,f.source.system.details.creature.value);assert.equal(rows.at(-1).text.complete,true);assert.equal(f.lookups,0);
});
test('identity master statuses distinguish resolved absent null denied unsupported and unverified',async()=>{
 for(const status of ['resolved','missing','unassociated','denied','unsupported','unverified']){
  const f=fixture();
  if(status==='missing')delete f.source.system.master.id;
  if(status==='unassociated')f.source.system.master.id=null;
  if(status==='denied')f.setMasterPermission(false);
  if(status==='unsupported')f.master.type='npc';
  if(status==='unverified')f.master.uuid='Compendium.example.Actor.master';
  const rows=(await pages(['identity'])).flatMap(page=>page.records),relation=rows.find(row=>row.provenance.mapping==='pf2e.familiar.master.v1');
  assert.equal(relation.mapped.value.status,status);
  if(status==='resolved'){assert.equal(relation.mapped.value.name,'Master');assert.deepEqual(relation.mapped.value.next_call,{tool:'read_actor',arguments:{actor_uuid:'Actor.master'}});}
  else{assert.equal(relation.mapped.value.target_uuid,null);assert.ok(!Object.hasOwn(relation.mapped.value,'name'));}
 }
});
test('actual owned actions remain separate unclassified references regardless of familiar or master trait labels',async()=>{
 const f=fixture();f.action('one',['familiar','custom']);f.action('two',['master']);f.action('three',[]);
 const result=await pages(['abilities']),rows=result.flatMap(page=>page.records);
 assert.equal(rows.length,3);assert.equal(new Set(rows.map(row=>row.mapped.value.target_uuid)).size,3);
 assert.ok(rows.every(row=>row.mapped.value.ability_kind==='unclassified'&&row.provenance.mapping==='pf2e.familiar.ability.v1'));
 assert.ok(result.every(page=>page.sections[0].status==='partial'&&page.sections[0].reasons.includes('other_abilities_pending')));assert.equal(f.lookups,0);
});
test('deleted master and denied owned abilities retain unresolved evidence without exposing target identity',async()=>{
 const f=fixture();game.actors.delete('master');
 const denied=f.action('secret',['master']);denied.item.testUserPermission=()=>false;denied.item.toObject=()=>{throw Error('denied source must not be read');};
 const result=await pages(['identity','abilities']),rows=result.flatMap(page=>page.records);
 const master=rows.find(row=>row.provenance.mapping==='pf2e.familiar.master.v1');assert.equal(master.mapped.value.status,'missing');assert.equal(master.raw[0].value,'master');
 const ability=rows.find(row=>row.provenance.mapping==='pf2e.familiar.ability.v1');assert.deepEqual(ability.raw,[]);assert.deepEqual(ability.mapped.value,{status:'denied',target_uuid:null});
 assert.ok(!JSON.stringify(result).includes('Item.secret'));assert.ok(!JSON.stringify(result).includes('Ability secret'));
 assert.ok(result.every(page=>page.sections.find(section=>section.name==='abilities').reasons.includes('related_items_denied')));
});
test('continuations invalidate selected master identity permission and owned action changes',async()=>{
 for(const change of ['rename','permission','action']){
  const f=fixture(),ability=f.action('one',['custom']);f.action('two',[]);
  const sections=['identity','abilities','source'];const first=await readActor({actor_uuid:'Actor.f',sections,limit:1});assert.ok(first.pagination.next_cursor);
  if(change==='rename')f.master.name='Changed master';
  if(change==='permission')f.setMasterPermission(false);
  if(change==='action')ability.data.system.traits.value.push('changed');
  await assert.rejects(readActor({actor_uuid:'Actor.f',sections,limit:1,cursor:first.pagination.next_cursor}),error=>error.rpcError.code==='ContentChanged');
 }
});
