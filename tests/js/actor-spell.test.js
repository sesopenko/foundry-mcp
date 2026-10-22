import test from 'node:test';
import assert from 'node:assert/strict';
import {spellFields,spellDescriptionFields} from '../../foundry-module/scripts/actorSpell.js';
const fixture=()=>({type:'spell',system:{level:{value:2},traits:{value:['attack','future'],traditions:['arcane'],otherTags:[],rarity:'common'},time:{value:'1 minute or longer'},requirements:'a voice',cost:{value:'1 gp'},range:{value:'120 feet'},target:{value:'one creature'},area:null,duration:{value:'1 minute',sustained:true},damage:{a:{formula:'2d6',type:'fire',category:null,materials:[],kinds:['damage','healing'],applyMod:false}},defense:{passive:null,save:{statistic:'reflex',basic:true}},counteraction:false,ritual:null,location:{value:null,signature:false,heightenedLevel:5,autoHeightenLevel:null,uses:{value:1,max:3}},slug:null,publication:{title:'PC',authors:'Author',license:'ORC',remaster:true}}});
const at=(rows,path)=>rows.find(row=>row.path==='/system/'+path);
test('spell definitions retain text, damage kinds and configured ranks without casting inference',()=>{
 const s=fixture(),before=JSON.stringify(s),rows=spellFields(s);
 assert.equal(at(rows,'level/value').concept,'spell_base_rank');assert.equal(at(rows,'level/value').value,2);
 assert.equal(at(rows,'time/value').value,'1 minute or longer');assert.equal(at(rows,'location/heightenedLevel').value,5);
 assert.equal(at(rows,'damage/a/kinds/1').value,'healing');assert.equal(at(rows,'area').value,null);
 assert.equal(JSON.stringify(s),before);assert.equal(spellFields({type:'action'}),null);
 assert.ok(rows.every(r=>r.limitations.includes('source_only_no_spell_casting_or_variant_application')));
});
test('interval and recursive fixed/overlay fields preserve source provenance and escaped keys',()=>{
 const s=fixture();s.system.heightening={type:'fixed',levels:{4:{damage:{'a/b~c':{formula:'4d6',type:'fire',category:null,materials:[]}},heightening:{type:'interval',interval:2,area:5,damage:{a:'1d6'}},description:{value:'nested prose'}}}};
 s.system.overlays={'x/y':{overlayType:'override',sort:2,name:'Alternative',system:{level:{value:3},description:{value:'variant prose'},traits:{value:[]}}}};
 const rows=spellFields(s);assert.equal(at(rows,'heightening/levels/4/damage/a~1b~0c/formula').value,'4d6');
 assert.equal(at(rows,'heightening/levels/4/heightening/damage/a').value,'1d6');assert.equal(at(rows,'overlays/x~1y/system/level/value').value,3);
 assert.ok(!rows.some(r=>r.path.includes('description')));assert.ok(!rows.some(r=>r.path==='/system/heightening/levels/4/time'));
 assert.deepEqual(spellDescriptionFields(s).filter(r=>r.present).map(r=>r.value),['nested prose','variant prose']);
});
test('missing, empty, null and optional undefined remain distinct',()=>{
 const s=fixture();s.system.damage={};s.system.overlays={};s.system.heightening={type:'fixed',levels:{}};s.system.area={value:20,type:'burst',details:undefined};s.system.location.signature=undefined;
 const rows=spellFields(s);for(const p of ['damage','overlays','heightening/levels'])assert.deepEqual(at(rows,p).value,{});
 assert.equal(at(rows,'area/details').present,false);assert.equal(at(rows,'location/signature').present,false);
 delete s.system.duration;assert.equal(at(spellFields(s),'duration').present,false);
});
test('malformed selected source rejects without evaluating unknown or prepared fields',()=>{
 for(const change of [s=>s.system.level.value=undefined,s=>s.system.damage.a.formula=3,s=>s.system.area=[],s=>s.system.heightening={type:'unknown'},s=>s.system.heightening={type:'fixed',levels:{11:{}}},s=>s.system.location.signature=null,s=>s.system.overlays={x:null}]){const s=fixture();change(s);assert.throws(()=>spellFields(s),TypeError);}
 const s=fixture();for(const key of ['rules','cast','flags','description'])Object.defineProperty(s.system,key,{get(){throw Error(key);}});assert.ok(spellFields(s).length);
});
test('cyclic nesting and excessive selected fields reject instead of truncating',()=>{
 const s=fixture();const layer={};layer.heightening={type:'fixed',levels:{2:layer}};s.system.heightening=layer.heightening;assert.throws(()=>spellFields(s),/nesting depth/);
 const many=fixture();many.system.damage=Object.fromEntries(Array.from({length:2500},(_,i)=>[String(i),{formula:'1',type:'fire',category:null,materials:[]} ]));assert.throws(()=>spellFields(many),/12000/);
});
test('partial overlay patches preserve incomplete damage and discriminatorless heightening without defaults',()=>{
 const s=fixture();s.system.overlays={variant:{overlayType:'override',sort:0,system:{damage:{0:{category:null,formula:'1d12'}},heightening:{damage:{0:'1d12'}},range:undefined}}};
 const rows=spellFields(s);assert.equal(at(rows,'overlays/variant/system/damage/0/formula').value,'1d12');
 assert.equal(at(rows,'overlays/variant/system/heightening/damage/0').value,'1d12');
 assert.ok(!rows.some(r=>r.path==='/system/overlays/variant/system/damage/0/type'));
 assert.ok(!rows.some(r=>r.path==='/system/overlays/variant/system/heightening/type'));
 s.system.heightening={type:'fixed',levels:{3:{}}};assert.deepEqual(at(spellFields(s),'heightening/levels/3').value,{});
 assert.equal(at(spellDescriptionFields(s),'description/value').present,false);
});
