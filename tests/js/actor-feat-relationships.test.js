import test from 'node:test';
import assert from 'node:assert/strict';
import {readItem} from '../../foundry-module/scripts/actors.js';

function fixture(scope='owned') {
 const docs=new Map(),lookups=[];
 const owner={documentName:'Actor',id:'owner',uuid:scope==='token'?'Scene.s.Token.t.Actor.owner':'Actor.owner',name:'Owner',type:'character',items:new Map(),testUserPermission:()=>true};
 const pack=scope==='pack'?{collection:'test.feats',title:'Feat definitions',testUserPermission:()=>true}:null;
 const owned=['owned','token'].includes(scope);
 const source={name:'Feature',type:'feat',flags:{pf2e:{itemGrants:{'first/~':{id:'benefit',onDelete:'cascade',nested:null},repeat:{id:'benefit'}},grantedBy:{id:'granter'},rulesSelections:{private:'private_selection_sentinel'},private:'private_flag_sentinel'}},system:{category:'classfeature',level:{value:1},actionType:{value:'passive'},actions:{value:null},prerequisites:{value:[]},selfEffect:{uuid:'Item.effect'},subfeatures:{suppressedFeatures:['Item.suppressed','Item.suppressed']},rules:[{key:'GrantItem',uuid:'Item.future',private:'private_rule_sentinel'}]}};
 function make(id,type,parent=owner,uuid=parent?`${parent.uuid}.Item.${id}`:`Item.${id}`){const item={documentName:'Item',id,uuid,name:'Duplicate',type,parent,folder:null,compendium:null,testUserPermission:()=>true,toObject(){throw Error('related target source must not be expanded');}};docs.set(uuid,item);if(parent)parent.items.set(id,item);return item;}
 const selected=make('selected','feat',owned?owner:null,owned?`${owner.uuid}.Item.selected`:pack?'Compendium.test.feats.Item.selected':'Item.selected');selected.compendium=pack;selected.toObject=basis=>{assert.equal(basis,true);return structuredClone(source);};
 const benefit=make('benefit','feat'),granter=make('granter','feat'),effect=make('effect','effect',null),suppressed=make('suppressed','feat',null);
 const scene={documentName:'Scene',uuid:'Scene.s',name:'Scene',testUserPermission:()=>true};
 const token={documentName:'Token',id:'t',uuid:'Scene.s.Token.t',name:'Encounter',parent:scene,actor:owner,baseActor:null,isLinked:false,testUserPermission:()=>true};owner.token=token;docs.set(token.uuid,token);docs.set(owner.uuid,owner);
 globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map(),items:new Map()};
 globalThis.foundry={utils:{fromUuid:async uuid=>{lookups.push(uuid);return docs.get(uuid);}}};
 return {source,selected,owner,benefit,granter,effect,suppressed,docs,lookups,token,make,args:{item_uuid:selected.uuid,...(scope==='token'?{token_uuid:token.uuid}:{})}};
}
async function rows(f,sections=['relationships'],limit=2){const records=[];let cursor;do{const page=await readItem({...f.args,sections,limit,...(cursor?{cursor}:{})});records.push(...page.records);cursor=page.pagination.next_cursor;}while(cursor);return records;}
const at=(records,path)=>records.find(row=>row.raw[0]?.path===path);
const unresolved=row=>assert.deepEqual(Object.keys(row.mapped.value).sort(),['status','target_uuid']);

test('feat immediate references preserve occurrence paths, actual owner and token identities without target expansion',async()=>{
 for(const scope of ['owned','token']){const f=fixture(scope),before=JSON.stringify(f.source),records=await rows(f);
  assert.equal(records.length,6);assert.equal(new Set(records.map(r=>r.key)).size,6);
  assert.equal(at(records,'/flags/pf2e/itemGrants/first~1~0/id').mapped.concept,'feat_grant_reference');
  assert.equal(at(records,'/flags/pf2e/grantedBy/id').mapped.concept,'feat_granted_by_reference');
  assert.equal(at(records,'/system/selfEffect/uuid').mapped.concept,'feat_self_effect_reference');
  assert.equal(at(records,'/system/subfeatures/suppressedFeatures/0').mapped.concept,'feat_suppressed_feature_reference');
  for(const row of records){assert.equal(row.key,`relationships:feat:${row.raw[0].path}`);assert.equal(row.provenance.mapping,'pf2e.feat.reference.v1');assert.deepEqual(row.provenance.limitations,['persisted_reference_not_active_benefit']);assert.equal(row.mapped.value.status,'resolved');assert.equal(row.mapped.value.document_name,'Item');assert.equal(row.mapped.value.name,'Duplicate');assert.equal(row.mapped.value.name_truncated,false);}
  const grants=records.filter(r=>r.mapped.concept==='feat_grant_reference');assert.ok(grants.every(r=>r.mapped.value.target_uuid===f.benefit.uuid));assert.equal(grants.length,2);
  if(scope==='token'){assert.ok(grants.every(r=>r.mapped.value.token_uuid===f.token.uuid));assert.ok(!Object.hasOwn(at(records,'/system/selfEffect/uuid').mapped.value,'token_uuid'));}
  assert.equal(JSON.stringify(f.source),before);assert.ok(!JSON.stringify(records).includes('sentinel'));
 }
});

test('world and pack definitions retain local grant claims as unowned while UUID definitions resolve independently',async()=>{
 for(const scope of ['world','pack']){const f=fixture(scope),records=await rows(f);assert.equal(records.filter(r=>r.mapped.value.status==='unowned').length,3);for(const row of records.filter(r=>r.raw[0].path.startsWith('/flags/'))){assert.equal(row.mapped.value.status,'unowned');unresolved(row);}assert.equal(at(records,'/system/selfEffect/uuid').mapped.value.target_uuid,f.effect.uuid);assert.ok(!f.lookups.includes(f.benefit.uuid));}
});

test('local grant resolution checks exact membership and target permissions without global or base actor fallback',async()=>{
 const f=fixture('token');f.owner.items.delete('benefit');f.granter.testUserPermission=()=>false;
 const base={...f.owner,uuid:'Actor.base',items:new Map([['benefit',f.benefit]])};f.token.baseActor=base;
 let records=await rows(f);assert.equal(at(records,'/flags/pf2e/itemGrants/repeat/id').mapped.value.status,'missing');assert.equal(at(records,'/flags/pf2e/grantedBy/id').mapped.value.status,'denied');
 f.owner.items.set('benefit',f.benefit);f.benefit.parent=base;
 records=await rows(f);assert.equal(at(records,'/flags/pf2e/itemGrants/repeat/id').mapped.value.status,'unsupported');
 for(const row of records.filter(r=>r.mapped.value.status!=='resolved'))unresolved(row);
 assert.ok(!f.lookups.includes(f.benefit.uuid));
});

test('UUID reference type checks and distinct synthetic target context preserve follow-up identity',async()=>{
 const f=fixture('token');f.effect.type='feat';f.suppressed.type='effect';let records=await rows(f);assert.equal(at(records,'/system/selfEffect/uuid').mapped.value.status,'unsupported');assert.equal(at(records,'/system/subfeatures/suppressedFeatures/0').mapped.value.status,'unsupported');
 const otherOwner={...f.owner,id:'other',uuid:'Scene.s.Token.other.Actor.other',items:new Map()};const target=f.make('otherEffect','effect',otherOwner);const otherToken={...f.token,id:'other',uuid:'Scene.s.Token.other',actor:otherOwner};otherOwner.token=otherToken;f.docs.set(otherToken.uuid,otherToken);f.source.system.selfEffect.uuid=target.uuid;
 records=await rows(f);const value=at(records,'/system/selfEffect/uuid').mapped.value;assert.equal(value.status,'resolved');assert.equal(value.target_uuid,target.uuid);assert.equal(value.token_uuid,otherToken.uuid);
 target.toObject=()=>({name:target.name,type:target.type});assert.equal((await readItem({item_uuid:value.target_uuid,token_uuid:value.token_uuid,sections:['identity']})).identity.uuid,target.uuid);
});

test('missing null and empty roots remain distinct without exposing other PF2e flags',async()=>{
 for(const state of ['missing','null','empty']){const f=fixture();if(state==='missing'){delete f.source.flags.pf2e.itemGrants;delete f.source.flags.pf2e.grantedBy;delete f.source.system.selfEffect;delete f.source.system.subfeatures.suppressedFeatures;}else{f.source.flags.pf2e.itemGrants={};f.source.flags.pf2e.grantedBy=null;f.source.system.selfEffect=null;f.source.system.subfeatures.suppressedFeatures=[];}
  const records=await rows(f);assert.equal(records.length,4);assert.ok(records.every(r=>r.raw[0].present===(state!=='missing')));for(const row of records){unresolved(row);assert.equal(row.mapped.value.status,state==='missing'?'missing':row.raw[0].value===null?'unassociated':'empty');}assert.ok(!JSON.stringify(records).includes('sentinel'));
 }
});

test('source-only feat reads never resolve target documents or inspect owner Items',async()=>{
 const f=fixture();f.owner.items={values(){throw Error('owner collection forbidden for source');},get(){throw Error('owner collection forbidden for source');}};const records=await rows(f,['source']);assert.ok(records.every(r=>r.section==='source'));assert.ok(f.lookups.every(uuid=>uuid===f.selected.uuid));assert.ok(!JSON.stringify(records).includes('sentinel'));
});

test('relationship continuations revalidate source, target names, permissions and exact owner identity',async()=>{
 for(const mutate of [f=>f.source.flags.pf2e.itemGrants.repeat.id='granter',f=>f.benefit.name='Renamed',f=>f.benefit.testUserPermission=()=>false,f=>f.benefit.parent={...f.owner,uuid:'Actor.other',items:new Map()}]){const f=fixture();const first=await readItem({...f.args,sections:['relationships'],limit:1});assert.ok(first.pagination.next_cursor);mutate(f);await assert.rejects(readItem({...f.args,sections:['relationships'],limit:1,cursor:first.pagination.next_cursor}),e=>e.rpcError.code==='ContentChanged');}
});

test('200 immediate claim cap applies across all reference kinds and non-PF2e rejects clearly',async()=>{
 const f=fixture();f.source.flags.pf2e.itemGrants=Object.fromEntries(Array.from({length:196},(_,i)=>[String(i),{id:'benefit'}]));assert.equal((await rows(f,['relationships'],100)).length,200);f.source.flags.pf2e.itemGrants=Object.fromEntries(Array.from({length:197},(_,i)=>[String(i),{id:'benefit'}]));await assert.rejects(readItem({...f.args,sections:['relationships']}),e=>e.rpcError.code==='ReadFailed');assert.ok((await readItem({...f.args,sections:['source'],limit:1})).pagination.next_cursor);game.system.id='other';await assert.rejects(readItem({...f.args,sections:['relationships']}),e=>e.rpcError.code==='UnsupportedSystem');
});
