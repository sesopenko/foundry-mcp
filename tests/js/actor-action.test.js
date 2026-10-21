import test from 'node:test';
import assert from 'node:assert/strict';
import {actionFields} from '../../foundry-module/scripts/actorAction.js';

const source=(kind='reaction',count=null)=>({type:'action',name:'Ability',system:{actionType:{value:kind},actions:{value:count},category:'familiar',deathNote:false,slug:null,traits:{value:['auditory','custom-code'],otherTags:['custom-tag']},frequency:{max:2,per:'day'},selfEffect:{uuid:'Compendium.example.effects.Item.effect',name:'Named Effect'},publication:{title:'Book',authors:'Author',license:'ORC',remaster:true},description:{value:'<p>Trigger: a custom event</p>'},rules:[{key:'SECRET'}],_migration:{secret:'excluded'}}});
const selected=(rows,path)=>rows.find(row=>row.path===path);

test('passive, free and reaction activation remain distinct with null action counts',()=>{
  const expected={passive:'passive_ability',free:'free_action',reaction:'reaction',action:'action_or_activity'};
  for(const [kind,mapped]of Object.entries(expected)) {
    const rows=actionFields(source(kind));
    assert.equal(selected(rows,'/system/actionType/value').value,kind);
    assert.equal(selected(rows,'/system/actionType/value').mapped_value,mapped);
    assert.equal(selected(rows,'/system/actions/value').value,null);
  }
  const rows=actionFields(source('action',2));assert.equal(selected(rows,'/system/actions/value').value,2);
  assert.equal(selected(rows,'/system/actionType/value').mapped_value,'action_or_activity');
  const custom=actionFields(source('custom-kind'));assert.equal(selected(custom,'/system/actionType/value').mapped_value,'custom-kind');
  assert.ok(selected(custom,'/system/actionType/value').limitations.includes('unknown_activation_code_preserved'));
});

test('selected action fields retain source provenance without preparation or writes',()=>{
  const input=source();const before=JSON.stringify(input);const rows=actionFields(input);
  assert.equal(selected(rows,'/system/category').value,'familiar');
  assert.deepEqual(selected(rows,'/system/frequency/value'),{path:'/system/frequency/value',present:false,concept:'recorded_frequency_remaining',limitations:['source_only_not_initialized_or_castability']});
  assert.equal(selected(rows,'/system/frequency/max').value,2);
  assert.equal(selected(rows,'/system/selfEffect/uuid').value,input.system.selfEffect.uuid);
  assert.ok(selected(rows,'/system/selfEffect/uuid').limitations.includes('unverified_reference_not_applied_or_hydrated'));
  assert.equal(selected(rows,'/system/deathNote').value,false);
  assert.equal(JSON.stringify(input),before);
  assert.ok(!JSON.stringify(rows).includes('SECRET'));assert.ok(!rows.some(row=>/description|rules|migration/.test(row.path)));
  assert.equal(actionFields({type:'feat'}),null);assert.equal(actionFields(null),null);
});

test('array indexes preserve unknown codes, duplicates and exact empty arrays',()=>{
  const input=source();input.system.traits.value=['custom','custom','😀'];
  let rows=actionFields(input);
  assert.deepEqual(rows.filter(row=>row.path.startsWith('/system/traits/value/')).map(row=>[row.path,row.value]),[['/system/traits/value/0','custom'],['/system/traits/value/1','custom'],['/system/traits/value/2','😀']]);
  input.system.traits.value=[];rows=actionFields(input);assert.deepEqual(selected(rows,'/system/traits/value').value,[]);
  delete input.system.traits.value;rows=actionFields(input);assert.equal(selected(rows,'/system/traits/value').present,false);
});

test('absent and null optional state differ; stored zero never becomes unknown',()=>{
  const input=source();input.system.frequency.value=0;let rows=actionFields(input);
  assert.equal(selected(rows,'/system/frequency/value').value,0);
  input.system.frequency=null;input.system.selfEffect=null;rows=actionFields(input);
  assert.equal(selected(rows,'/system/frequency').value,null);assert.equal(selected(rows,'/system/selfEffect').value,null);
  delete input.system.frequency;delete input.system.selfEffect;rows=actionFields(input);
  assert.equal(selected(rows,'/system/frequency').present,false);assert.equal(selected(rows,'/system/selfEffect').present,false);
  assert.ok(!Object.hasOwn(selected(rows,'/system/frequency'),'value'));
});

test('malformed allowlisted data cannot produce arbitrary object dumps',()=>{
  for(const change of [
    item=>item.system.actions.value={secret:1},item=>item.system.frequency={max:{secret:1},per:'day'},
    item=>item.system.selfEffect={uuid:{secret:1},name:'x'},item=>item.system.traits.value=[{secret:1}],
    item=>item.system.publication.authors={secret:1},item=>item.system.frequency=[],item=>item.system.deathNote=null
  ]) {const input=source();change(input);assert.throws(()=>actionFields(input),TypeError);}
});

test('schema-optional own undefined source values remain absent without prepared defaults',()=>{
 const input=source();input.system.deathNote=undefined;input.system.frequency.value=undefined;
 let rows=actionFields(input);
 assert.equal(selected(rows,'/system/deathNote').present,false);
 assert.equal(selected(rows,'/system/frequency/value').present,false);
 input.system.frequency=undefined;input.system.selfEffect=undefined;rows=actionFields(input);
 assert.equal(selected(rows,'/system/frequency').present,false);
 assert.equal(selected(rows,'/system/selfEffect').present,false);
});
