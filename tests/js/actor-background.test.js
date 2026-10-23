import test from 'node:test';
import assert from 'node:assert/strict';
import {backgroundFields} from '../../foundry-module/scripts/actorBackground.js';
const rows=source=>new Map(backgroundFields(source).map(row=>[row.path,row]));
test('background preserves offered and selected boosts, training packages, references and metadata',()=>{
 const source={type:'background',system:{boosts:{'a/b~c':{value:['str','dex'],selected:null},fixed:{value:['int'],selected:'int'}},trainedSkills:{value:['arcana','unknown'],lore:['Sailing Lore','']},items:{'f/~':{uuid:'Item.named',img:'x.svg',name:'Feature',level:0,secret:'excluded'}},traits:{value:[],otherTags:['custom'],rarity:'rare'},slug:null,publication:{title:'Book',authors:'Author',license:'ORC',remaster:false}}};
 const before=structuredClone(source),result=rows(source);
 assert.equal(result.get('/system/boosts/a~1b~0c/value/0').value,'str');assert.equal(result.get('/system/boosts/a~1b~0c/value/0').concept,'background_boost_offer_code');assert.equal(result.get('/system/boosts/a~1b~0c/selected').value,null);
 assert.equal(result.get('/system/boosts/fixed/selected').value,'int');assert.equal(result.get('/system/trainedSkills/value/1').value,'unknown');assert.equal(result.get('/system/trainedSkills/lore/0').value,'Sailing Lore');assert.equal(result.get('/system/trainedSkills/lore/1').value,'');
 assert.equal(result.get('/system/items/f~1~0/uuid').concept,'background_feature_uuid');assert.equal(result.get('/system/items/f~1~0/img').concept,'background_feature_image');assert.equal(result.get('/system/items/f~1~0/level').value,0);assert.equal(result.get('/system/publication/remaster').value,false);
 assert.ok(![...result.keys()].some(path=>path.includes('secret')));assert.deepEqual(source,before);assert.ok([...result.values()].every(row=>row.limitations[0]==='background_source_not_effective_character'));
});
test('background missing, null and empty source facts remain distinct without defaults',()=>{
 const empty=rows({type:'background',system:{boosts:{empty:{value:[],selected:null}},trainedSkills:{value:[],lore:[]},items:{}}});
 assert.deepEqual(empty.get('/system/boosts/empty/value').value,[]);assert.equal(empty.get('/system/boosts/empty/selected').value,null);assert.deepEqual(empty.get('/system/trainedSkills/lore').value,[]);assert.deepEqual(empty.get('/system/items').value,{});
 const absent=rows({type:'background'});for(const path of ['/system/boosts','/system/trainedSkills/value','/system/trainedSkills/lore','/system/items']){assert.equal(absent.get(path).present,false);assert.ok(!Object.hasOwn(absent.get(path),'value'));}
 assert.deepEqual(rows({type:'background',system:{boosts:{}}}).get('/system/boosts').value,{});assert.equal(backgroundFields({type:'ancestry'}),null);
});
test('background rejects malformed selected leaves, map entries and oversized lists/maps',()=>{
 for(const system of [{boosts:null},{boosts:[]},{boosts:{x:null}},{boosts:{x:{value:[1]}}},{boosts:{x:{selected:0}}},{boosts:{x:{selected:undefined}}},{trainedSkills:{value:null}},{trainedSkills:{lore:{}}},{trainedSkills:{lore:[null]}},{items:{x:null}},{items:{x:{uuid:3}}},{items:{x:{level:Infinity}}},{items:{x:{level:-1}}},{items:{x:{level:1.5}}},{publication:{remaster:null}},{slug:0},{trainedSkills:{value:Array(12001).fill('arcana')}},{boosts:Object.fromEntries(Array.from({length:12001},(_,i)=>[i,{}]))},{items:Object.fromEntries(Array.from({length:12001},(_,i)=>[i,{}]))}])assert.throws(()=>backgroundFields({type:'background',system}),TypeError);
 assert.equal(backgroundFields({type:'background',system:{trainedSkills:{value:Array(12000).fill('arcana')}}}).filter(row=>row.concept==='background_trained_skill_code').length,12000);
});
test('background ignores unrelated getters, rules, descriptions and inherited selected leaves',()=>{
 const source={type:'background',system:{trainedSkills:Object.create({value:['secret']}),rules:[{key:'GrantItem',uuid:'secret'}],description:{value:'secret'},get prepared(){throw new Error('prepared getter');}}};
 const result=rows(source);assert.equal(result.get('/system/trainedSkills/value').present,false);assert.ok(!JSON.stringify([...result.values()]).includes('secret'));
});
