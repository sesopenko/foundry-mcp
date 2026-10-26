import test from 'node:test';
import assert from 'node:assert/strict';
import {readActor} from '../../foundry-module/scripts/actors.js';

function fixture(context='world',type='character'){
 const docs=new Map(),calls=[];
 const source={name:'Creature',type,system:{skills:{athletics:type==='npc'?{base:null,note:'Authored qualifier'}:{rank:1}}}};
 const skill={slug:'athletics',label:'Athletics',attribute:'str',value:12,totalModifier:13,dc:24,breakdown:'Serialized explanation',lore:false,itemId:null,rank:2,armor:true,base:10,mod:14,visible:true,note:'Only while swimming'};
 const current={name:'Creature',type,system:{skills:{athletics:{...skill},'sailing/lore~':{...skill,slug:'sailing-lore',label:'Sailing Lore',lore:true,itemId:'second',attribute:'int'}}}};
 const actor={documentName:'Actor',id:'a',uuid:'Actor.a',name:'Creature',type,items:new Map(),folder:null,compendium:null,testUserPermission:()=>true,toObject(flag){calls.push(flag);if(type==='familiar')assert.equal(flag,true);return structuredClone(flag?source:current);}};
 if(context==='pack'){actor.uuid='Compendium.pf2e.example.Actor.a';actor.compendium={collection:'pf2e.example',title:'Examples',testUserPermission:()=>true};}
 let selector={actor_uuid:actor.uuid};
 if(context==='token'){const scene={documentName:'Scene',uuid:'Scene.s',name:'Scene',testUserPermission:()=>true};const token={documentName:'Token',uuid:'Scene.s.Token.t',name:'Token',parent:scene,actor,baseActor:null,isLinked:false,testUserPermission:()=>true};actor.uuid='Scene.s.Token.t.Actor.a';docs.set(token.uuid,token);selector={token_uuid:token.uuid};}
 const loreSources=new Map();
 for(const id of ['first','second']){const data={name:'Sailing Lore',type:'lore',system:{proficient:{value:1},mod:{value:7}}};const item={documentName:'Item',id,uuid:`${actor.uuid}.Item.${id}`,name:data.name,type:'lore',parent:actor,folder:null,compendium:null,testUserPermission:()=>true,toObject(flag){assert.equal(flag,true);return structuredClone(data);}};actor.items.set(id,item);docs.set(item.uuid,item);loreSources.set(id,data);}
 docs.set(actor.uuid,actor);globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map([['a',actor]]),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>docs.get(uuid)}};
 return {actor,source,current,selector,calls,loreSources};
}
async function all(f,sections=['skills']){const rows=[],pages=[];let cursor;do{const page=await readActor({...f.selector,sections,limit:3,max_bytes:8000,...(cursor?{cursor}:{})});rows.push(...page.records);pages.push(page);assert.ok(Buffer.byteLength(JSON.stringify(page))<=8000);cursor=page.pagination.next_cursor;assert.ok(pages.length<200);}while(cursor);return {rows,pages};}
const code=expected=>error=>error.rpcError?.code===expected;

test('actual world/pack/token skills pagination keeps current values and original source Lore references separate',async()=>{
 for(const context of ['world','pack','token'])for(const type of ['character','npc']){
  const f=fixture(context,type),before=JSON.stringify([f.source,...f.loreSources]),result=await all(f,['source','skills']);assert.ok(result.pages.length>1);assert.equal(new Set(result.rows.map(row=>row.key)).size,result.rows.length);
  const value=result.rows.find(row=>row.key==='skills:current:/system/skills/athletics/value');assert.equal(value.raw[0].value,12);assert.equal(value.raw[0].basis,'transformed');assert.equal(value.raw[0].document_uuid,f.actor.uuid);
  const source=result.rows.find(row=>row.section==='source'&&row.raw[0]?.path===`/system/skills/athletics/${type==='character'?'rank':'base'}`);assert.equal(source.raw[0].basis,'source');assert.equal(source.raw[0].value,type==='character'?1:null);
  const sourceLore=result.rows.filter(row=>row.provenance.mapping==='pf2e.lore.specialty.v1');assert.equal(sourceLore.length,2);assert.equal(new Set(sourceLore.map(row=>row.mapped.value.target_uuid)).size,2);
  const join=result.rows.find(row=>row.key==='skills:current-lore:sailing~1lore~0');assert.equal(join.mapped.value.target_uuid,f.actor.items.get('second').uuid);assert.deepEqual(join.raw.map(raw=>raw.path),['/system/skills/sailing~1lore~0/lore','/system/skills/sailing~1lore~0/itemId']);if(context==='token')assert.equal(join.mapped.value.token_uuid,f.selector.token_uuid);
  assert.ok(result.pages.every(page=>page.sections.find(section=>section.name==='skills').status==='partial'));if(type==='npc'){assert.ok(result.pages[0].sections.find(section=>section.name==='skills').reasons.includes('conditional_skill_variants_not_evaluated'));assert.equal(result.rows.find(row=>row.key==='skills:current:/system/skills/athletics/note').mapped.value,'Only while swimming');}
  assert.equal(JSON.stringify([f.source,...f.loreSources]),before);assert.ok(f.calls.includes(false));
 }
});
test('selected current-only totals and Lore identity/membership/permissions invalidate continuations',async()=>{
 for(const change of [f=>f.current.system.skills.athletics.totalModifier++,f=>f.actor.items.get('second').name='Renamed',f=>f.actor.items.delete('second'),f=>f.actor.items.get('second').testUserPermission=()=>false]){
  const f=fixture(),before=JSON.stringify(f.source),params={...f.selector,sections:['skills'],limit:1},first=await readActor(params);assert.ok(first.pagination.next_cursor);change(f);assert.equal(JSON.stringify(f.source),before);await assert.rejects(readActor({...params,cursor:first.pagination.next_cursor}),code('ContentChanged'));
 }
});
test('denied Lore hides prepared skill keys/labels/totals while preserving independent readable source rows',async()=>{
 const f=fixture();f.current.system.skills={'SECRET_KEY':{...f.current.system.skills.athletics,lore:true,itemId:'second',label:'SECRET_LABEL',value:987654321}};const denied=f.actor.items.get('second');denied.testUserPermission=()=>false;denied.toObject=()=>{throw Error('denied Item source');};const result=await all(f),text=JSON.stringify(result);
 for(const hidden of ['SECRET_KEY','SECRET_LABEL','987654321',denied.uuid])assert.ok(!text.includes(hidden));assert.ok(result.rows.some(row=>row.key==='skills:current:denied'));assert.equal(result.rows.filter(row=>row.provenance.mapping==='pf2e.lore.specialty.v1'&&row.mapped.value.status==='resolved').length,1);assert.ok(result.pages.every(page=>page.sections[0].reasons.includes('current_skill_items_denied')));
});
test('source/default and familiar reads never request transformed skills; unsupported systems reject before serialization',async()=>{
 const defaults=fixture();await readActor(defaults.selector);assert.ok(defaults.calls.every(flag=>flag===true));
 const sourceOnly=fixture();await all(sourceOnly,['source']);assert.ok(sourceOnly.calls.every(flag=>flag===true));
 const familiar=fixture('token','familiar');familiar.source.system={master:{id:null,ability:null},attributes:{hp:{value:0,temp:0}}};const result=await all(familiar);assert.ok(familiar.calls.every(flag=>flag===true));assert.equal(result.rows.filter(row=>row.provenance.mapping==='pf2e.lore.specialty.v1').length,2);assert.ok(!result.rows.some(row=>row.provenance.mapping==='pf2e.actor.skills-current.v1'));
 const other=fixture();game.system.id='other';await assert.rejects(readActor({...other.selector,sections:['skills']}),code('UnsupportedSystem'));assert.deepEqual(other.calls,[]);
});
