import test from 'node:test';
import assert from 'node:assert/strict';
import {characterFields,characterNoteFields} from '../../foundry-module/scripts/actorCharacter.js';
const row=(rows,path)=>rows.find(entry=>entry.path===path);
const fixture=()=>({type:'character',system:{
 abilities:null,
 details:{level:{value:3},age:{value:'adult'},height:{value:'6 feet'},weight:{value:'180 lb'},gender:{value:'they'},ethnicity:{value:'custom'},nationality:{value:'custom'},keyability:{value:'custom-attribute'},languages:{value:['common','custom','common'],details:'<p>custom speech</p>'},xp:{value:0,min:0,max:1000,pct:999},biography:{appearance:'<p>exact appearance</p>',backstory:'secret',birthPlace:'place',attitude:'kind',beliefs:'belief',edicts:['help','help'],anathema:[],likes:'tea',dislikes:'rain',catchphrases:'hello',campaignNotes:'<p>campaign</p>',allies:'allies',enemies:'enemies',organizations:'guild',visibility:{appearance:true,backstory:false,personality:false,campaign:false}}},
 attributes:{hp:{value:0,temp:0,tempSource:'local-item',sp:{value:0,max:999},max:999},ac:{value:999},immunities:[{type:'poison'}]},
 skills:{athletics:{rank:0,total:999},stealth:{rank:4}},
 resources:{heroPoints:{value:0,max:3},focus:{value:0,max:999,cap:999},resolve:{value:0,max:999},crafting:{infusedReagents:{value:0,max:999}},investiture:{value:999}},
 build:{attributes:{manual:false,boosts:{1:['str','custom','str'],5:[]},apex:null,keyOptions:['secret'],allowedBoosts:{1:999},flaws:{ancestry:['secret']}}},
 traits:{value:['prepared']},perception:{rank:4,mod:999},saves:{will:{value:999}},actions:[{name:'prepared'}],_migration:{secret:1}
}});
test('character nullable root abilities never manufacture six zero modifiers',()=>{
 const input=fixture(),rows=characterFields(input);assert.equal(row(rows,'/system/abilities').value,null);assert.ok(!rows.some(entry=>entry.path.startsWith('/system/abilities/')));
 delete input.system.abilities;const absent=row(characterFields(input),'/system/abilities');assert.equal(absent.present,false);assert.ok(!Object.hasOwn(absent,'value'));
 input.system.abilities={str:{mod:0},dex:{mod:-1},con:{mod:2},int:{mod:3},wis:{mod:4},cha:{mod:5}};
 const manual=characterFields(input);assert.equal(row(manual,'/system/abilities/str/mod').value,0);assert.equal(row(manual,'/system/abilities/dex/mod').value,-1);assert.ok(!row(manual,'/system/abilities'));
});
test('selected character identity resources and build source preserve provenance without effective additions',()=>{
 const input=fixture(),before=JSON.stringify(input),rows=characterFields(input);
 for(const [path,value] of [['/system/details/height/value','6 feet'],['/system/details/keyability/value','custom-attribute'],['/system/attributes/hp/value',0],['/system/attributes/hp/temp',0],['/system/attributes/hp/sp/value',0],['/system/resources/focus/value',0],['/system/resources/heroPoints/max',3],['/system/build/attributes/manual',false],['/system/build/attributes/apex',null],['/system/build/attributes/boosts/1/1','custom']])assert.equal(row(rows,path).value,value);
 assert.deepEqual(row(rows,'/system/build/attributes/boosts/5').value,[]);
 assert.ok(!rows.some(entry=>/\/hp\/max|\/sp\/max|\/focus\/(max|cap)|\/resolve\/max|\/infusedReagents\/max|\/xp\/pct|traits|perception|saves|\/ac\/|immunities|actions|_migration|keyOptions|allowedBoosts|flaws|investiture/.test(entry.path)));
 assert.ok(rows.every(entry=>entry.limitations.includes('character_source_not_effective_statistics')));assert.equal(JSON.stringify(input),before);
 // Returned empty markers also must not alias input arrays/records.
 row(rows,'/system/build/attributes/boosts/5').value.push('output mutation');assert.deepEqual(input.system.build.attributes.boosts[5],[]);
});
test('rank labels remain separate from check bonuses, including unknown escaped skill keys',()=>{
 const input=fixture();input.system.skills=JSON.parse('{"a~/b":{"rank":2,"total":999},"__proto__":{"rank":3}}');
 const rows=characterFields(input);assert.deepEqual(row(rows,'/system/skills/a~0~1b/rank').mapped_value,{rank:2,label:'Expert'});assert.deepEqual(row(rows,'/system/skills/__proto__/rank').mapped_value,{rank:3,label:'Master'});
 assert.ok(!rows.some(entry=>entry.path.endsWith('/total')));
 for(let rank=0;rank<=4;rank++){input.system.skills={athletics:{rank}};assert.equal(row(characterFields(input),'/system/skills/athletics/rank').mapped_value.label,['Untrained','Trained','Expert','Master','Legendary'][rank]);}
});
test('absent optional values empty records zero and null retain different source evidence',()=>{
 const input=fixture();input.system.skills={};delete input.system.resources.focus;delete input.system.build.attributes.apex;
 const rows=characterFields(input);assert.deepEqual(row(rows,'/system/skills').value,{});assert.equal(row(rows,'/system/resources/focus/value').present,false);assert.equal(row(rows,'/system/build/attributes/apex').present,false);assert.equal(row(rows,'/system/resources/heroPoints/value').value,0);
 assert.equal(characterFields(null),null);assert.equal(characterFields({type:'npc'}),null);assert.equal(characterNoteFields({type:'familiar'}),null);
});
test('prose requires explicit notes selector including language details and biography arrays',()=>{
 const input=fixture(),source=characterFields(input),notes=characterNoteFields(input);
 assert.ok(!source.some(entry=>entry.path==='/system/details/biography/backstory'||entry.path==='/system/details/languages/details'||entry.path.includes('/edicts')));
 assert.equal(row(notes,'/system/details/biography/appearance').value,'<p>exact appearance</p>');assert.equal(row(notes,'/system/details/languages/details').value,'<p>custom speech</p>');assert.equal(row(notes,'/system/details/biography/edicts/1').value,'help');assert.deepEqual(row(notes,'/system/details/biography/anathema').value,[]);
 assert.equal(row(source,'/system/details/biography/visibility/backstory').value,false);
});
test('malformed selected scalar records arrays and ranks fail without coercion',()=>{
 for(const mutate of [s=>s.system.abilities=0,s=>s.system.abilities=[],s=>s.system.abilities={str:null},s=>s.system.abilities={str:{mod:'0'}},s=>s.system.skills=null,s=>s.system.skills={athletics:null},s=>s.system.skills.athletics.rank=1.5,s=>s.system.skills.athletics.rank=5,s=>s.system.skills.athletics.rank=-1,s=>s.system.attributes.hp.value=NaN,s=>s.system.resources.focus.value=Infinity,s=>s.system.build.attributes.manual='false',s=>s.system.build.attributes.apex={},s=>s.system.build.attributes.boosts[1]=[null],s=>s.system.details.languages.value='common',s=>s.system.details.biography.visibility.backstory=0]){const input=fixture();mutate(input);assert.throws(()=>characterFields(input),TypeError);}
 for(const mutate of [s=>s.system.details.biography.backstory={},s=>s.system.details.biography.edicts=[false],s=>s.system.details.languages.details=null]){const input=fixture();mutate(input);assert.throws(()=>characterNoteFields(input),TypeError);}
});
test('numeric fields impose no unproven integer bounds while optional undefined stays absent',()=>{
 const input=fixture();input.system.details.level.value=-0.5;input.system.attributes.hp.value=-3.25;input.system.resources.heroPoints.max=1.5;input.system.attributes.hp.tempSource=undefined;
 const rows=characterFields(input);assert.equal(row(rows,'/system/details/level/value').value,-0.5);assert.equal(row(rows,'/system/attributes/hp/value').value,-3.25);assert.equal(row(rows,'/system/resources/heroPoints/max').value,1.5);assert.equal(row(rows,'/system/attributes/hp/tempSource').present,false);
});
