import test from 'node:test';
import assert from 'node:assert/strict';
import {readActor} from '../../foundry-module/scripts/actors.js';

function fixture(context='world'){
 const source={name:'Familiar',type:'familiar',system:{master:{id:'master',ability:'int'},attributes:{hp:{value:3,temp:0}}}};
 const current={name:'Familiar',type:'familiar',system:{attributes:{ac:{value:20,breakdown:'Selected AC',details:''},hp:{value:5,max:25,temp:1}},saves:Object.fromEntries(['fortitude','reflex','will'].map(save=>[save,{value:10,totalModifier:11,breakdown:'Selected save'}])),perception:{value:8,totalModifier:9,breakdown:'Selected Perception',vision:true},movement:{speeds:Object.fromEntries(['land','burrow','climb','fly','swim','travel'].map(mode=>[mode,['land','travel'].includes(mode)?{value:25,base:20,type:mode,source:null}:null]))},skills:{acrobatics:{slug:'acrobatics',label:'Acrobatics',value:6,totalModifier:7,dc:18,breakdown:'Selected skill',lore:false,itemId:null}}}};
 const calls=[],docs=new Map();let allowed=true,masterLookups=0,race=null;
 const master={documentName:'Actor',id:'master',uuid:'Actor.master',name:'Master',type:'character',items:new Map(),folder:null,compendium:null,testUserPermission:()=>allowed,toObject(){throw Error('master source must not be read');}};
 const actor={documentName:'Actor',id:'f',uuid:'Actor.f',name:'Familiar',type:'familiar',items:new Map(),folder:null,compendium:null,testUserPermission:()=>true,toObject(flag){calls.push(flag);return flag?structuredClone(source):current;},prepareData(){throw Error('preparation prohibited');},update(){throw Error('writes prohibited');}};
 Object.defineProperty(actor,'master',{get(){throw Error('master getter prohibited');}});Object.defineProperty(actor,'system',{get(){throw Error('runtime system prohibited');}});
 if(context==='pack'){actor.uuid='Compendium.pf2e.example.Actor.f';actor.compendium={collection:'pf2e.example',title:'Examples',testUserPermission:()=>true};}
 let selector={actor_uuid:actor.uuid};
 if(context==='token'){const scene={documentName:'Scene',uuid:'Scene.s',name:'Scene',testUserPermission:()=>true};const token={documentName:'Token',uuid:'Scene.s.Token.t',name:'Token',parent:scene,actor,baseActor:null,isLinked:false,testUserPermission:()=>true};actor.uuid='Scene.s.Token.t.Actor.f';docs.set(token.uuid,token);selector={token_uuid:token.uuid};}
 docs.set(actor.uuid,actor);docs.set(master.uuid,master);
 const actors=new Map([['f',actor],['master',master]]),get=actors.get.bind(actors);actors.get=id=>{if(id==='master')masterLookups++;return get(id);};
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors,items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>{if(uuid===master.uuid&&race){const callback=race;race=null;callback();}return docs.get(uuid);}}};
 return {source,current,actor,master,selector,calls,docs,setPermission(value){allowed=value;},setRace(callback){race=callback;},get masterLookups(){return masterLookups;}};
}
async function all(f,sections=['statistics']){const rows=[],pages=[];let cursor;do{const page=await readActor({...f.selector,sections,limit:3,max_bytes:8000,...(cursor?{cursor}:{})});rows.push(...page.records);pages.push(page);assert.ok(Buffer.byteLength(JSON.stringify(page))<=8000);cursor=page.pagination.next_cursor;assert.ok(pages.length<150);}while(cursor);return {rows,pages};}
const code=expected=>error=>error.rpcError?.code===expected;

test('world/pack/token familiar current statistics preserve source/master separation and bounded provenance',async()=>{
 for(const context of ['world','pack','token']){const f=fixture(context),before=JSON.stringify(f.source),result=await all(f,['source','statistics']);assert.ok(result.pages.length>1);const rows=result.rows,current=rows.find(row=>row.key==='statistics:/system/attributes/hp/value'),source=rows.find(row=>row.section==='source'&&row.raw[0]?.path==='/system/attributes/hp/value');assert.equal(source.raw[0].value,3);assert.equal(source.raw[0].basis,'source');assert.equal(current.raw[0].value,5);assert.equal(current.raw[0].basis,'transformed');assert.equal(current.provenance.mapping,'pf2e.familiar.current.v1');assert.equal(current.raw[0].document_uuid,f.actor.uuid);assert.deepEqual(current.provenance.limitations,['serialized_familiar_value_not_recalculated']);
  const master=rows.find(row=>row.key==='statistics:familiar_master');assert.equal(master.mapped.value.target_uuid,f.master.uuid);assert.deepEqual(master.raw.map(raw=>raw.path),['/system/master/id','/system/master/ability']);assert.ok(master.raw.every(raw=>raw.basis==='source'&&raw.document_uuid===f.actor.uuid));assert.ok(!rows.some(row=>/\/abilities\/|\/attack(?:\/|$)/.test(row.raw[0]?.path??'')));assert.ok(f.calls.includes(false));assert.equal(JSON.stringify(f.source),before);assert.ok(result.pages.every(page=>page.sections.find(section=>section.name==='statistics').status==='partial'));if(context==='token')assert.ok(result.pages.every(page=>page.identity.instance.token_uuid===f.selector.token_uuid));
 }
});
test('unresolved master states return only source context without current serialization',async()=>{
 for(const [change,status]of [[f=>delete f.source.system.master.id,'missing'],[f=>f.source.system.master.id=null,'unassociated'],[()=>game.actors.delete('master'),'missing'],[f=>f.setPermission(false),'denied'],[f=>f.master.type='npc','unsupported']]){const f=fixture();change(f);const result=await all(f);assert.ok(f.calls.every(flag=>flag===true));assert.equal(result.rows.length,1);assert.deepEqual(result.rows[0].mapped.value,{status,target_uuid:null});assert.ok(result.pages[0].sections[0].reasons.includes('familiar_master_'+status));}
});
test('current-only values and selected master context changes invalidate continuations',async()=>{
 for(const change of [f=>f.current.system.attributes.hp.max++,f=>f.current.system.skills.acrobatics.totalModifier++,f=>f.source.system.master.id=null,f=>f.source.system.master.ability='wis',f=>f.master.name='Renamed',f=>f.setPermission(false)]){const f=fixture(),params={...f.selector,sections:['statistics'],limit:1},first=await readActor(params);assert.ok(first.pagination.next_cursor);change(f);await assert.rejects(readActor({...params,cursor:first.pagination.next_cursor}),code('ContentChanged'));}
});
test('master resolution races never return stale transformed statistics',async()=>{
 const reassigned=fixture();reassigned.setRace(()=>reassigned.source.system.master.id=null);await assert.rejects(readActor({...reassigned.selector,sections:['statistics']}),code('ContentChanged'));
 const denied=fixture();denied.setRace(()=>denied.setPermission(false));const result=await readActor({...denied.selector,sections:['statistics']});assert.ok(denied.calls.every(flag=>flag===true));assert.ok(!result.records.some(row=>row.provenance.mapping==='pf2e.familiar.current.v1'));assert.equal(result.records[0].mapped.value.status,'denied');
});
test('familiar or GM permission loss during resolution prevents transformed serialization',async()=>{
 for(const change of [f=>f.actor.testUserPermission=()=>false,()=>game.user.isGM=false]){
  const f=fixture();f.setRace(()=>change(f));
  await assert.rejects(readActor({...f.selector,sections:['statistics']}),code('PermissionDenied'));
  assert.ok(f.calls.every(flag=>flag===true));
 }
});
test('source avoids master/current reads, defaults retain source basis and Item-linked skills reveal no metadata',async()=>{
 const sourceOnly=fixture();await readActor({...sourceOnly.selector,sections:['source']});assert.equal(sourceOnly.masterLookups,0);assert.ok(sourceOnly.calls.every(flag=>flag===true));
 const defaults=fixture();const defaultResult=await readActor(defaults.selector);assert.ok(defaults.calls.every(flag=>flag===true));assert.ok(!defaultResult.records.some(row=>row.provenance.mapping==='pf2e.familiar.current.v1'));
 const f=fixture();f.current.system.skills={SECRET_KEY:{lore:true,itemId:'secret'}};Object.defineProperty(f.current.system.skills.SECRET_KEY,'label',{get(){throw Error('private label');}});const result=await all(f);assert.ok(!JSON.stringify(result).includes('SECRET_KEY'));assert.ok(result.pages.every(page=>page.sections[0].reasons.includes('familiar_item_linked_skills_unsupported')));
});
