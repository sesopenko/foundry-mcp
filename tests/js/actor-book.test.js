import test from 'node:test';
import assert from 'node:assert/strict';
import {bookFields} from '../../foundry-module/scripts/actorBook.js';
import {physicalFields} from '../../foundry-module/scripts/actorPhysical.js';
const source=()=>({type:'book',system:{category:'spell',capacity:20,contents:['Compendium.pf2e.spells-srd.Item.first','Compendium.pf2e.spells-srd.Item.first','Actor.owner.Item.second'],quantity:2,price:{value:{gp:1},per:10},containerId:null,traits:{value:['magical','future-trait'],otherTags:['future-tag'],rarity:'common'},slug:null,publication:{title:'Source',authors:'Author',license:'ORC',remaster:true}}});
const row=(rows,path)=>rows.find(r=>r.path==='/system/'+path);
test('book source preserves ordered duplicate UUID claims independently of ownership and capacity use',()=>{
 const input=source(),before=JSON.stringify(input),rows=bookFields(input);
 for(const [path,value]of [['category','spell'],['capacity',20],['contents/0',input.system.contents[0]],['contents/1',input.system.contents[0]],['contents/2',input.system.contents[2]],['traits/value/1','future-trait'],['traits/otherTags/0','future-tag'],['traits/rarity','common'],['slug',null],['publication/title','Source'],['publication/remaster',true]])assert.equal(row(rows,path).value,value);
 assert.equal(JSON.stringify(input),before);assert.ok(rows.every(r=>r.limitations.includes('source_only_no_book_ownership_or_preparation')));
 assert.equal(bookFields({type:'equipment'}),null);assert.equal(bookFields(null),null);
 for(const category of ['formula','future-category']){input.system.category=category;assert.equal(row(bookFields(input),'category').value,category);}
 input.system.contents=['invalid-but-preserved-claim'];assert.equal(row(bookFields(input),'contents/0').value,'invalid-but-preserved-claim');
});
test('missing empty and malformed book fields retain source distinctions',()=>{
 const input=source();input.system.contents=[];input.system.traits.value=[];input.system.traits.otherTags=[];
 for(const path of ['contents','traits/value','traits/otherTags'])assert.deepEqual(row(bookFields(input),path).value,[]);
 delete input.system.category;delete input.system.capacity;delete input.system.contents;delete input.system.slug;delete input.system.publication;
 for(const path of ['category','capacity','contents','slug','publication/title','publication/remaster']){const missing=row(bookFields(input),path);assert.equal(missing.present,false);assert.equal(Object.hasOwn(missing,'value'),false);}
});
test('malformed selected book leaves reject without coercion',()=>{
 for(const change of [s=>s.system.category=null,s=>s.system.category=undefined,s=>s.system.category=5,s=>s.system.capacity=NaN,s=>s.system.capacity=Infinity,s=>s.system.capacity='20',s=>s.system.capacity=null,s=>s.system.contents=undefined,s=>s.system.contents=null,s=>s.system.contents={},s=>s.system.contents=[null],s=>s.system.contents=[{}],s=>s.system.traits.value=[false],s=>s.system.traits.rarity=3,s=>s.system.slug=undefined,s=>s.system.publication.title=null,s=>s.system.publication.remaster='true']){const input=source();change(input);assert.throws(()=>bookFields(input),TypeError);}
});
test('book specialty selector excludes runtime contents and source subitems without colliding with physical fields',()=>{
 const input=source();for(const key of ['subitems','prepared','knownSpells','formulas','description','rules','usedCapacity'])Object.defineProperty(input.system,key,{get(){throw new Error(key);}});
 const rows=[...physicalFields(input),...bookFields(input)],paths=rows.map(r=>r.path);assert.equal(new Set(paths).size,paths.length);
 assert.equal(row(rows,'quantity').value,2);assert.equal(row(rows,'price/per').value,10);assert.equal(row(rows,'price/value/gp').value,1);
 assert.ok(!bookFields(input).some(r=>/quantity|price|containerId|equipped|usage|description|rules|subitems/.test(r.path)));
});
