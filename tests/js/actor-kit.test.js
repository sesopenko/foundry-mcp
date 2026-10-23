import test from 'node:test';
import assert from 'node:assert/strict';
import {kitFields} from '../../foundry-module/scripts/actorKit.js';
const entry=(items=null)=>({uuid:'Compendium.example.items.Item.definition',img:'icons/gear.webp',quantity:2,name:'Component',isContainer:true,items});
const values=(source)=>new Map(kitFields(source).map((row)=>[row.path,row]));
test('kit source retains keyed nested definitions and own nonphysical price',()=>{
 const source={type:'kit',system:{items:{'a/~':entry({child:entry(null)})},price:{value:{gp:4,cp:0},per:10,sizeSensitive:false},traits:{value:['unknown','unknown'],otherTags:[]},slug:null,quantity:999,containerId:'not-a-possession',rules:[{key:'Secret'}]}};
 const before=structuredClone(source),rows=values(source);
 assert.equal(rows.get('/system/items/a~1~0/quantity').value,2);
 assert.equal(rows.get('/system/items/a~1~0/items/child/items').value,null);
 assert.equal(rows.get('/system/price/per').value,10);
 assert.equal(rows.get('/system/price/value/cp').value,0);
 assert.equal(rows.get('/system/price/value/pp').present,false);
 assert.equal(rows.get('/system/traits/value/1').value,'unknown');
 assert.deepEqual(rows.get('/system/traits/otherTags').value,[]);
 assert.equal(rows.get('/system/slug').value,null);
 assert.equal(rows.has('/system/quantity'),false);
 assert.deepEqual(source,before);
 assert.equal(rows.size,kitFields(source).length);
 for(const row of rows.values())assert.deepEqual(row.limitations,['bundle_definition_not_owned_inventory']);
});
test('kit missing, empty and optional undefined markers remain distinct',()=>{
 const absent=values({type:'kit'}),empty=values({type:'kit',system:{items:{},price:{sizeSensitive:undefined}}});
 assert.deepEqual(absent.get('/system/items'),{path:'/system/items',present:false,concept:'kit_items',limitations:['bundle_definition_not_owned_inventory']});
 assert.deepEqual(empty.get('/system/items').value,{});
 assert.equal(empty.get('/system/price/sizeSensitive').present,false);
 assert.equal(kitFields({type:'equipment'}),null);
});
test('kit source depth follows actual constructor boundary and rejects malformed selected values',()=>{
 const deepest=entry(null),source={type:'kit',system:{items:{a:entry({b:entry({c:entry({d:deepest})})})}}};
 assert.equal(values(source).get('/system/items/a/items/b/items/c/items/d/items').value,null);
 deepest.items={};assert.throws(()=>kitFields(source),/depth/);
 for(const items of [null,[],42,{a:null},{a:{...entry(),quantity:0}},{a:{...entry(),quantity:1.5}},{a:{...entry(),name:undefined}},{'':entry()}])assert.throws(()=>kitFields({type:'kit',system:{items}}),TypeError);
 for(const price of [{per:0},{per:Infinity},{value:{gp:-1}},{value:{cp:0.2}},{sizeSensitive:null}])assert.throws(()=>kitFields({type:'kit',system:{price}}),TypeError);
 assert.throws(()=>kitFields({type:'kit',system:{traits:{value:[null]}}}),TypeError);
});
test('kit source bounds entries and does not inspect unrelated prepared getters',()=>{
 const items=Object.fromEntries(Array.from({length:12001},(_,i)=>[String(i),entry()]));
 assert.throws(()=>kitFields({type:'kit',system:{items}}),/12000/);
 const source={type:'kit',system:{items:{}}};
 source.system.items.a=entry();
 Object.defineProperty(source.system.items.a,'unselected',{get(){throw Error('custom getter');},enumerable:true});
 Object.defineProperty(source.system,'contents',{get(){throw Error('prepared getter');}});
 assert.doesNotThrow(()=>kitFields(source));
});
