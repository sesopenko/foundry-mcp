import test from 'node:test';
import assert from 'node:assert/strict';
import {deityFields} from '../../foundry-module/scripts/actorDeity.js';
const rows=source=>new Map(deityFields(source).map(row=>[row.path,row]));
test('deity retains faith categories and devotee options without acquisition or rank inference',()=>{
 const source={type:'deity',system:{category:'philosophy',sanctification:{modal:'must',what:['holy','future']},domains:{primary:['fire'],alternate:['unknown']},font:['harm','heal'],attribute:['wis'],skill:['religion',''],weapons:['longsword','custom'],spells:{'1':'Compendium.p.spells.Item.s','rank/~opaque':'Item.s'},traits:{otherTags:['custom'],value:['excluded'],rarity:'excluded'},slug:null,publication:{title:'Book',authors:'Author',license:'ORC',remaster:false},rules:[{key:'excluded'}]}};
 const before=structuredClone(source),result=rows(source);
 for(const [path,value]of [['category','philosophy'],['sanctification/modal','must'],['sanctification/what/1','future'],['domains/primary/0','fire'],['domains/alternate/0','unknown'],['font/1','heal'],['attribute/0','wis'],['skill/1',''],['weapons/1','custom'],['spells/rank~1~0opaque','Item.s'],['slug',null],['publication/remaster',false]])assert.equal(result.get('/system/'+path).value,value);
 assert.equal(result.get('/system/spells/1').concept,'deity_spell_uuid');assert.deepEqual(source,before);assert.ok([...result.values()].every(row=>row.limitations[0]==='deity_options_not_active_benefits'));assert.ok(!JSON.stringify([...result.values()]).includes('excluded'));
 for(const category of ['deity','pantheon','covenant','philosophy','future'])assert.equal(rows({type:'deity',system:{category}}).get('/system/category').value,category);
});
test('deity preserves absent, nullable and empty facts with no template defaults',()=>{
 const absent=rows({type:'deity'});for(const path of ['category','sanctification','domains/primary','domains/alternate','font','attribute','skill','weapons','spells','traits/otherTags']){assert.equal(absent.get('/system/'+path).present,false);assert.ok(!Object.hasOwn(absent.get('/system/'+path),'value'));}
 const empty=rows({type:'deity',system:{sanctification:null,skill:null,spells:{},font:[],domains:{primary:[],alternate:[]}}});assert.equal(empty.get('/system/sanctification').value,null);assert.equal(empty.get('/system/skill').value,null);assert.deepEqual(empty.get('/system/spells').value,{});assert.equal(empty.get('/system/spells').concept,'deity_spell_entries');assert.deepEqual(empty.get('/system/font').value,[]);
 assert.deepEqual(rows({type:'deity',system:{skill:[]}}).get('/system/skill').value,[]);assert.equal(deityFields({type:'npc'}),null);
});
test('deity rejects malformed leaves and bounded lists/maps',()=>{
 for(const system of [{category:null},{category:1},{sanctification:[]},{sanctification:0},{sanctification:{modal:null}},{sanctification:{what:null}},{sanctification:{what:[null]}},{domains:{primary:null}},{domains:{alternate:[1]}},{font:null},{attribute:[false]},{skill:1},{weapons:[null]},{spells:null},{spells:[]},{spells:{1:null}},{spells:{x:undefined}},{traits:{otherTags:[0]}},{slug:0},{publication:{remaster:null}},{font:Array(12001).fill('heal')},{spells:Object.fromEntries(Array.from({length:12001},(_,i)=>[i,'Item.s']))}])assert.throws(()=>deityFields({type:'deity',system}),TypeError);
 assert.equal(deityFields({type:'deity',system:{font:Array(12000).fill('heal')}}).filter(row=>row.concept==='deity_font_code').length,12000);
 assert.equal(deityFields({type:'deity',system:{spells:Object.fromEntries(Array.from({length:12000},(_,i)=>[i,'Item.s']))}}).filter(row=>row.concept==='deity_spell_uuid').length,12000);
});
test('deity ignores unrelated/prepared and inherited values',()=>{
 const result=rows({type:'deity',system:{domains:Object.create({primary:['secret']}),traits:{otherTags:[]},get prepared(){throw new Error('unrelated getter');},description:{value:'secret'}}});assert.equal(result.get('/system/domains/primary').present,false);assert.ok(!JSON.stringify([...result.values()]).includes('secret'));
});
