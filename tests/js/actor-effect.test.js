import test from 'node:test';
import assert from 'node:assert/strict';
import {effectFields} from '../../foundry-module/scripts/actorEffect.js';
const input=()=>({type:'effect',system:{level:{value:0},duration:{value:-1,unit:'unlimited',expiry:null,sustained:false},start:{value:0,initiative:null},tokenIcon:{show:false},unidentified:false,fromSpell:true,slug:null,traits:{value:['magical'],otherTags:[]},badge:{type:'counter',value:0,min:null,max:9,loop:false,labels:['','Second']},context:{origin:{actor:'Actor.origin',token:null,item:'Item.origin',spellcasting:{attribute:{type:'int',mod:4},tradition:null},rollOptions:['action:cast-a-spell']},target:{actor:'Actor.target',token:'Scene.s.Token.t'},roll:{total:22,degreeOfSuccess:2}},publication:{title:'Player Core',authors:'Paizo',license:'ORC',remaster:true},rules:[{key:'SECRET'}],expired:true,description:{value:'SECRET'}}});
const row=(rows,path)=>rows.find(row=>row.path===path);
test('effect source retains zero/null/false and allowlisted context without preparation or mutation',()=>{
 const source=input(),before=JSON.stringify(source),rows=effectFields(source);
 assert.equal(row(rows,'/system/badge/value').value,0);assert.equal(row(rows,'/system/start/initiative').value,null);
 assert.equal(row(rows,'/system/tokenIcon/show').value,false);assert.deepEqual(row(rows,'/system/traits/otherTags').value,[]);
 assert.equal(row(rows,'/system/context/origin/item').value,'Item.origin');assert.equal(row(rows,'/system/context/roll/total').value,22);
 assert.equal(JSON.stringify(source),before);assert.ok(!JSON.stringify(rows).includes('SECRET'));
 assert.ok(!rows.some(row=>/expired|rules|description|flags/.test(row.path)));
 assert.equal(effectFields({type:'condition'}),null);assert.equal(effectFields(null),null);
});
test('badge discriminator controls exact branch and formula strings are never evaluated',()=>{
 const source=input();source.system.badge={type:'formula',value:'@actor.level + 1d4',labels:null,evaluate:true,reevaluate:'turn-start',min:{secret:true}};
 let rows=effectFields(source);assert.equal(row(rows,'/system/badge/value').value,'@actor.level + 1d4');assert.equal(row(rows,'/system/badge/labels').value,null);assert.ok(!row(rows,'/system/badge/min'));
 source.system.badge={type:'value',value:3,labels:[],reevaluate:{event:'initiative-roll',formula:'1d20',initial:0,secret:'SECRET'}};
 rows=effectFields(source);assert.equal(row(rows,'/system/badge/reevaluate/initial').value,0);assert.equal(row(rows,'/system/badge/reevaluate/formula').value,'1d20');assert.ok(!row(rows,'/system/badge/evaluate'));assert.ok(!JSON.stringify(rows).includes('SECRET'));
 source.system.badge.reevaluate=null;assert.equal(row(effectFields(source),'/system/badge/reevaluate').value,null);
});
test('nullable container and absent source remain distinct without emitted objects or defaults',()=>{
 const source=input();source.system.badge=null;source.system.context=null;
 let rows=effectFields(source);assert.equal(row(rows,'/system/badge').value,null);assert.equal(row(rows,'/system/context').value,null);
 delete source.system.badge;delete source.system.context;delete source.system.slug;
 rows=effectFields(source);for(const path of ['/system/badge','/system/context','/system/slug']){assert.equal(row(rows,path).present,false);assert.ok(!Object.hasOwn(row(rows,path),'value'));}
 source.system.context={origin:{actor:'Actor.a',spellcasting:null,rollOptions:[]},target:null,roll:null};
 rows=effectFields(source);assert.equal(row(rows,'/system/context/target').value,null);assert.equal(row(rows,'/system/context/roll').value,null);assert.equal(row(rows,'/system/context/origin/spellcasting').value,null);
 assert.ok(rows.every(row=>!row.present||row.value===null||typeof row.value!=='object'||(Array.isArray(row.value)&&row.value.length===0)));
});
test('all selected malformed values fail without object leakage or silent badge loss',()=>{
 for(const change of [
  source=>source.system.level.value=0.5,source=>source.system.duration.value=-2,source=>source.system.duration.unit='weeks',
  source=>source.system.duration.expiry='tomorrow',source=>source.system.start.value=Infinity,source=>source.system.badge={},
  source=>source.system.badge.type='future',source=>source.system.badge.value={},source=>source.system.badge.labels=[{}],
  source=>source.system.badge.min=1.5,source=>source.system.badge.loop=null,source=>source.system.context=[],
  source=>source.system.context.origin.actor={},source=>source.system.context.origin.rollOptions=null,
  source=>source.system.context.origin.spellcasting.attribute.type='luck',source=>source.system.context.roll.degreeOfSuccess=4,
  source=>source.system.context.target='Actor.a',source=>source.system.traits.value=[null],source=>source.system.publication.remaster=1,
  source=>source.system.badge={type:'value',value:1,reevaluate:{event:'daily',formula:'1'}},
  source=>source.system.badge={type:'formula',value:4,reevaluate:null}
 ]) {const source=input();change(source);assert.throws(()=>effectFields(source),TypeError);}
});
test('unselected objects and source getters are not traversed',()=>{
 const source=input();Object.defineProperty(source.system,'expired',{get(){throw new Error('prepared state accessed');}});
 Object.defineProperty(source.system,'rules',{get(){throw new Error('rules accessed');}});
 source.system.context.origin.extra={secret:'SECRET'};source.system.badge.extra={secret:'SECRET'};
 assert.ok(!JSON.stringify(effectFields(source)).includes('SECRET'));
});

test('schema-optional own undefined is absent while required source fields remain strict',()=>{
 const source=input();source.system.badge.loop=undefined;source.system.badge.labels=undefined;source.system.context=undefined;
 const rows=effectFields(source);
 for(const path of ['/system/badge/loop','/system/badge/labels','/system/context']){assert.equal(row(rows,path).present,false);assert.ok(!Object.hasOwn(row(rows,path),'value'));}
 source.system.duration.sustained=undefined;assert.throws(()=>effectFields(source),TypeError);
});
