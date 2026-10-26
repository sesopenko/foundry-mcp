import test from 'node:test';
import assert from 'node:assert/strict';
import {actorStrikeSnapshot} from '../../foundry-module/scripts/actorStrikes.js';

function fixture(type='character') {
 const actor={documentName:'Actor',type,id:'a',uuid:'Actor.a',name:'Actor',items:new Map(),testUserPermission:()=>true};
 const item={documentName:'Item',type:type==='character'?'weapon':'melee',id:'w',uuid:'Actor.a.Item.w',parent:actor,name:'Display',folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>({name:'Stored',type:type==='character'?'weapon':'melee'})};
 actor.items.set(item.id,item);
 const strike={type:'strike',item,slug:'attack',label:'Attack',glyph:'A',description:'',ready:true,canAttack:true,totalModifier:12,breakdown:'Authored',options:[],traits:[],variants:[],altUsages:[],visible:true,handsAvailable:true,domains:[],weaponTraits:[]};
 actor.system={actions:[strike]};
 globalThis.game={user:{isGM:true},version:'14.369',system:{id:'pf2e',version:'8.6.1'}};
 return {actor,item,strike,target:{document:actor,token:null,identity:{uuid:actor.uuid,type:actor.type}}};
}

test('declared current fields preserve zero/false and canonical source origin',()=>{
 const {strike,target}=fixture();strike.totalModifier=0;strike.ready=false;
 const view=actorStrikeSnapshot(target);
 const row=view.records.find(r=>r.raw[0]?.path==='/system/actions/0/totalModifier');
 assert.equal(row.mapped.value,0);assert.equal(row.raw[0].basis,'transformed');
 assert.equal(view.records.find(r=>r.mapped.concept==='current_strike_ready').mapped.value,false);
 const origin=view.records.find(r=>r.mapped.concept==='current_strike_origin');
 assert.deepEqual(origin.mapped.value,{status:'resolved',target_uuid:'Actor.a.Item.w',type:'weapon',name:'Stored',name_truncated:false});
 assert.equal(origin.raw[1].path,'/name');assert.equal(origin.raw[1].basis,'source');
});

test('empty model arrays detach without retaining serialization callbacks',()=>{
 for(const key of ['actions','options']){
  const {actor,strike,target}=fixture();let calls=0;
  const array=[];array.toJSON=()=>{calls++;throw Error('model serialization must not run');};
  if(key==='actions')actor.system.actions=array;else strike.options=array;
  const view=actorStrikeSnapshot(target);
  assert.doesNotThrow(()=>JSON.stringify(view));assert.equal(calls,0);
 }
});

test('PC getter variants are explicit unavailable and compiled class own data is supported',()=>{
 const {actor,strike,target}=fixture();let calls=0;
 class Strike {constructor(){Object.assign(this,strike);this.variants=[{get penalty(){calls++;throw Error('private calculation');},get label(){calls++;throw Error('label calculation');}}];}}
 actor.system.actions=[new Strike()];
 const view=actorStrikeSnapshot(target);
 assert.equal(calls,0);
 const unavailable=view.records.filter(r=>r.key.startsWith('strikes:unavailable:'));
 assert.equal(unavailable.length,2);assert.ok(unavailable.every(r=>r.raw.length===0&&r.mapped.value.reason==='accessor_not_read'));
 assert.ok(view.reasons.includes('current_strike_fields_unavailable'));
});

test('denied canonical and same-ID ephemeral origins reveal no labels or paths',()=>{
 for(const ephemeral of [false,true]){
  const {item,strike,target}=fixture();item.testUserPermission=()=>false;
  if(ephemeral)strike.item={...item,testUserPermission:()=>true};
  Object.defineProperty(strike,'label',{get(){throw Error('Denied label touched');}});
  const view=actorStrikeSnapshot(target);
  assert.equal(view.records.length,1);assert.equal(view.records[0].key,'strikes:current:denied');
  assert.deepEqual(view.records[0].mapped.value,{status:'denied',target_uuid:null});
  assert.equal(view.records[0].raw.length,0);assert.ok(view.reasons.includes('strike_items_denied'));
 }
});

test('generated unarmed has no invented UUID and foreign/accessor origin stays unavailable',()=>{
 const {actor,item,strike,target}=fixture();actor.items.clear();
 assert.equal(actorStrikeSnapshot(target).records.find(r=>r.mapped.concept==='current_strike_origin').mapped.value.status,'generated');
 item.parent={};
 const unavailable=actorStrikeSnapshot(target);
 assert.equal(unavailable.records.length,1);assert.equal(unavailable.records[0].mapped.value.status,'unavailable');
 item.parent=actor;Object.defineProperty(strike,'item',{get(){throw Error('Origin getter');}});
 assert.equal(actorStrikeSnapshot(target).records[0].mapped.value.status,'unavailable');
});

test('alternate nodes, ordered duplicate traits and exact bounded Unicode text',()=>{
 const {strike,target}=fixture();strike.description='界😀'.repeat(1200);
 strike.traits=[{name:'attack',label:'Attack',description:null},{name:'attack',label:'Attack',description:null}];
 strike.altUsages=[{...strike,description:'Alternative',traits:[],altUsages:[]}];
 const view=actorStrikeSnapshot(target);
 const text=view.records.filter(r=>r.kind==='text'&&r.text.path==='/system/actions/0/description');
 assert.ok(text.length>1);assert.equal(text.map(r=>r.raw[0].value).join(''),strike.description);
 assert.equal(text[0].text.start,0);assert.equal(text.at(-1).text.total,strike.description.length);
 assert.ok(view.records.some(r=>r.key==='strikes:current:/system/actions/0/altUsages/0/type'));
 assert.equal(view.records.filter(r=>r.mapped.concept==='current_strike_trait_code').length,2);
});

test('closed bounds reject cycles, holes, malformed values and excessive text/nodes',()=>{
 for(const mutate of [s=>s.altUsages=[s],s=>s.variants=Array(1),s=>s.totalModifier=Infinity,s=>s.options=Array(257).fill('x'),s=>s.description='x'.repeat(300001),s=>s.variants=Array(17).fill({penalty:0,label:'x'})]){
  const {strike,target}=fixture();mutate(strike);
  assert.throws(()=>actorStrikeSnapshot(target),e=>e.rpcError?.code==='ReadFailed');
 }
 const {actor,strike,target}=fixture();actor.system.actions=Array(257).fill(strike);
 assert.throws(()=>actorStrikeSnapshot(target),e=>e.rpcError?.code==='ReadFailed');
});

test('NPC authored source ID, unsupported area modes and unavailable missing fields remain distinct',()=>{
 const {actor,strike,target}=fixture('npc');strike.sourceId='w';strike.attackRollType='PF2E.NPCAttackMelee';delete strike.totalModifier;
 actor.system.actions.push({type:'area-fire',get statistic(){throw Error('Area statistic');}});
 const view=actorStrikeSnapshot(target);
 assert.ok(view.records.some(r=>r.mapped.concept==='current_strike_source_item_local_id'&&r.mapped.value==='w'));
 assert.ok(view.records.some(r=>r.mapped.concept==='current_strike_attack_modifier'&&!r.raw[0].present));
 assert.ok(view.records.some(r=>r.key==='strikes:capability:non_strike_actions'));
 assert.ok(view.reasons.includes('non_strike_actions_unsupported'));
});

test('canonical token origin preserves actual UUID and bounded persisted Unicode name',()=>{
 const {actor,item,target}=fixture();
 actor.uuid='Scene.s.Token.t.Actor.a';item.uuid=actor.uuid+'.Item.w';
 target.token={uuid:'Scene.s.Token.t',parent:{uuid:'Scene.s',name:'Scene'},name:'Token',isLinked:false,baseActor:{uuid:'Actor.a',name:'Base'}};
 item.toObject=()=>({name:'😀'.repeat(257),type:'weapon'});
 const row=actorStrikeSnapshot(target).records.find(r=>r.mapped.concept==='current_strike_origin');
 assert.equal(row.mapped.value.target_uuid,item.uuid);assert.equal(row.mapped.value.token_uuid,target.token.uuid);
 assert.equal([...row.raw[1].value].length,257);assert.equal([...row.mapped.value.name].length,256);assert.equal(row.mapped.value.name_truncated,true);
});

test('persisted origin source accessors reject without invocation',()=>{
 for(const leaf of ['name','type']){
  const {item,target}=fixture();let calls=0;
  item.toObject=()=>{const source={name:'Stored',type:'weapon'};Object.defineProperty(source,leaf,{get(){calls++;throw Error('Source getter forbidden');}});return source;};
  assert.throws(()=>actorStrikeSnapshot(target),e=>e.rpcError?.code==='ReadFailed');
  assert.equal(calls,0);
 }
});

test('own missing, inherited and accessor collection fields remain explicit without evaluation',()=>{
 const {actor,strike,target}=fixture();let getters=0;
 delete strike.totalModifier;Object.setPrototypeOf(strike,{get totalModifier(){getters++;return 99;}});
 const rows=actorStrikeSnapshot(target).records;
 assert.equal(rows.find(r=>r.mapped.concept==='current_strike_attack_modifier').raw[0].present,false);
 Object.defineProperty(actor,'system',{get(){getters++;throw Error('System getter');}});
 const view=actorStrikeSnapshot(target);
 assert.equal(getters,0);assert.equal(view.records.length,1);
 assert.equal(view.records[0].key,'strikes:unavailable:/system/actions');
});

test('depth/owned-Item bounds and source claims cannot bypass Item privacy',()=>{
 const {actor,item,strike,target}=fixture('npc');
 actor.items.set('secret',{testUserPermission:()=>false});strike.sourceId='secret';
 Object.defineProperty(strike,'slug',{get(){throw Error('Private source label');}});
 assert.equal(actorStrikeSnapshot(target).records[0].key,'strikes:current:denied');
 const depth=fixture();let child=depth.strike;
 for(let i=0;i<5;i++){const next={...depth.strike,altUsages:[]};child.altUsages=[next];child=next;}
 assert.throws(()=>actorStrikeSnapshot(depth.target),e=>e.rpcError?.code==='ReadFailed');
 const tooMany=fixture();tooMany.actor.items={size:12001};
 assert.throws(()=>actorStrikeSnapshot(tooMany.target),e=>e.rpcError?.code==='ReadFailed');
});
