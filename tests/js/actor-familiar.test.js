import test from 'node:test';
import assert from 'node:assert/strict';
import {familiarFields,familiarNoteFields,familiarMasterField} from '../../foundry-module/scripts/actorFamiliar.js';
const fixture=()=>({type:'familiar',system:{master:{id:'character-id',ability:'custom-code'},attributes:{hp:{value:0,temp:0,tempSource:'item-id',max:999},immunities:['secret']},details:{creature:{value:'<p>exact creature notes</p>'},level:{value:999},languages:{value:['secret']}},traits:{value:['secret']},perception:{mod:999},saves:{will:999},skills:{acrobatics:999},resources:{focus:{value:999}},abilities:{str:{mod:999}}}});
const row=(rows,path)=>rows.find(entry=>entry.path===`/system/${path}`);
test('familiar source master selection rejects own accessors without invoking them',()=>{
 for(const select of [familiarMasterField,familiarFields]){
  const source=fixture();let invoked=0;
  Object.defineProperty(source.system.master,'id',{get(){invoked++;return 'character-id';}});
  assert.throws(()=>select(source),TypeError);assert.equal(invoked,0);
 }
});
test('familiar selects only persisted master and HP leaves without derived statistics',()=>{
 const input=fixture(),before=JSON.stringify(input),rows=familiarFields(input);
 assert.deepEqual(rows.map(entry=>entry.path),['/system/master/id','/system/master/ability','/system/attributes/hp/value','/system/attributes/hp/temp','/system/attributes/hp/tempSource']);
 assert.equal(row(rows,'master/ability').value,'custom-code');assert.equal(row(rows,'attributes/hp/value').value,0);assert.equal(row(rows,'attributes/hp/temp').value,0);
 assert.ok(rows.every(entry=>entry.limitations.includes('familiar_source_not_master_derived_statistics')));assert.equal(JSON.stringify(input),before);
 assert.deepEqual(familiarMasterField(input),row(rows,'master/id'));
});
test('nullable master and ability preserve null separately from absent and zero',()=>{
 const input=fixture();input.system.master={id:null,ability:null};input.system.attributes.hp.tempSource=undefined;
 const rows=familiarFields(input);assert.equal(row(rows,'master/id').value,null);assert.equal(row(rows,'master/ability').value,null);assert.equal(row(rows,'attributes/hp/tempSource').present,false);assert.ok(!Object.hasOwn(row(rows,'attributes/hp/tempSource'),'value'));
 delete input.system.master;assert.equal(familiarMasterField(input).present,false);
 delete input.system.attributes.hp.value;assert.equal(row(familiarFields(input),'attributes/hp/value').present,false);
});
test('familiar prose is exact and separately selected including blank text',()=>{
 const input=fixture();assert.equal(familiarNoteFields(input)[0].value,'<p>exact creature notes</p>');
 assert.ok(!familiarFields(input).some(entry=>entry.path.includes('creature')));
 input.system.details.creature.value='';assert.equal(familiarNoteFields(input)[0].value,'');
 delete input.system.details.creature.value;assert.equal(familiarNoteFields(input)[0].present,false);
});
test('declared HP bounds and scalar types reject malformed source without coercion',()=>{
 for(const key of ['value','temp'])for(const value of [-1,1.5,NaN,Infinity,null,'0',false,{}]){const input=fixture();input.system.attributes.hp[key]=value;assert.throws(()=>familiarFields(input),TypeError);}
 for(const value of [null,'',0,{}]){const input=fixture();input.system.attributes.hp.tempSource=value;assert.throws(()=>familiarFields(input),TypeError);}
 for(const key of ['id','ability'])for(const value of [0,false,{},[]]){const input=fixture();input.system.master[key]=value;assert.throws(()=>familiarFields(input),TypeError);}
 for(const value of [null,0,{},[]]){const input=fixture();input.system.details.creature.value=value;assert.throws(()=>familiarNoteFields(input),TypeError);}
});
test('non-familiar inputs and inherited leaves are excluded',()=>{
 for(const source of [null,{}, {type:'character'}, {type:'npc'}])for(const helper of [familiarFields,familiarNoteFields,familiarMasterField])assert.equal(helper(source),null);
 const input=fixture();input.system.master=Object.create({id:'inherited',ability:'str'});assert.equal(familiarMasterField(input).present,false);assert.equal(row(familiarFields(input),'master/ability').present,false);
});
