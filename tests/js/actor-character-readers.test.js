import test from 'node:test';
import assert from 'node:assert/strict';
import {readActor} from '../../foundry-module/scripts/actors.js';

function fixture(context='world'){
 const source={name:'Character',type:'character',system:{abilities:null,details:{level:{value:3},languages:{value:['common','custom'],details:'secret language notes'},biography:{appearance:'<p>Exact 🙂 &amp; @UUID[Actor.x]</p>',backstory:'excluded secret',edicts:[],anathema:[],visibility:{appearance:true,backstory:false,personality:false,campaign:false}}},attributes:{hp:{value:0,temp:0,max:999}},skills:{athletics:{rank:2,total:999}},resources:{focus:{value:0,max:999},heroPoints:{value:1,max:3}},build:{attributes:{manual:false,boosts:{1:['str','custom']},apex:null}}}};
 const docs=new Map();let permitted=true,writes=0;
 const actor={documentName:'Actor',uuid:'Actor.a',id:'a',name:'Character',type:'character',items:new Map(),folder:null,compendium:null,testUserPermission:()=>permitted,toObject(flag){assert.equal(flag,true);return structuredClone(source);},update(){writes++;throw Error('unexpected write');},prepareData(){throw Error('unexpected preparation');}};
 let selector={actor_uuid:actor.uuid};
 let scene,token,base;
 if(context==='pack'){actor.uuid='Compendium.pf2e.example.Actor.a';actor.compendium={collection:'pf2e.example',title:'Examples',testUserPermission:()=>permitted};selector={actor_uuid:actor.uuid};}
 if(context==='token'){
  base={documentName:'Actor',id:'base',uuid:'Actor.base',name:'Base',type:'character',testUserPermission:()=>true};
  scene={documentName:'Scene',id:'s',uuid:'Scene.s',name:'Scene',testUserPermission:()=>true};
  token={documentName:'Token',id:'t',uuid:'Scene.s.Token.t',name:'Token',parent:scene,actor,baseActor:base,isLinked:false,testUserPermission:()=>true};
  actor.uuid='Scene.s.Token.t.Actor.a';docs.set(scene.uuid,scene);docs.set(token.uuid,token);selector={token_uuid:token.uuid};
 }
 docs.set(actor.uuid,actor);
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map([['a',actor],...(base?[['base',base]]:[])]),items:new Map()};
 globalThis.foundry={utils:{fromUuid:async uuid=>docs.get(uuid)}};
 return {source,actor,selector,scene,token,setPermission(value){permitted=value;},get writes(){return writes;}};
}
async function pages(selector,sections,options={}){let cursor;const result=[];do{const page=await readActor({...selector,sections,limit:5,max_bytes:8000,...options,...(cursor?{cursor}:{})});assert.ok(Buffer.byteLength(JSON.stringify(page))<=8000);result.push(page);cursor=page.pagination.next_cursor;assert.ok(result.length<200);}while(cursor);return result;}
const field=(rows,path)=>rows.find(r=>r.raw[0]?.path===path);

test('character source reads retain world pack and synthetic context with rank and nullable provenance',async()=>{
 for(const context of ['world','pack','token']){
  const f=fixture(context),before=JSON.stringify(f.source),result=await pages(f.selector,['source','effective']),rows=result.flatMap(p=>p.records);
  assert.ok(result.every(p=>p.sections.find(s=>s.name==='source').status!=='unsupported'&&p.sections.find(s=>s.name==='effective').status==='unsupported'));
  const attributes=field(rows,'/system/abilities'),rank=field(rows,'/system/skills/athletics/rank');
  assert.equal(attributes.raw[0].value,null);assert.equal(attributes.mapped.value,null);
  assert.deepEqual(rank.mapped.value,{rank:2,label:'Expert'});assert.equal(rank.raw[0].value,2);assert.ok(rank.provenance.limitations.includes('rank_not_total_check_modifier'));
  for(const record of rows.filter(r=>r.provenance.mapping==='pf2e.character.source.v1')){assert.equal(record.raw[0].document_uuid,f.actor.uuid);assert.equal(record.raw[0].basis,'source');assert.deepEqual(record.provenance.contributors,[{document_uuid:f.actor.uuid,path:record.raw[0].path,basis:'source'}]);assert.ok(record.provenance.limitations.includes('character_source_not_effective_statistics'));}
  assert.ok(!rows.some(r=>r.raw[0]?.path==='/system/attributes/hp/max'||r.raw[0]?.path==='/system/resources/focus/max'||r.raw[0]?.path.endsWith('/total')));
  assert.ok(!JSON.stringify(rows).includes('excluded secret'));assert.equal(JSON.stringify(f.source),before);assert.equal(f.writes,0);
  assert.equal(result[0].identity.source_kind,context==='pack'?'compendium':context);
  if(context==='pack')assert.equal(result[0].identity.pack.id,'pf2e.example');
  if(context==='token'){assert.equal(result[0].identity.instance.token_uuid,f.token.uuid);assert.equal(result[0].identity.instance.base_actor.uuid,'Actor.base');assert.equal(result[0].identity.instance.actor_link,false);}
 }
});
test('default character reading excludes biography and source changes preserve source immutability',async()=>{
 const f=fixture(),before=JSON.stringify(f.source),page=await readActor(f.selector);
 assert.ok(!JSON.stringify(page).includes('excluded secret'));assert.ok(!JSON.stringify(page).includes('secret language notes'));
 assert.equal(page.sections.find(s=>s.name==='source').status,'complete');assert.equal(JSON.stringify(f.source),before);assert.equal(f.writes,0);
});
test('explicit character biography fragments preserve UTF16 offsets exact text and empty list markers',async()=>{
 const f=fixture();f.source.system.details.biography.backstory='<p>\n🙂 &amp; " \\ \u0000 @UUID[Actor.x]</p>'.repeat(450);
 f.source.system.details.biography.edicts=['help','help'];const before=JSON.stringify(f.source);
 const result=await pages(f.selector,['description'],{limit:2}),rows=result.flatMap(p=>p.records);
 const path='/system/details/biography/backstory',fragments=rows.filter(r=>r.raw[0].path===path);let text='';
 assert.ok(fragments.length>1);
 for(const fragment of fragments){assert.equal(fragment.kind,'text');assert.equal(fragment.mapped.value,null);assert.equal(fragment.text.start,text.length);text+=fragment.raw[0].value;assert.equal(fragment.text.end,text.length);assert.ok(fragment.raw[0].value.length<=6000);assert.equal(fragment.provenance.mapping,'pf2e.character.notes.v1');assert.deepEqual(fragment.provenance.limitations,['character_source_not_effective_statistics']);}
 assert.equal(text,f.source.system.details.biography.backstory);assert.equal(fragments.at(-1).text.complete,true);
 assert.equal(field(rows,'/system/details/biography/edicts/1').raw[0].value,'help');
 const empty=field(rows,'/system/details/biography/anathema');assert.equal(empty.kind,'field');assert.deepEqual(empty.raw[0].value,[]);assert.equal(empty.raw[0].present,true);
 assert.equal(field(rows,'/system/details/languages/details').raw[0].value,'secret language notes');
 assert.equal(JSON.stringify(f.source),before);assert.equal(f.writes,0);
 f.source.system.details.biography.edicts=[];
 const emptyRows=(await pages(f.selector,['description'])).flatMap(p=>p.records);
 for(const key of ['edicts','anathema']){const marker=field(emptyRows,`/system/details/biography/${key}`);assert.equal(marker.kind,'field');assert.deepEqual(marker.raw[0].value,[]);assert.equal(marker.provenance.mapping,'pf2e.character.notes.v1');}
});
test('character continuation detects source biography permission and identity changes',async()=>{
 for(const change of ['source','biography','permission','identity']){
  const f=fixture(),sections=['source','description'];const first=await readActor({...f.selector,sections,limit:1});assert.ok(first.pagination.next_cursor);
  if(change==='source')f.source.system.attributes.hp.value=12;
  if(change==='biography')f.source.system.details.biography.backstory+='changed';
  if(change==='permission')f.setPermission(false);
  if(change==='identity')f.actor.name='Changed identity';
  await assert.rejects(readActor({...f.selector,sections,limit:1,cursor:first.pagination.next_cursor}),e=>e.rpcError.code===(change==='permission'?'PermissionDenied':'ContentChanged'));
 }
});
test('malformed selected character source fails safely and unsupported gates stay explicit',async()=>{
 for(const mutate of [s=>s.system.skills.athletics.rank=9,s=>s.system.abilities={str:{mod:'private-secret'}},s=>s.system.details.biography.backstory={secret:'private-secret'},s=>s.system.build.attributes.boosts[1]=Array(12001).fill('str')]){
  const f=fixture();mutate(f.source);await assert.rejects(readActor({...f.selector,sections:['source','description']}),e=>e.rpcError.code==='ReadFailed'&&!e.message.includes('private-secret'));
 }
 const f=fixture();game.system.id='other';await assert.rejects(readActor(f.selector),e=>e.rpcError.code==='UnsupportedSystem');game.system.id='pf2e';game.user.isGM=false;await assert.rejects(readActor(f.selector),e=>e.rpcError.code==='PermissionDenied');
});
test('character reader input limits fail before source expansion',async()=>{
 const f=fixture();f.actor.toObject=()=>{throw Error('must not read');};
 for(const options of [{limit:0},{limit:101},{max_bytes:7999},{max_bytes:48001},{limit:true}])await assert.rejects(readActor({...f.selector,...options}),e=>e.rpcError.code==='InvalidRequest');
});
