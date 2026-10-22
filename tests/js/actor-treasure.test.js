import test from 'node:test';
import assert from 'node:assert/strict';
import {treasureFields} from '../../foundry-module/scripts/actorTreasure.js';
import {physicalFields} from '../../foundry-module/scripts/actorPhysical.js';
const source=()=>({type:'treasure',system:{category:'coin',quantity:53,price:{value:{pp:0,gp:1,sp:0,cp:0},per:100},containerId:null,equipped:{carryType:'worn'},traits:{value:['precious','future-trait'],otherTags:['future-tag'],rarity:'common'},slug:null,publication:{title:'Source',authors:'Author',license:'ORC',remaster:true}}});
const row=(rows,path)=>rows.find(r=>r.path==='/system/'+path);
test('treasure source retains category and metadata without valuation or sale assumptions',()=>{
 const input=source(),before=JSON.stringify(input),rows=treasureFields(input);
 for(const [path,value]of [['category','coin'],['traits/value/0','precious'],['traits/value/1','future-trait'],['traits/otherTags/0','future-tag'],['traits/rarity','common'],['slug',null],['publication/title','Source'],['publication/remaster',true]])assert.equal(row(rows,path).value,value);
 assert.equal(JSON.stringify(input),before);assert.ok(rows.every(r=>r.limitations.includes('source_only_no_treasure_valuation_or_sale')));
 assert.equal(treasureFields({type:'equipment'}),null);assert.equal(treasureFields(null),null);
 for(const category of [null,'gem','art-object','material','credstick','future-category']){input.system.category=category;assert.equal(row(treasureFields(input),'category').value,category);}
});
test('missing null and empty treasure fields retain their source distinctions',()=>{
 const input=source();input.system.category=null;input.system.traits.value=[];input.system.traits.otherTags=[];
 assert.equal(row(treasureFields(input),'category').value,null);assert.deepEqual(row(treasureFields(input),'traits/value').value,[]);assert.deepEqual(row(treasureFields(input),'traits/otherTags').value,[]);
 delete input.system.category;delete input.system.traits.value;delete input.system.slug;delete input.system.publication;
 for(const path of ['category','traits/value','slug','publication/title','publication/remaster']){const missing=row(treasureFields(input),path);assert.equal(missing.present,false);assert.equal(Object.hasOwn(missing,'value'),false);}
});
test('malformed selected treasure fields reject without coercion',()=>{
 for(const change of [s=>s.system.category=undefined,s=>s.system.category=5,s=>s.system.category={},s=>s.system.traits.value=undefined,s=>s.system.traits.value=null,s=>s.system.traits.value={},s=>s.system.traits.value=[null],s=>s.system.traits.otherTags=[false],s=>s.system.traits.rarity=3,s=>s.system.slug=undefined,s=>s.system.slug=3,s=>s.system.publication.title=null,s=>s.system.publication.remaster='true']){const input=source();change(input);assert.throws(()=>treasureFields(input),TypeError);}
});
test('shared treasure quantity and price-per stay independent and source paths unique',()=>{
 const input=source();for(const key of ['stackGroup','usage','investment','coinValue','assetValue','salePrice','description','rules','subitems'])Object.defineProperty(input.system,key,{get(){throw new Error(key);}});
 const rows=[...physicalFields(input),...treasureFields(input)],paths=rows.map(r=>r.path);assert.equal(new Set(paths).size,paths.length);
 assert.equal(row(rows,'quantity').value,53);assert.equal(row(rows,'price/per').value,100);assert.equal(row(rows,'price/value/gp').value,1);assert.equal(row(rows,'containerId').value,null);assert.equal(row(rows,'equipped/carryType').value,'worn');
 assert.ok(!treasureFields(input).some(r=>/quantity|price|containerId|equipped|usage|stackGroup|description|rules|subitems/.test(r.path)));
});
