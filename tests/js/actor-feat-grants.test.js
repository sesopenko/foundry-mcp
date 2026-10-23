import test from 'node:test';
import assert from 'node:assert/strict';
import {featGrantFields} from '../../foundry-module/scripts/actorFeatGrants.js';
const rows=pf2e=>new Map(featGrantFields({type:'feat',flags:{pf2e}}).map(row=>[row.path,row]));
test('grant selector retains only declared source fields and escaped opaque keys',()=>{
 const source={type:'feat',flags:{pf2e:{itemGrants:{'opaque/~key':{id:'child',onDelete:'future-policy',nested:false,secret:'omit'}},grantedBy:{id:'parent',onDelete:'detach'},rulesSelections:{secret:'omit'},other:'omit'}}};
 const before=structuredClone(source),result=new Map(featGrantFields(source).map(row=>[row.path,row]));
 assert.equal(result.get('/flags/pf2e/itemGrants/opaque~1~0key/id').value,'child');
 assert.equal(result.get('/flags/pf2e/itemGrants/opaque~1~0key/onDelete').value,'future-policy');
 assert.equal(result.get('/flags/pf2e/itemGrants/opaque~1~0key/nested').value,false);
 assert.equal(result.get('/flags/pf2e/grantedBy/id').value,'parent');
 assert.equal(result.get('/flags/pf2e/grantedBy/onDelete').concept,'feat_granted_by_delete_policy');
 assert.equal(result.size,5);assert.ok(!JSON.stringify([...result.values()]).includes('omit'));assert.deepEqual(source,before);
 for(const row of result.values())assert.deepEqual(row.limitations,['feat_source_not_effective_benefit']);
 for(const source of [null,{}, {type:'action'}, {type:'effect'}])assert.equal(featGrantFields(source),null);
});
test('grant selector distinguishes missing empty null and optional own undefined',()=>{
 const absent=rows({});assert.deepEqual(absent.get('/flags/pf2e/itemGrants'),{path:'/flags/pf2e/itemGrants',present:false,concept:'feat_grant_entries',limitations:['feat_source_not_effective_benefit']});
 assert.equal(absent.get('/flags/pf2e/grantedBy').present,false);
 const empty=rows({itemGrants:{},grantedBy:null});assert.deepEqual(empty.get('/flags/pf2e/itemGrants').value,{});assert.equal(empty.get('/flags/pf2e/grantedBy').value,null);
 const undefinedRows=rows({itemGrants:undefined,grantedBy:undefined});assert.deepEqual(undefinedRows,absent);
 const entries=rows({itemGrants:{empty:{},nullable:{id:'x',nested:null},undefined:{id:'y',nested:undefined,onDelete:undefined}},grantedBy:{onDelete:undefined}});
 for(const path of ['itemGrants/empty/id','itemGrants/empty/onDelete','itemGrants/empty/nested','itemGrants/undefined/nested','itemGrants/undefined/onDelete','grantedBy/id','grantedBy/onDelete']){const row=entries.get('/flags/pf2e/'+path);assert.equal(row.present,false);assert.ok(!Object.hasOwn(row,'value'));}
 assert.equal(entries.get('/flags/pf2e/itemGrants/nullable/nested').value,null);
 const inherited=rows(Object.create({itemGrants:{x:{id:'inherited'}},grantedBy:{id:'inherited'}}));assert.deepEqual(inherited,absent);
});
test('grant selector rejects malformed declared types and bounds the map',()=>{
 for(const pf2e of [{itemGrants:null},{itemGrants:[]},{itemGrants:'bad'},{itemGrants:{x:null}},{itemGrants:{x:[]}},{itemGrants:{x:1}},{itemGrants:{x:{id:undefined}}},{itemGrants:{x:{id:null}}},{itemGrants:{x:{id:1}}},{itemGrants:{x:{onDelete:null}}},{itemGrants:{x:{onDelete:1}}},{itemGrants:{x:{nested:'true'}}},{itemGrants:{x:{nested:0}}},{grantedBy:[]},{grantedBy:false},{grantedBy:{id:null}},{grantedBy:{id:undefined}},{grantedBy:{onDelete:null}}])assert.throws(()=>rows(pf2e),TypeError);
 const map=count=>Object.fromEntries(Array.from({length:count},(_,i)=>[String(i),{}]));
 assert.equal(rows({itemGrants:map(12000)}).size,36001);assert.throws(()=>rows({itemGrants:map(12001)}),/12000/);
});
