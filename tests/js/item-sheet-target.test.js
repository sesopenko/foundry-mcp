import test from 'node:test';
import assert from 'node:assert/strict';
import {world} from './fixtures/item-sheet-world.js';
import {sheetTarget} from '../../foundry-module/scripts/itemSheetTarget.js';

test('ready GM, qualified system, exact standalone membership and update permission', async()=>{
  const {item}=world();
  const read=()=>sheetTarget({item_uuid:item.uuid});
  assert.equal((await read()).reason,null);
  item.canUserModify=()=>false; assert.match((await read()).reason,/permission/);
  game.items.clear();assert.match((await read()).reason,/standalone/);
  item.compendium={testUserPermission:()=>true,title:'Pack',collection:'pack'};
  assert.match((await read()).reason,/Compendium/);
  game.system.id='other';await assert.rejects(read,/PF2e/);
  game.system.id='pf2e';game.user.isGM=false;await assert.rejects(read,/GM/);
});

test('only exact direct members of eligible world Actors can be edited',async()=>{
  const {doc}=world();
  for(const type of ['party','loot','character','npc','familiar']){
    const actor=doc('Actor.'+type,'Actor',{type,items:new Map()});
    game.actors.set(actor.id,actor);
    const item=doc(actor.uuid+'.Item.i','Item',{type:'weapon',parent:actor});
    actor.items.set(item.id,item);
    assert.equal((await sheetTarget({item_uuid:item.uuid})).reason,null);
    actor.items.clear();
    if(type==='party'||type==='loot') await assert.rejects(()=>sheetTarget({item_uuid:item.uuid}));
    else assert.match((await sheetTarget({item_uuid:item.uuid})).reason,/inventory/);
  }
  const nested=doc('Item.blade.Item.fake','Item',{type:'weapon',parent:game.items.get('blade')});
  assert.match((await sheetTarget({item_uuid:nested.uuid})).reason,/standalone/);
});

test('scene inventory is exact, linked alias redirects and generated selectors fail',async()=>{
  const {doc}=world();
  const scene=doc('Scene.s','Scene',{tokens:new Map()});game.scenes.set('s',scene);
  const token=doc('Scene.s.Token.t','Token',{isLinked:false,parent:scene});scene.tokens.set('t',token);
  const actor=doc(token.uuid+'.Actor.a','Actor',{type:'loot',items:new Map()});token.actor=actor;
  const item=doc(actor.uuid+'.Item.i','Item',{type:'weapon',parent:actor});actor.items.set('i',item);
  const args={item_uuid:item.uuid,token_uuid:token.uuid};
  assert.equal((await sheetTarget(args)).reason,null);
  await assert.rejects(()=>sheetTarget({item_uuid:item.uuid}),/token_uuid/);
  await assert.rejects(()=>sheetTarget({...args,item_uuid:'Item.blade'}),/does not belong/);
  token.isLinked=true;assert.match((await sheetTarget(args)).reason,/canonical Actor/);
  await assert.rejects(()=>sheetTarget({item_uuid:'strike:blade'}),/canonical/);
});
