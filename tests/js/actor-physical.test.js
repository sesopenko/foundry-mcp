import test from 'node:test';
import assert from 'node:assert/strict';
import {physicalFields,PHYSICAL_TYPES} from '../../foundry-module/scripts/actorPhysical.js';
const lookup=(source,path)=>physicalFields(source).find(field=>field.path===`/system/${path}`);
test('physical source preserves zero, false, null, absence and unknown codes',()=>{
 const source={type:'weapon',system:{quantity:0,hp:{value:0,max:0},equipped:{carryType:'custom',handsHeld:0,invested:null},temporary:false}};
 assert.equal(lookup(source,'quantity').value,0);
 assert.equal(lookup(source,'hp/max').value,0);
 assert.equal(lookup(source,'temporary').value,false);
 assert.equal(lookup(source,'equipped/invested').value,null);
 assert.equal(lookup(source,'equipped/carryType').value,'custom');
 assert.equal(lookup(source,'price/per').present,false);
 assert.equal(Object.hasOwn(lookup(source,'price/per'),'value'),false);
});
test('GM unidentified source is retained without substituting original identity',()=>{
 const source={type:'equipment',name:'true name',system:{identification:{status:'unidentified',unidentified:{name:'unknown object',data:{description:{value:'<p>Unknown</p>'}}}}}};
 assert.equal(lookup(source,'identification/status').value,'unidentified');
 assert.equal(lookup(source,'identification/unidentified/name').value,'unknown object');
 assert.equal(lookup(source,'identification/unidentified/data/description/value').value,'<p>Unknown</p>');
 assert.equal(source.name,'true name');
});
test('price.per is exact source and never multiplied by quantity',()=>{
 const source={type:'ammo',system:{quantity:30,price:{value:{gp:2,sp:0},per:10}}};
 assert.equal(lookup(source,'price/value/gp').value,2);
 assert.equal(lookup(source,'price/value/sp').value,0);
 assert.equal(lookup(source,'price/per').value,10);
 assert.equal(lookup(source,'price/value/cp').present,false);
});
test('type omissions exclude derived usage/investment and unsupported attachments',()=>{
 for(const type of ['armor','shield','treasure']) assert.equal(lookup({type,system:{usage:{value:'derived'}}},'usage/value'),undefined);
 assert.equal(lookup({type:'treasure',system:{equipped:{invested:true}}},'equipped/invested'),undefined);
 for(const type of ['ammo','book','consumable','backpack','treasure']) assert.equal(lookup({type,system:{subitems:[{name:'ignored'}]}},'subitems/0/name'),undefined);
 assert.equal(physicalFields({type:'kit',system:{quantity:3}}),null);
 assert.equal(physicalFields({type:'spell'}),null);
 assert.equal(PHYSICAL_TYPES.length,9);
});
test('attachments retain named source paths but never manufacture document identities or recurse',()=>{
 const source={type:'weapon',system:{containerId:'container',subitems:[{_id:'attachment',name:'attached',type:'equipment',flags:{secret:'omit'},system:{subitems:[{name:'nested'}]}}]}};
 const fields=physicalFields(source);
 assert.equal(lookup(source,'containerId').value,'container');
 assert.equal(lookup(source,'subitems/0/name').value,'attached');
 assert.equal(lookup(source,'subitems/0/_id').value,'attachment');
 assert.ok(fields.every(f=>!f.path.includes('flags')&&!f.path.includes('uuid')&&!f.path.includes('/system/subitems/0/system')));
 assert.ok(lookup(source,'subitems/0/name').limitations.includes('serialized_source_not_document'));
 fields[0].limitations.push('changed');
 assert.ok(!physicalFields(source)[0].limitations.includes('changed'));
 assert.deepEqual(lookup({type:'armor',system:{subitems:[]}},'subitems').value,[]);
});
test('reject malformed allowlisted values instead of leaking unselected objects',()=>{
 assert.throws(()=>physicalFields({type:'weapon',system:{quantity:{secret:'no'}}}),TypeError);
 assert.throws(()=>physicalFields({type:'weapon',system:{subitems:{secret:'no'}}}),TypeError);
 assert.throws(()=>physicalFields({type:'equipment',system:{hardness:Infinity}}),TypeError);
});

test('selected leaves reject scalar schema mismatches and malformed attachment elements',()=>{
 for(const system of [{quantity:'3'},{equipped:{handsHeld:false}},{identification:{status:1}},{hp:{max:null}},{temporary:'false'}]) {
  assert.throws(()=>physicalFields({type:'weapon',system}),TypeError);
 }
 for(const attachment of [null,3,[],{name:{hidden:true}}]) assert.throws(()=>physicalFields({type:'weapon',system:{subitems:[attachment]}}),TypeError);
 const source={type:'book',system:{category:'spell',capacity:3,contents:['Item.unselected'],subitems:[{name:'not allowed'}]}};
 assert.ok(physicalFields(source).every(field=>!field.path.includes('/contents')&&!field.path.includes('/capacity')&&!field.path.includes('/category')&&!field.path.includes('/subitems')));
});

test('optional PriceField undefined source initial is absent rather than invalid boolean',()=>{
 const source={type:'treasure',system:{price:{value:{gp:1},sizeSensitive:undefined}}};
 const field=lookup(source,'price/sizeSensitive');
 assert.equal(field.present,false);
 assert.equal(Object.hasOwn(field,'value'),false);
 assert.throws(()=>physicalFields({type:'treasure',system:{price:{sizeSensitive:'false'}}}),TypeError);
 assert.throws(()=>physicalFields({type:'weapon',system:{quantity:undefined}}),TypeError);
});
