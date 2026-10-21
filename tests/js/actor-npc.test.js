import test from 'node:test';
import assert from 'node:assert/strict';
import {npcFields,npcNoteFields} from '../../foundry-module/scripts/actorNpc.js';
const source=()=>({type:'npc',system:{details:{level:{value:5},alliance:null,languages:{value:['common','custom'],details:'telepathy only'},publication:{title:'Book',authors:'Author',license:'ORC',remaster:true},blurb:'brief',publicNotes:'<p>Public</p>',privateNotes:'secret'},traits:{size:{value:'lg'},rarity:'unique',value:['beast','custom']},abilities:{str:{mod:4},dex:{mod:2},con:{mod:3},int:{mod:-1},wis:{mod:1},cha:{mod:0}},attributes:{adjustment:'elite',ac:{value:22,details:'24 against rays'},hp:{value:0,max:70,temp:0,details:'regeneration',tempSource:'localId'},allSaves:{value:'+1 against magic'},speed:{value:25,details:'ignores rubble',otherSpeeds:[{type:'fly',value:40,label:'winged',source:'authored',total:999}]},immunities:[{type:'poison',exceptions:['custom']}],weaknesses:[{type:'cold',value:5,applyOnce:false,exceptions:[]}],resistances:[{type:'physical',value:10,exceptions:[{label:'special silver',definition:[{and:['silver','magical']}]}],doubleVs:['fire']}]},saves:{fortitude:{value:13,saveDetail:'+2 poison'},reflex:{value:10,saveDetail:''},will:{value:11,saveDetail:''}},perception:{mod:12,details:'scent',vision:true,senses:[{type:'scent',acuity:'imprecise',range:30,source:null}]},skills:{athletics:{base:14,note:'+18 swimming',special:[{label:'swim',base:18,predicate:['action:swim']}]},custom:{base:null}},initiative:{statistic:'perception'},spellcasting:{rituals:{dc:25}},resources:{focus:{value:0,max:1}},actions:[{secret:'prepared'}],customModifiers:{secret:[]},_migration:{secret:1}}});
const row=(rows,path)=>rows.find(entry=>entry.path===path);
test('NPC authored statistics differ from ability modifiers and effective elite math',()=>{
 const input=source(),before=JSON.stringify(input),rows=npcFields(input);
 assert.equal(row(rows,'/system/abilities/str/mod').value,4);assert.equal(row(rows,'/system/attributes/ac/value').value,22);
 assert.equal(row(rows,'/system/saves/fortitude/value').concept,'authored_fortitude_save_bonus');
 assert.equal(row(rows,'/system/perception/mod').concept,'authored_perception_bonus');
 assert.equal(row(rows,'/system/attributes/adjustment').value,'elite');assert.ok(row(rows,'/system/attributes/adjustment').limitations.includes('elite_weak_math_not_applied'));
 assert.equal(row(rows,'/system/attributes/hp/value').value,0);assert.equal(row(rows,'/system/attributes/hp/temp').value,0);
 assert.equal(row(rows,'/system/skills/custom/base').value,null);assert.equal(JSON.stringify(input),before);
 assert.ok(!JSON.stringify(rows).includes('prepared'));assert.ok(!rows.some(entry=>/privateNotes|publicNotes|blurb|customModifiers|_migration|\/total$/.test(entry.path)));
});
test('stat-block exceptions senses movement languages and publication retain exact provenance',()=>{
 const rows=npcFields(source());
 for(const [path,value]of [['/system/attributes/ac/details','24 against rays'],['/system/attributes/allSaves/value','+1 against magic'],['/system/skills/athletics/special/0/base',18],['/system/perception/senses/0/source',null],['/system/attributes/speed/otherSpeeds/0/value',40],['/system/details/languages/details','telepathy only'],['/system/details/publication/remaster',true]])assert.equal(row(rows,path).value,value);
 assert.equal(row(rows,'/system/skills/athletics/special/0/predicate/0').value,'action:swim');
 assert.ok(row(rows,'/system/skills/athletics/special/0/predicate/0').limitations.includes('predicate_not_evaluated'));
});
test('IWR source records preserve string and compound exceptions without applicability calculations',()=>{
 const rows=npcFields(source());
 assert.equal(row(rows,'/system/attributes/immunities/0/type').value,'poison');
 assert.ok(!rows.some(entry=>entry.path==='/system/attributes/immunities/0/value'));
 assert.equal(row(rows,'/system/attributes/weaknesses/0/applyOnce').value,false);
 assert.deepEqual(row(rows,'/system/attributes/weaknesses/0/exceptions').value,[]);
 assert.equal(row(rows,'/system/attributes/resistances/0/exceptions/0/definition/0/and/0').value,'silver');
 assert.equal(row(rows,'/system/attributes/resistances/0/doubleVs/0').value,'fire');
 assert.ok(rows.every(entry=>entry.value===null||typeof entry.value!=='object'||Object.keys(entry.value).length===0));
});
test('missing null zero and empty collections remain distinct without default statistics',()=>{
 const input=source();input.system.skills={};input.system.traits.value=[];delete input.system.saves.will;input.system.attributes.adjustment=null;
 const rows=npcFields(input);assert.deepEqual(row(rows,'/system/skills').value,{});assert.deepEqual(row(rows,'/system/traits/value').value,[]);
 assert.equal(row(rows,'/system/saves/will/value').present,false);assert.ok(!Object.hasOwn(row(rows,'/system/saves/will/value'),'value'));
 assert.equal(row(rows,'/system/attributes/adjustment').value,null);assert.equal(npcFields({type:'character'}),null);assert.equal(npcFields(null),null);
});
test('unknown skill names retain escaped paths and source codes without invented identities',()=>{
 const input=source();input.system.skills=JSON.parse('{"a~/b":{"base":0},"__proto__":{"base":7}}');
 const rows=npcFields(input);assert.equal(row(rows,'/system/skills/a~0~1b/base').value,0);assert.equal(row(rows,'/system/skills/__proto__/base').value,7);assert.ok(rows.every(entry=>!Object.hasOwn(entry,'uuid')));
});
test('malformed selected values and cyclic or excessive predicates fail rather than leak or truncate',()=>{
 for(const change of [s=>s.system.attributes.immunities=['poison'],s=>s.system.skills.custom.base={},s=>s.system.perception.senses=[null],s=>s.system.attributes.hp.value=Infinity,s=>s.system.attributes.resistances[0].exceptions=[3],s=>{const a=[];a.push(a);s.system.skills.athletics.special[0].predicate=a;},s=>s.system.skills.athletics.special[0].predicate=[()=>1],s=>{let a=[];for(let i=0;i<34;i++)a=[a];s.system.skills.athletics.special[0].predicate=a;}]){const input=source();change(input);assert.throws(()=>npcFields(input),TypeError);}
});
test('notes require separate explicit selection and preserve exact source without enrichment',()=>{
 const input=source();assert.ok(!npcFields(input).some(entry=>entry.path.endsWith('privateNotes')));
 assert.equal(row(npcNoteFields(input),'/system/details/privateNotes').value,'secret');assert.equal(row(npcNoteFields(input),'/system/details/publicNotes').value,'<p>Public</p>');
 assert.equal(npcNoteFields({type:'familiar'}),null);
});
