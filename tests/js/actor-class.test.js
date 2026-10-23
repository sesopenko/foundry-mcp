import test from 'node:test';
import assert from 'node:assert/strict';
import {classFields} from '../../foundry-module/scripts/actorClass.js';
const rows=system=>new Map(classFields({type:'class',system}).map(row=>[row.path,row]));
test('class preserves source choices, starting ranks, progression and named references',()=>{
 const system={keyAbility:{value:['str','dex','unknown'],selected:null},hp:8,perception:0,savingThrows:{fortitude:1,reflex:2,will:3},attacks:{simple:4,martial:0,advanced:1,unarmed:2,other:{name:'custom group',rank:3}},defenses:{unarmored:1,light:2,medium:3,heavy:4},spellcasting:0,trainedSkills:{value:['arcana','unknown'],additional:2},ancestryFeatLevels:{value:[1,5]},classFeatLevels:{value:[1,2,2.5]},generalFeatLevels:{value:[3]},skillFeatLevels:{value:[]},skillIncreaseLevels:{value:[3,5]},items:{'a/~':{uuid:'Compendium.test.features.Item.one',img:'a.svg',name:'Later feature',level:20,secret:'excluded'}},traits:{otherTags:['custom'],rarity:'rare',value:['excluded']},slug:null,publication:{title:'Book',authors:'Writer',license:'ORC',remaster:false}};
 const before=structuredClone(system),result=rows(system);
 assert.equal(result.get('/system/keyAbility/value/2').value,'unknown');assert.equal(result.get('/system/keyAbility/selected').value,null);assert.equal(result.get('/system/hp').concept,'class_hp_contribution');
 for(const [path,rank]of [['perception',0],['savingThrows/fortitude',1],['savingThrows/reflex',2],['savingThrows/will',3],['attacks/simple',4],['attacks/other/rank',3],['defenses/heavy',4],['spellcasting',0]])assert.deepEqual(result.get('/system/'+path).mapped_value,{rank,label:['Untrained','Trained','Expert','Master','Legendary'][rank]});
 assert.equal(result.get('/system/classFeatLevels/value/2').value,2.5);assert.equal(result.get('/system/items/a~1~0/uuid').concept,'class_feature_uuid');assert.equal(result.get('/system/items/a~1~0/level').value,20);assert.equal(result.get('/system/publication/remaster').value,false);
 assert.deepEqual(system,before);assert.ok([...result.values()].every(row=>row.limitations[0]==='class_source_not_effective_character'));assert.ok(!JSON.stringify([...result.values()]).includes('excluded'));
});
test('class missing, empty and nullable facts stay distinct without defaults',()=>{
 const result=rows({keyAbility:{value:[],selected:null},items:{},trainedSkills:{value:[],additional:0},skillFeatLevels:{value:[]},attacks:{other:{name:undefined}}});
 for(const path of ['keyAbility/value','trainedSkills/value','skillFeatLevels/value'])assert.deepEqual(result.get('/system/'+path).value,[]);
 assert.deepEqual(result.get('/system/items').value,{});assert.equal(result.get('/system/keyAbility/selected').value,null);assert.equal(result.get('/system/attacks/other/name').present,false);
 for(const path of ['hp','perception','keyAbility/selected','items']){const row=rows({}).get('/system/'+path);assert.equal(row.present,false);assert.ok(!Object.hasOwn(row,'value'));}
 assert.equal(classFields({type:'background'}),null);
});
test('class rejects malformed selected source and enforces schema bounds',()=>{
 const invalid=[{attacks:{other:{name:null}}},{hp:3},{hp:13},{hp:NaN},{hp:null},{perception:1.5},{perception:5},{perception:-1},{perception:null},{keyAbility:{value:[null]}},{keyAbility:{selected:undefined}},{keyAbility:{selected:3}},{trainedSkills:{additional:-1}},{trainedSkills:{additional:1.5}},{trainedSkills:{value:null}},{classFeatLevels:{value:[0]}},{classFeatLevels:{value:[Infinity]}},{classFeatLevels:{value:['2']}},{items:null},{items:[]},{items:{x:null}},{items:{x:{level:-1}}},{items:{x:{level:1.5}}},{items:{x:{uuid:0}}},{traits:{otherTags:null}},{publication:{remaster:null}},{slug:0},{keyAbility:{value:Array(12001).fill('str')}},{items:Object.fromEntries(Array.from({length:12001},(_,i)=>[i,{}]))}];
 for(const system of invalid)assert.throws(()=>rows(system),TypeError,JSON.stringify(system).slice(0,120));
 assert.equal(classFields({type:'class',system:{trainedSkills:{value:Array(12000).fill('arcana')}}}).filter(row=>row.concept==='class_trained_skill_code').length,12000);
 assert.equal(classFields({type:'class',system:{items:Object.fromEntries(Array.from({length:12000},(_,i)=>[i,{}]))}}).filter(row=>row.concept==='class_feature_uuid').length,12000);
});
test('class ignores inherited values, prepared getters, descriptions and rule elements',()=>{
 const result=rows({keyAbility:Object.create({value:['secret']}),rules:[{key:'GrantItem',uuid:'secret'}],description:{value:'secret'},get prepared(){throw new Error('prepared');}});
 assert.equal(result.get('/system/keyAbility/value').present,false);assert.ok(!JSON.stringify([...result.values()]).includes('secret'));
});
