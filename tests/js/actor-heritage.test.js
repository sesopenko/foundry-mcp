import test from 'node:test';
import assert from 'node:assert/strict';
import {heritageFields} from '../../foundry-module/scripts/actorHeritage.js';
const rows=source=>new Map(heritageFields(source).map(row=>[row.path,row]));
test('heritage selects ancestry association leaves and metadata without inferring ownership',()=>{
 const source={type:'heritage',system:{ancestry:{name:'Associated ancestry',slug:'unknown-code',uuid:'Compendium.system.ancestries.Item.target',secret:'excluded'},traits:{value:['unknown-trait','unknown-trait'],otherTags:['tag'],rarity:'uncommon'},slug:null,publication:{title:'Book',authors:'Author',license:'ORC',remaster:false},quantity:99,level:12,rules:[{key:'GrantItem',uuid:'excluded'}],description:{value:'excluded'}}};
 const before=structuredClone(source),result=rows(source);
 assert.equal(result.get('/system/ancestry/name').concept,'heritage_ancestry_name');
 assert.equal(result.get('/system/ancestry/slug').value,'unknown-code');
 assert.equal(result.get('/system/ancestry/uuid').value,source.system.ancestry.uuid);
 assert.ok(!result.has('/system/ancestry'));
 assert.equal(result.get('/system/traits/value/1').value,'unknown-trait');
 assert.equal(result.get('/system/traits/otherTags/0').concept,'heritage_other_tag_code');
 assert.equal(result.get('/system/publication/remaster').value,false);
 assert.equal(result.get('/system/slug').value,null);
 assert.ok([...result.values()].every(row=>row.limitations.length===1&&row.limitations[0]==='heritage_source_not_effective_character'));
 assert.ok(!JSON.stringify([...result]).includes('excluded'));
 assert.ok(!result.has('/system/quantity'));assert.ok(!result.has('/system/level'));
 assert.deepEqual(source,before);
});
test('heritage null association, absent association and missing leaves remain distinct',()=>{
 const absent=rows({type:'heritage'}),versatile=rows({type:'heritage',system:{ancestry:null,traits:{value:[],otherTags:[]}}}),empty=rows({type:'heritage',system:{ancestry:{name:''}}});
 assert.equal(absent.get('/system/ancestry').present,false);assert.ok(!Object.hasOwn(absent.get('/system/ancestry'),'value'));
 assert.equal(versatile.get('/system/ancestry').value,null);assert.equal(versatile.get('/system/ancestry').concept,'heritage_ancestry_association');
 assert.deepEqual(versatile.get('/system/traits/value').value,[]);assert.deepEqual(versatile.get('/system/traits/otherTags').value,[]);
 assert.ok(!empty.has('/system/ancestry'));assert.equal(empty.get('/system/ancestry/name').value,'');assert.equal(empty.get('/system/ancestry/uuid').present,false);
 assert.equal(heritageFields({type:'ancestry'}),null);
});
test('heritage rejects malformed association leaves, metadata and bounded code lists',()=>{
 for(const system of [{ancestry:undefined},{ancestry:[]},{ancestry:false},{ancestry:''},{ancestry:{name:null}},{ancestry:{slug:0}},{ancestry:{uuid:{}}},{slug:0},{traits:{value:null}},{traits:{value:[false]}},{traits:{otherTags:{}}},{traits:{rarity:null}},{publication:{remaster:0}},{publication:{title:undefined}},{traits:{value:Array(12001).fill('x')}}])assert.throws(()=>heritageFields({type:'heritage',system}),TypeError);
 assert.equal(heritageFields({type:'heritage',system:{traits:{value:Array(12000).fill('x')}}}).filter(row=>row.path.startsWith('/system/traits/value/')).length,12000);
});
test('heritage ignores inherited values and unrelated prepared getters',()=>{
 const system=Object.create({ancestry:{name:'inherited'},slug:'inherited'});
 Object.defineProperty(system,'prepared',{get(){throw new Error('prepared getter');}});
 const result=rows({type:'heritage',system});
 assert.equal(result.get('/system/ancestry').present,false);assert.equal(result.get('/system/slug').present,false);
});
