import test from 'node:test';
import assert from 'node:assert/strict';
import {readActor,getActorTypes} from '../../foundry-module/scripts/actors.js';

function fixture(synthetic=false,type='character') {
 const source={name:'Owner',type,system:{}};
 const actor={documentName:'Actor',uuid:synthetic?'Scene.s.Token.t.Actor.a':'Actor.a',id:'a',name:'Owner',type,folder:null,compendium:null,items:new Map(),testUserPermission:()=>true,toObject:basis=>{assert.equal(basis,true);return structuredClone(source);}};
 const sources=new Map(),docs=new Map([[actor.uuid,actor]]),lookups=[],reads=new Map();
 const grant=(id)=>({id,onDelete:'detach'});
 function add(id,itemType,system={},pf2e={}) {
  const data={name:id==='lore'?'Terrain Lore':id,type:itemType,system:{...system,rules:[{key:'GrantItem',uuid:'Item.never-hydrate',private:'rules_private_sentinel'}]},flags:{pf2e}};
  const item={documentName:'Item',uuid:actor.uuid+'.Item.'+id,id,name:data.name,type:itemType,parent:actor,folder:null,compendium:null,testUserPermission:()=>true,toObject:basis=>{assert.equal(basis,true);reads.set(id,(reads.get(id)??0)+1);return structuredClone(data);}};
  sources.set(id,data);actor.items.set(id,item);docs.set(item.uuid,item);return item;
 }
 add('ancestry','ancestry',{hp:8,boosts:{first:{value:['str','wis'],selected:null}},items:{}});
 add('heritage','heritage',{ancestry:null,traits:{value:['versatile']}});
 add('background','background',{boosts:{first:{value:['str','wis'],selected:null}},trainedSkills:{value:['nature'],lore:['Terrain Lore']},items:{offered:{uuid:'Item.offered',name:'Offered feat',img:'x.webp',level:1}}},{itemGrants:{'lore/~':grant('lore'),feat:grant('feat')}});
 add('class','class',{hp:10,trainedSkills:{value:['nature'],additional:2},keyAbility:{value:['str','dex'],selected:null},items:{future:{uuid:'Item.future',name:'Future feature',img:'x.webp',level:19}}},{itemGrants:{lore:grant('lore'),feat:grant('feat')}});
 add('deity','deity',{category:'deity',spells:{'1':'Item.spell'},attribute:['wis'],weapons:['staff']});
 add('feat','feat',{category:'classfeature',level:{value:19,taken:1}},{grantedBy:grant('background'),rulesSelections:{'choice/~':'Item.offered',number:2}});
 add('lore','lore',{mod:{value:0},proficient:{value:1}},{grantedBy:grant('background')});
 const scene={documentName:'Scene',uuid:'Scene.s',name:'Scene',testUserPermission:()=>true};
 const base={documentName:'Actor',uuid:'Actor.base',id:'base',name:'Base',type:'character',items:new Map(),testUserPermission:()=>true};
 const token={documentName:'Token',uuid:'Scene.s.Token.t',id:'t',name:'Token',parent:scene,actor,baseActor:synthetic?base:actor,isLinked:!synthetic,testUserPermission:()=>true};
 if(synthetic)actor.token=token;docs.set(token.uuid,token);
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map([['a',actor]]),items:new Map()};
 globalThis.foundry={utils:{fromUuid:async uuid=>{lookups.push(uuid);assert.ok(!['Item.offered','Item.future','Item.spell','Item.never-hydrate'].includes(uuid),'definition must remain unhydrated');return docs.get(uuid);}}};
 return {actor,source,sources,reads,lookups,token,base,add,args:synthetic?{token_uuid:token.uuid}:{actor_uuid:actor.uuid}};
}
async function all(f,limit=17) {
 let cursor,last,rows=[];
 do {last=await readActor({...f.args,sections:['build','effective'],limit,max_bytes:12000,...(cursor?{cursor}:{})});rows.push(...last.records);cursor=last.pagination.next_cursor;}while(cursor);
 assert.equal(last.sections[1].status,'unsupported');assert.equal(new Set(rows.map(r=>r.key)).size,rows.length);
 return {rows,last};
}
const field=(rows,id,path)=>rows.find(r=>r.raw[0]?.document_uuid.endsWith('.Item.'+id)&&r.raw[1]?.path===path&&r.kind==='field');
const claims=rows=>rows.filter(r=>r.mapped.concept==='build_grant_claim');

test('Build keeps seven actual owned contributors, typed source and multi-granter claims in world and synthetic contexts',async()=>{
 for(const synthetic of [false,true]) {
  const f=fixture(synthetic),before=JSON.stringify([...f.sources]),{rows,last}=await all(f);
  const owned=rows.filter(r=>r.mapped.concept==='build_item');assert.equal(owned.length,7);
  assert.deepEqual(new Set(owned.map(r=>r.mapped.value.target_uuid)),new Set([...f.actor.items.values()].map(i=>i.uuid)));
  for(const row of owned) {assert.equal(row.raw[0].path,'/name');assert.equal(row.raw[1].path,'/type');assert.equal(row.mapped.value.name,row.raw[0].value);if(synthetic)assert.equal(row.mapped.value.token_uuid,f.token.uuid);}
  for(const row of rows.filter(r=>r.kind==='field')) {assert.equal(row.raw[0].path,'/type');assert.equal(row.raw[0].document_uuid,row.raw[1].document_uuid);assert.equal(row.provenance.contributors.length,2);}
  assert.equal(field(rows,'heritage','/system/ancestry').raw[1].value,null);
  assert.equal(field(rows,'background','/system/boosts/first/selected').mapped.value,null);
  assert.deepEqual(field(rows,'feat','/system/category').mapped.value,{code:'classfeature',kind:'feature'});
  assert.equal(field(rows,'feat','/system/level/value').raw[1].value,19);assert.equal(field(rows,'feat','/system/level/taken').raw[1].value,1);
  assert.equal(field(rows,'class','/system/items/future/level').raw[1].value,19);
  assert.equal(field(rows,'deity','/system/spells/1').raw[1].value,'Item.spell');
  assert.equal(field(rows,'feat','/flags/pf2e/rulesSelections/choice~1~0').raw[1].value,'Item.offered');
  for(const id of ['background','class'])assert.equal(field(rows,id,'/system/trainedSkills/value/0').raw[1].value,'nature');
  assert.equal(field(rows,'background','/flags/pf2e/itemGrants/lore~1~0/id').provenance.mapping,'pf2e.build.grants.v1');
  assert.equal(field(rows,'background','/system/trainedSkills/value/0').provenance.mapping,'pf2e.background.source.v1');
  const outgoing=claims(rows);assert.equal(outgoing.length,4);
  for(const id of ['feat','lore']) {const links=outgoing.filter(r=>r.mapped.value.target_uuid===f.actor.items.get(id).uuid);assert.equal(links.length,2);assert.deepEqual(new Set(links.map(r=>r.mapped.value.reciprocity)),new Set(['agree','disagree']));for(const row of links){assert.equal(row.raw.length,3);assert.equal(row.raw[2].path,'/flags/pf2e/grantedBy/id');assert.equal(row.raw[2].document_uuid,f.actor.items.get(id).uuid);}}
  assert.ok(rows.filter(r=>r.mapped.concept==='build_granted_by_claim').every(r=>r.mapped.value.reciprocity==='not_evaluated'));
  assert.ok(!JSON.stringify(rows).includes('rules_private_sentinel'));assert.ok(!JSON.stringify(rows).includes('replacement'));assert.equal(JSON.stringify([...f.sources]),before);assert.equal(last.sections[0].status,'complete');
 }
});

test('Build claims use exact local IDs, retain absent reciprocity and withhold denied identities',async()=>{
 const f=fixture(true);delete f.sources.get('lore').flags.pf2e.grantedBy;
 f.sources.get('background').flags.pf2e.itemGrants={absent:{id:'lore',onDelete:'detach'},missing:{id:'gone',onDelete:'detach'},denied:{id:'secret',onDelete:'detach'},unsupported:{id:'weird',onDelete:'detach'}};
 const secret=f.add('secret','feat');secret.name='Denied private name';secret.testUserPermission=()=>false;secret.toObject=()=>{throw Error('denied source read');};f.add('weird','unsupported');
 f.base.items.set('gone',{id:'gone',name:'Must not substitute base'});
 const {rows,last}=await all(f),outgoing=claims(rows),byId=id=>outgoing.find(r=>r.raw[1].value===id);
 assert.equal(byId('lore').mapped.value.reciprocity,'absent');assert.equal(byId('lore').raw[2].path,'/flags/pf2e/grantedBy');assert.equal(byId('lore').raw[2].present,false);
 for(const [id,status]of [['gone','missing'],['secret','denied'],['weird','unsupported']])assert.deepEqual(byId(id).mapped.value,{status,target_uuid:null,reciprocity:'not_evaluated'});
 assert.ok(!JSON.stringify(rows).includes(secret.uuid));assert.ok(!JSON.stringify(rows).includes('Denied private name'));assert.ok(last.sections[0].reasons.includes('build_items_denied'));assert.equal(last.sections[0].status,'partial');
});

test('Build unsupported recorded selection values make source partial without exposing nested content',async()=>{
 const f=fixture();f.sources.get('feat').flags.pf2e.rulesSelections.complex={secret:'selection_private_sentinel'};
 const {rows,last}=await all(f);assert.equal(last.sections[0].status,'partial');assert.ok(last.sections[0].reasons.includes('unsupported_selection_values'));assert.ok(!JSON.stringify(rows).includes('selection_private_sentinel'));assert.ok(!field(rows,'feat','/flags/pf2e/rulesSelections/complex'));assert.equal(field(rows,'feat','/flags/pf2e/rulesSelections/number').raw[1].value,2);
});

test('Build uses persisted donor names and rejects malformed typed source',async()=>{
 const f=fixture();f.actor.items.get('class').name='Prepared display name';
 const page=await readActor({...f.args,sections:['build'],limit:1});assert.ok(page.pagination.next_cursor);
 assert.equal(f.reads.size,7);
 const {rows}=await all(f);assert.equal(rows.find(r=>r.mapped.concept==='build_item'&&r.mapped.value.type==='class').mapped.value.name,'class');
 f.sources.get('class').system.hp='10';await assert.rejects(readActor({...f.args,sections:['build']}),e=>e.rpcError.code==='ReadFailed');
 f.sources.get('class').system.hp=10;f.sources.get('class').type='background';await assert.rejects(readActor({...f.args,sections:['build']}),e=>e.rpcError.code==='ReadFailed');
});

test('Build continuations revalidate source, source names, permissions, membership and inverse grant evidence',async()=>{
 for(const change of ['source','name','permission','membership','grant']) {
  const f=fixture(),first=await readActor({...f.args,sections:['build'],limit:1});assert.ok(first.pagination.next_cursor);
  if(change==='source')f.sources.get('class').system.hp=12;
  if(change==='name')f.sources.get('class').name='Renamed source';
  if(change==='permission')f.actor.items.get('lore').testUserPermission=()=>false;
  if(change==='membership')f.actor.items.delete('lore');
  if(change==='grant')f.sources.get('lore').flags.pf2e.grantedBy.id='class';
  await assert.rejects(readActor({...f.args,sections:['build'],limit:1,cursor:first.pagination.next_cursor}),e=>e.rpcError.code==='ContentChanged');
 }
});

test('Build type and system boundaries remain explicit and discovery is source only',async()=>{
 for(const type of ['npc','familiar']) {const f=fixture(false,type),{rows,last}=await all(f);assert.equal(rows.length,0);assert.equal(last.sections[0].status,'unsupported');}
 const f=fixture();game.system.id='other';await assert.rejects(readActor({...f.args,sections:['build']}),e=>e.rpcError.code==='UnsupportedSystem');
 fixture();const build=(await getActorTypes()).actor_sections.find(r=>r.name==='build');assert.equal(build.source_supported,true);assert.equal(build.mapped_supported,true);assert.equal(build.effective_supported,false);
});

test('Build enforces owner count and aggregate emitted-record bounds before pagination',async()=>{
 const f=fixture();for(let i=0;i<12000;i++)f.add('extra'+i,'equipment');
 await assert.rejects(readActor({...f.args,sections:['build'],limit:1}),e=>e.rpcError.code==='ReadFailed');
 const g=fixture();g.sources.get('class').system.items=Object.fromEntries(Array.from({length:6000},(_,i)=>[String(i),{uuid:'Item.future',name:'Future',img:'x.webp',level:20}]));
 await assert.rejects(readActor({...g.args,sections:['build'],limit:1}),e=>e.rpcError.code==='ReadFailed');
});
