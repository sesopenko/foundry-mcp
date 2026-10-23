import test from 'node:test';
import assert from 'node:assert/strict';
import {ancestryFields} from '../../foundry-module/scripts/actorAncestry.js';
const rows=source=>new Map(ancestryFields(source).map(row=>[row.path,row]));
test('ancestry preserves offered, selected, alternate and legacy voluntary configuration',()=>{
 const source={type:'ancestry',system:{boosts:{'a/b~c':{value:['str','dex'],selected:null}},flaws:{0:{value:[],selected:'con'}},alternateAncestryBoosts:[],voluntary:{legacy:false,boost:null,flaws:['wis']},hp:6,speed:25,size:'med',hands:2,reach:5,vision:'unknown',languages:{value:['common'],custom:''},additionalLanguages:{count:0,value:[],custom:'Regional'},items:{'f/~':{uuid:'Item.named',img:'x.svg',name:'Feature',level:1,secret:'excluded'}},traits:{value:[],otherTags:[],rarity:'common'},slug:null}};
 const before=structuredClone(source),result=rows(source);
 assert.deepEqual(result.get('/system/boosts/a~1b~0c/value/0').value,'str');assert.equal(result.get('/system/boosts/a~1b~0c/selected').value,null);
 assert.deepEqual(result.get('/system/alternateAncestryBoosts').value,[]);assert.equal(result.get('/system/voluntary/legacy').value,false);assert.equal(result.get('/system/hp').concept,'ancestry_hp_contribution');assert.equal(result.get('/system/items/f~1~0/img').concept,'ancestry_feature_image');assert.equal(result.get('/system/items/f~1~0/uuid').value,'Item.named');assert.equal(result.get('/system/additionalLanguages/count').value,0);assert.equal(result.get('/system/vision').value,'unknown');
 assert.ok(![...result.keys()].some(path=>path.includes('secret')));assert.deepEqual(source,before);assert.ok([...result.values()].every(row=>row.limitations[0]==='ancestry_source_not_effective_character'));
});
test('ancestry missing, null and empty markers stay distinct without defaults',()=>{
 const empty=rows({type:'ancestry',system:{boosts:{},flaws:{},items:{},alternateAncestryBoosts:null}});
 assert.deepEqual(empty.get('/system/boosts').value,{});assert.deepEqual(empty.get('/system/items').value,{});assert.equal(empty.get('/system/alternateAncestryBoosts').value,null);assert.equal(empty.get('/system/hp').present,false);assert.ok(!Object.hasOwn(empty.get('/system/hp'),'value'));
 const absent=rows({type:'ancestry'});assert.equal(absent.get('/system/boosts').present,false);assert.equal(absent.get('/system/items').present,false);assert.equal(absent.get('/system/alternateAncestryBoosts').present,false);
 assert.equal(ancestryFields({type:'equipment'}),null);
});
test('ancestry rejects malformed selected leaves, slots, feature entries and overlong arrays',()=>{
 for(const system of [{hp:undefined},{hp:Infinity},{boosts:[]},{boosts:{x:null}},{flaws:{x:{value:[1]}}},{boosts:{x:{selected:0}}},{items:{x:null}},{items:{x:{level:-1}}},{items:{x:{level:1.5}}},{alternateAncestryBoosts:{}},{languages:{value:Array(12001).fill('common')}}])assert.throws(()=>ancestryFields({type:'ancestry',system}),TypeError);
});
test('ancestry excludes prepared getters and unrelated source objects',()=>{
 const source={type:'ancestry',system:{rules:[{key:'GrantItem',uuid:'private'}],description:{value:'private'},get prepared(){throw new Error('prepared getter');}}};
 assert.ok(!JSON.stringify(ancestryFields(source)).includes('private'));
});
