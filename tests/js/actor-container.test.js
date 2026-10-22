import test from 'node:test';
import assert from 'node:assert/strict';
import {containerFields} from '../../foundry-module/scripts/actorContainer.js';
import {physicalFields} from '../../foundry-module/scripts/actorPhysical.js';
const source=()=>({type:'backpack',system:{stowing:true,bulk:{value:1,heldOrStowed:0,capacity:4,ignored:2},containerId:'outer',usage:{value:'worncloak'},equipped:{carryType:'worn',invested:false},subitems:[],traits:{value:['invested','magical','future-trait'],otherTags:['future-tag'],rarity:'uncommon'},slug:null,publication:{title:'Source',authors:'Author',license:'ORC',remaster:true}}});
const row=(rows,path)=>rows.find(r=>r.path==='/system/'+path);
test('container source preserves exact Bulk configuration, stowing, traits and metadata without calculating totals',()=>{
 const input=source(),before=JSON.stringify(input),rows=containerFields(input);
 for(const [path,value]of [['traits/value/0','invested'],['traits/value/2','future-trait'],['traits/otherTags/0','future-tag'],['traits/rarity','uncommon'],['slug',null],['publication/title','Source'],['publication/remaster',true]])assert.equal(row(rows,path).value,value);
 for(const [path,value]of [['bulk/heldOrStowed',0],['bulk/capacity',4],['bulk/ignored',2],['stowing',true]])assert.equal(row(rows,path).value,value);
 assert.equal(JSON.stringify(input),before);assert.ok(rows.every(r=>r.limitations.includes('source_only_no_container_bulk_calculation')));
 assert.equal(containerFields({type:'consumable'}),null);assert.equal(containerFields(null),null);
});
test('missing and empty trait arrays remain distinct without fabricated metadata defaults',()=>{
 const input=source();input.system.traits.value=[];input.system.traits.otherTags=[];
 assert.deepEqual(row(containerFields(input),'traits/value').value,[]);assert.deepEqual(row(containerFields(input),'traits/otherTags').value,[]);
 delete input.system.traits.value;delete input.system.slug;delete input.system.publication;
 for(const path of ['traits/value','slug','publication/title','publication/remaster']){const missing=row(containerFields(input),path);assert.equal(missing.present,false);assert.equal(Object.hasOwn(missing,'value'),false);}
});
test('malformed selected container fields reject without coercion',()=>{
 for(const change of [s=>s.system.stowing=undefined,s=>s.system.stowing=1,s=>s.system.bulk.capacity=Infinity,s=>s.system.bulk.ignored='2',s=>s.system.bulk.heldOrStowed=null,s=>s.system.traits.value=undefined,s=>s.system.traits.value=null,s=>s.system.traits.value={},s=>s.system.traits.value=[null],s=>s.system.traits.otherTags=[false],s=>s.system.traits.rarity=3,s=>s.system.slug=undefined,s=>s.system.slug=3,s=>s.system.publication.title=null,s=>s.system.publication.remaster='true']){const input=source();change(input);assert.throws(()=>containerFields(input),TypeError);}
});
test('shared physical usage, uninvested state and parent identity stay unique while derived state stays untouched',()=>{
 const input=source();for(const key of ['flags','description','rules','activation','frequency','apex','abilities','collapsed','contents','totalBulk','computedBulk'])Object.defineProperty(input.system,key,{get(){throw new Error(key);}});
 const rows=[...physicalFields(input),...containerFields(input)],paths=rows.map(r=>r.path);assert.equal(new Set(paths).size,paths.length);
 assert.equal(row(rows,'usage/value').value,'worncloak');assert.equal(row(rows,'equipped/invested').value,false);assert.equal(row(rows,'containerId').value,'outer');assert.equal(row(rows,'bulk/value').value,1);
 assert.ok(!containerFields(input).some(r=>/usage|equipped|subitems|description|rules|activation|frequency|apex|abilities/.test(r.path)));
});

test('finite source parameters remain exact without clamping or capacity subtraction',()=>{
 const input=source();Object.assign(input.system.bulk,{heldOrStowed:-0.1,capacity:0,ignored:99});
 const rows=containerFields(input);assert.equal(row(rows,'bulk/heldOrStowed').value,-0.1);assert.equal(row(rows,'bulk/capacity').value,0);assert.equal(row(rows,'bulk/ignored').value,99);
 input.system.stowing=false;assert.equal(row(containerFields(input),'stowing').value,false);
 delete input.system.bulk;for(const path of ['bulk/heldOrStowed','bulk/capacity','bulk/ignored'])assert.equal(row(containerFields(input),path).present,false);
});
