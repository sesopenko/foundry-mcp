import test from 'node:test';
import assert from 'node:assert/strict';
import {familiarCurrentFields} from '../../foundry-module/scripts/actorFamiliarCurrent.js';
function fixture(){return {type:'familiar',system:{attributes:{ac:{value:20,breakdown:'Master AC',details:''},hp:{value:7,max:25,temp:0}},saves:Object.fromEntries(['fortitude','reflex','will'].map(save=>[save,{value:10,totalModifier:11,breakdown:'Master save'}])),perception:{value:8,totalModifier:9,breakdown:'Master Perception',vision:false},movement:{speeds:Object.fromEntries(['land','burrow','climb','fly','swim','travel'].map(mode=>[mode,['land','travel','fly'].includes(mode)?{value:30,base:25,type:mode,source:null}:null]))},skills:{acrobatics:{slug:'acrobatics',label:'Acrobatics',value:5,totalModifier:6,dc:17,breakdown:'Selected skill',lore:false,itemId:null}}}};}
const field=(result,path)=>result.fields.find(field=>field.path===path);
test('familiar selected current primitives retain independent totals and explicit nullable modes',()=>{
 const input=fixture(),before=JSON.stringify(input),result=familiarCurrentFields(input);assert.deepEqual(result.reasons,['other_statistics_pending']);assert.equal(field(result,'/system/attributes/hp/max').value,25);assert.equal(field(result,'/system/saves/will/value').value,10);assert.equal(field(result,'/system/saves/will/totalModifier').value,11);assert.equal(field(result,'/system/perception/vision').value,false);assert.equal(field(result,'/system/movement/speeds/burrow').value,null);assert.equal(field(result,'/system/skills/acrobatics/dc').value,17);assert.ok(result.fields.every(field=>field.limitations[0]==='serialized_familiar_value_not_recalculated'));assert.equal(JSON.stringify(input),before);
});
test('missing current values and optional undefined stay absent without source or master fallback',()=>{
 const input=fixture();delete input.system.attributes.hp.max;input.system.perception.value=undefined;input._source={system:{attributes:{hp:{max:999}}}};Object.defineProperty(input,'master',{get(){throw Error('master prohibited');}});const result=familiarCurrentFields(input);for(const path of ['/system/attributes/hp/max','/system/perception/value']){assert.equal(field(result,path).present,false);assert.equal(Object.hasOwn(field(result,path),'value'),false);}assert.ok(result.reasons.includes('current_fields_unavailable'));
});
test('familiar ordinary skills preserve escaped keys and empty/missing map markers',()=>{
 const input=fixture();input.system.skills={'a/~':input.system.skills.acrobatics};let result=familiarCurrentFields(input);assert.equal(field(result,'/system/skills/a~1~0/label').value,'Acrobatics');input.system.skills={};result=familiarCurrentFields(input);assert.deepEqual(field(result,'/system/skills').value,{});delete input.system.skills;result=familiarCurrentFields(input);assert.equal(field(result,'/system/skills').present,false);
});
test('Lore or any nonempty Item claim hides all skill metadata before getters or labels',()=>{
 for(const metadata of [{lore:true,itemId:null},{lore:false,itemId:'secret'},{itemId:'secret'}]){const input=fixture();input.system.skills={SECRET_KEY:{...metadata}};Object.defineProperty(input.system.skills.SECRET_KEY,'label',{get(){throw Error('private label');}});const result=familiarCurrentFields(input);assert.ok(result.reasons.includes('familiar_item_linked_skills_unsupported'));assert.ok(!JSON.stringify(result).includes('SECRET_KEY'));assert.ok(!result.fields.some(field=>field.path.startsWith('/system/skills/')));}
});
test('nonplain own data is allowed while inherited leaves stay absent and selected getters reject without invocation',()=>{
 const input=fixture();input.system.attributes.hp=Object.assign(Object.create({get hidden(){throw Error('prototype');}}),input.system.attributes.hp);assert.equal(field(familiarCurrentFields(input),'/system/attributes/hp/value').value,7);delete input.system.attributes.hp.max;Object.defineProperty(Object.getPrototypeOf(input.system.attributes.hp),'max',{get(){throw Error('inherited');}});assert.equal(field(familiarCurrentFields(input),'/system/attributes/hp/max').present,false);
 for(const path of [['type'],['system'],['system','attributes','hp','value'],['system','saves'],['system','movement','speeds','land','source'],['system','skills','acrobatics','lore'],['system','skills','acrobatics','value']]){const input=fixture();let node=input,calls=0;for(const key of path.slice(0,-1))node=node[key];Object.defineProperty(node,path.at(-1),{get(){calls++;return 1;}});assert.throws(()=>familiarCurrentFields(input),TypeError);assert.equal(calls,0);}
});
test('malformed scalars, movement modes, skills and key bounds reject; excluded abilities/attacks/resources stay unread',()=>{
 for(const value of [null,true,'2',NaN,Infinity]){const input=fixture();input.system.attributes.hp.max=value;assert.throws(()=>familiarCurrentFields(input),TypeError);}
 const literal=fixture();literal.system.movement.speeds.land.type='fly';assert.throws(()=>familiarCurrentFields(literal),TypeError);
 for(const value of [null,[],1]){const input=fixture();input.system.skills=value;assert.throws(()=>familiarCurrentFields(input),TypeError);}
 for(const key of ['', '🙂'.repeat(257)]){const input=fixture();input.system.skills={[key]:{}};assert.throws(()=>familiarCurrentFields(input),/1–256/);}
 const count=fixture();count.system.skills=Object.fromEntries(Array.from({length:513},(_,index)=>[String(index),{}]));assert.throws(()=>familiarCurrentFields(count),/512/);
 const input=fixture();for(const key of ['abilities','attack','actions','resources','master'])Object.defineProperty(input.system,key,{get(){throw Error('excluded '+key);}});assert.ok(familiarCurrentFields(input).fields.length>0);assert.equal(familiarCurrentFields({type:'character'}),null);
});
