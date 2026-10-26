import test from 'node:test';
import assert from 'node:assert/strict';
import {actorSkillsSnapshot} from '../../foundry-module/scripts/actorSkills.js';
function fixture(type='character'){
 const skill={slug:'athletics',label:'Athletics',attribute:'str',value:12,totalModifier:13,dc:24,breakdown:'Selected explanation',lore:false,itemId:null,rank:2,armor:true,base:10,mod:14,visible:false};
 const current={type,system:{skills:{athletics:skill}}};let calls=0;
 const actor={documentName:'Actor',id:'a',uuid:'Scene.s.Token.t.Actor.a',type,name:'Actor',items:new Map(),testUserPermission:()=>true,toObject(flag){calls++;assert.equal(flag,false);return current;}};
 const token={uuid:'Scene.s.Token.t',name:'Token',parent:{uuid:'Scene.s',name:'Scene'},baseActor:null,isLinked:false};
 const target={document:actor,token};globalThis.game={user:{isGM:true}};
 const lore=(id,type='lore')=>{const item={documentName:'Item',id,uuid:`${actor.uuid}.Item.${id}`,type,name:'Duplicate',parent:actor,folder:null,compendium:null,testUserPermission:()=>true,toObject(){throw Error('Lore source must not be read');}};actor.items.set(id,item);return item;};
 return {actor,target,current,skill,lore,get calls(){return calls;}};
}
test('character current leaves retain independent values, exact transformed provenance and rank labels',()=>{
 const f=fixture(),result=actorSkillsSnapshot(f.target);assert.equal(f.calls,1);assert.equal(result.records.length,11);
 const values=Object.fromEntries(result.records.map(row=>[row.raw[0].path.split('/').at(-1),row.mapped.value]));assert.equal(values.value,12);assert.equal(values.totalModifier,13);assert.equal(values.dc,24);assert.deepEqual(values.rank,{rank:2,label:'Expert'});assert.equal(values.armor,true);assert.ok(!Object.hasOwn(values,'base'));
 for(const row of result.records){assert.equal(row.key,`skills:current:${row.raw[0].path}`);assert.equal(row.raw[0].basis,'transformed');assert.equal(row.raw[0].document_uuid,f.actor.uuid);assert.deepEqual(row.provenance.contributors,[{document_uuid:f.actor.uuid,path:row.raw[0].path,basis:'transformed'}]);assert.deepEqual(row.provenance.limitations,['serialized_current_skill_not_target_context']);}
 for(const [rank,label]of ['Untrained','Trained','Expert','Master','Legendary'].entries()){f.skill.rank=rank;assert.deepEqual(actorSkillsSnapshot(f.target).records.find(row=>row.mapped.concept==='current_skill_rank').mapped.value,{rank,label});}
});
test('NPC resolved base/mod/visible are separate from totals and conditional variants stay excluded',()=>{
 const f=fixture('npc');Object.defineProperty(f.skill,'special',{get(){throw Error('variants must not be read');}});const result=actorSkillsSnapshot(f.target);assert.ok(result.reasons.includes('conditional_skill_variants_not_evaluated'));assert.ok(result.records.some(row=>row.raw[0].path.endsWith('/base')&&row.raw[0].value===10));assert.ok(result.records.some(row=>row.raw[0].path.endsWith('/mod')&&row.raw[0].value===14));assert.ok(!result.records.some(row=>row.raw[0].path.endsWith('/rank')));
});
test('NPC optional note qualifies the skill without invented missing qualifiers',()=>{
 const f=fixture('npc');f.skill.note='Only while swimming';let result=actorSkillsSnapshot(f.target);assert.equal(result.records.find(row=>row.mapped.concept==='current_skill_note').mapped.value,'Only while swimming');delete f.skill.note;result=actorSkillsSnapshot(f.target);assert.equal(result.records.find(row=>row.mapped.concept==='current_skill_note').raw[0].present,false);assert.ok(!result.reasons.includes('current_skill_fields_unavailable'));
});
test('Lore joins exact owner Item ID, retains duplicate names and escaped generated keys without name guessing',()=>{
 const f=fixture(),one=f.lore('one'),two=f.lore('two');f.current.system.skills={'A/B~ Lore':{...f.skill,lore:true,itemId:'two'},another:{...f.skill,lore:true,itemId:'one'}};const result=actorSkillsSnapshot(f.target),links=result.records.filter(row=>row.kind==='relationship');assert.equal(links.length,2);assert.equal(links[0].key,'skills:current-lore:A~1B~0 Lore');assert.equal(links[0].mapped.value.target_uuid,two.uuid);assert.equal(links[1].mapped.value.target_uuid,one.uuid);assert.ok(links.every(row=>row.mapped.value.name==='Duplicate'&&row.mapped.value.token_uuid===f.target.token.uuid));assert.deepEqual(links[0].raw.map(raw=>raw.path),['/system/skills/A~1B~0 Lore/lore','/system/skills/A~1B~0 Lore/itemId']);
});
test('denied Lore claim withholds all key/label/total evidence before touching selected getters',()=>{
 const f=fixture(),item=f.lore('secret','effect');item.testUserPermission=()=>false;Object.defineProperty(item,'name',{get(){throw Error('denied name');}});f.current.system.skills={'SECRET_KEY':{lore:true,itemId:'secret'}};Object.defineProperty(f.current.system.skills.SECRET_KEY,'label',{get(){throw Error('denied label');}});const result=actorSkillsSnapshot(f.target);assert.equal(result.records.length,1);assert.deepEqual(result.records[0].mapped.value,{status:'denied',target_uuid:null});assert.deepEqual(result.records[0].raw,[]);assert.ok(!JSON.stringify(result).includes('SECRET'));assert.ok(result.reasons.includes('current_skill_items_denied'));
});
test('missing/null/dangling/wrong-type Lore claims remain explicit without fabricated identities',()=>{
 for(const id of [null,undefined,'','missing','wrong']){const f=fixture();f.skill.lore=true;if(id===undefined)delete f.skill.itemId;else f.skill.itemId=id;f.lore('wrong','effect');const result=actorSkillsSnapshot(f.target),link=result.records.find(row=>row.kind==='relationship');assert.deepEqual(link.mapped.value,{status:id==='wrong'?'unsupported':'missing',target_uuid:null});}
});
test('absent and empty collection markers differ; missing leaves never fall back to source/defaults',()=>{
 const f=fixture();delete f.current.system.skills;let result=actorSkillsSnapshot(f.target);assert.deepEqual(result.records[0].raw[0],{document_uuid:f.actor.uuid,path:'/system/skills',present:false,basis:'transformed'});assert.ok(result.reasons.includes('current_skill_fields_unavailable'));f.current.system.skills={};result=actorSkillsSnapshot(f.target);assert.deepEqual(result.records[0].raw[0].value,{});assert.equal(result.records[0].mapped.value,null);f.current.system.skills={partial:{lore:false,itemId:null}};result=actorSkillsSnapshot(f.target);assert.equal(result.records[0].raw[0].present,false);assert.ok(!Object.hasOwn(result.records[0].raw[0],'value'));
});
test('nonplain own data works, inherited fields remain absent, selected getters reject without invocation',()=>{
 const f=fixture();f.current.system.skills.athletics=Object.assign(Object.create({get unrelated(){throw Error('prototype');}}),f.skill);assert.equal(actorSkillsSnapshot(f.target).records.length,11);delete f.current.system.skills.athletics.label;Object.defineProperty(Object.getPrototypeOf(f.current.system.skills.athletics),'label',{get(){throw Error('inherited label');}});assert.equal(actorSkillsSnapshot(f.target).records.find(row=>row.raw[0].path.endsWith('/label')).raw[0].present,false);
 for(const path of [['type'],['system'],['system','skills'],['system','skills','athletics'],['system','skills','athletics','lore'],['system','skills','athletics','itemId'],['system','skills','athletics','value']]){const f=fixture();let node=f.current,calls=0;for(const key of path.slice(0,-1))node=node[key];Object.defineProperty(node,path.at(-1),{get(){calls++;return 1;}});assert.throws(()=>actorSkillsSnapshot(f.target),TypeError);assert.equal(calls,0);}
});
test('malformed values and standalone bounds reject; familiar never serializes',()=>{
 for(const value of [null,true,'1',NaN,Infinity]){const f=fixture();f.skill.value=value;assert.throws(()=>actorSkillsSnapshot(f.target),TypeError);}
 for(const rank of [-1,5,1.5]){const f=fixture();f.skill.rank=rank;assert.throws(()=>actorSkillsSnapshot(f.target),TypeError);}
 const keys=fixture();keys.current.system.skills=Object.fromEntries(Array.from({length:513},(_,index)=>[String(index),{}]));assert.throws(()=>actorSkillsSnapshot(keys.target),/512/);
 const length=fixture();length.current.system.skills={['🙂'.repeat(257)]:{}};assert.throws(()=>actorSkillsSnapshot(length.target),/256/);
 const empty=fixture();empty.current.system.skills={'':{}};assert.throws(()=>actorSkillsSnapshot(empty.target),/1–256/);
 const items=fixture();for(let index=0;index<12001;index++)items.lore(String(index));assert.throws(()=>actorSkillsSnapshot(items.target),/12000/);assert.equal(items.calls,0);
 const familiar=fixture('familiar');assert.deepEqual(actorSkillsSnapshot(familiar.target),{records:[],reasons:['other_skills_pending']});assert.equal(familiar.calls,0);
});
