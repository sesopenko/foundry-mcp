import test from 'node:test';
import assert from 'node:assert/strict';
import {readActorSelected, readItemSelected, listActorItems, getActorTypes} from '../../foundry-module/scripts/actors.js';
import {searchActors, getActorTree} from '../../foundry-module/scripts/actorWorld.js';
import {listSceneActors} from '../../foundry-module/scripts/actorScenes.js';
import {actorTarget, itemTarget} from '../../foundry-module/scripts/actorDocuments.js';
import {searchCompendiumActors} from '../../foundry-module/scripts/actorPacks.js';
import {lootFixture as fixture} from './helpers/loot-fixture.js';

const read=(args,details=['inventory.summary'],extra={})=>readActorSelected({...args,select:{details,...extra},limit:10,max_bytes:8000});

test('loot world and Scene discovery feeds inventory and instance-correct Item reads',async()=>{
  const f=fixture();
  assert.equal((await searchActors({query:'chest',types:['loot']})).nodes[0].identity.type,'loot');
  assert.equal((await getActorTree()).nodes[0].identity.uuid,f.base.uuid);
  assert.equal((await listSceneActors({scene_uuid:f.scene.uuid,types:['loot']})).nodes.length,3);
  assert.deepEqual((await read({actor_uuid:f.base.uuid},[])).result.entries,[]);
  for(const [i,quantity]of [7,19,0].entries()){
    const token=f.scene.tokens.get('t'+i),selector={token_uuid:token.uuid};
    const page=(await read(selector)).result;
    assert.equal(page.identity.instance.actor_link,i===2);
    const values=page.entries.flatMap(e=>e.values);
    assert.equal(values.find(v=>v.concept==='quantity'&&v.present).value,quantity);
    assert.equal(values.filter(v=>v.concept==='inventory_item').length,2);
    const list=await listActorItems({...selector,select:{context:false,relationships:false,follow_up:true,limitations:false}});
    const next=list.nodes.find(n=>n.identity.type==='treasure').next_call;
    assert.equal(next.arguments.token_uuid,token.uuid);
    const item=(await readItemSelected({...next.arguments,select:{details:['source.physical','description']},limit:10,max_bytes:48000})).result;
    assert.equal(item.identity.actor.uuid,token.actor.uuid);
    assert.equal(item.identity.instance.token_uuid,token.uuid);
    assert.equal(item.entries.flatMap(e=>e.values).find(v=>v.concept==='quantity').value,quantity);
  }
});

test('loot unsupported sections never enter creature extraction or Actor source',async()=>{
  fixture();
  for(const detail of ['source','description','build','statistics','skills','strikes','abilities','spellcasting','state','effective','wealth','bulk']){
    const page=(await read({actor_uuid:'Actor.base'},[detail])).result;
    assert.deepEqual(page.entries,[]);assert.equal(page.sections[0].status,'unsupported');
  }
  const registry=await getActorTypes();
  const loot=registry.actor_types.find(t=>t.type==='loot');
  assert.equal(loot.in_scope,true);assert.match(loot.limitations.join(' '),/inventory/);
});

test('loot permission, kit, excluded Items, missing/current owner and pack boundaries',async()=>{
  const f=fixture();f.add(f.base,'kit','kit');const action=f.add(f.base,'action','action');
  const list=await listActorItems({actor_uuid:f.base.uuid});
  assert.equal(list.unsupported_count,1);assert.equal(list.nodes.length,3);
  await assert.rejects(itemTarget({item_uuid:action.uuid}),/loot|Loot/);
  const pack=f.actor('Compendium.example.loot.Actor.base');pack.compendium={collection:'example.loot',title:'Loot',testUserPermission:()=>true};
  await assert.rejects(actorTarget({actor_uuid:pack.uuid}),/loot|Loot/);
  const packItem=f.add(pack,'coins','treasure');await assert.rejects(itemTarget({item_uuid:packItem.uuid}),/loot|Loot/);
  await assert.rejects(searchCompendiumActors({pack_ids:['example.loot'],query:'chest',types:['loot']}),/types|scope/);
  const hidden=f.base.items.get('coins');hidden.testUserPermission=()=>false;hidden.toObject=()=>{throw Error('denied read');};
  const page=(await read({actor_uuid:f.base.uuid})).result;
  assert.ok(page.sections[0].reasons.includes('inventory_items_denied'));assert.ok(!JSON.stringify(page).includes(hidden.uuid));
  const token=f.scene.tokens.get('t0');token.actor=null;await assert.rejects(read({token_uuid:token.uuid}),/unavailable/);
  game.system.id='other';await assert.rejects(read({actor_uuid:f.base.uuid}),/PF2e/);
});

test('loot semantic pagination binds selections, evidence, stock and permissions',async()=>{
  const f=fixture(),args={actor_uuid:f.base.uuid,select:{details:['inventory.summary']},limit:1,max_bytes:8000};
  const first=(await readActorSelected(args)).result;assert.equal(first.pagination.complete,false);
  const second=(await readActorSelected({...args,cursor:first.pagination.next_cursor})).result;
  assert.equal(second.pagination.complete,true);assert.notEqual(first.entries[0].key,second.entries[0].key);
  await assert.rejects(readActorSelected({...args,select:{details:['inventory']},cursor:first.pagination.next_cursor}),e=>e.rpcError.code==='CursorMismatch');
  f.sources.get('Actor.basecoins').system.quantity=3;
  await assert.rejects(readActorSelected({...args,cursor:first.pagination.next_cursor}),/changed/);
  const evidence=(await read({actor_uuid:f.base.uuid},['inventory.summary'],{evidence:true})).result;
  assert.ok(evidence.entries[0].values.every(v=>v.evidence));
});

test('all physical loot families and separate kit definitions retain source owner',async()=>{
  const f=fixture();
  for(const owner of [f.base,f.scene.tokens.get('t0').actor]){
    const token=owner===f.base?{}:{token_uuid:'Scene.s.Token.t0'};
    for(const type of ['weapon','armor','shield','equipment','consumable','ammo','backpack','book','treasure','kit']){
      const item=f.add(owner,'family-'+type,type,{quantity:0,description:{value:'<p>Stored source.</p>'}});
      const page=(await readItemSelected({item_uuid:item.uuid,...token,select:{details:['source.physical','description']},limit:10,max_bytes:48000})).result;
      assert.equal(page.identity.actor.type,'loot');assert.equal(page.identity.uuid,item.uuid);
      assert.equal(page.identity.actor.uuid,owner.uuid);
    }
  }
});

test('loot containment cycles, orphan claims and empty/denied scopes remain explicit',async()=>{
  const f=fixture();f.base.items.clear();
  let page=(await read({actor_uuid:f.base.uuid})).result;
  assert.equal(page.sections[0].status,'complete');
  assert.equal(page.entries[0].values[0].value.status,'empty');
  f.add(f.base,'one','backpack',{containerId:'two'});f.add(f.base,'two','backpack',{containerId:'one'});
  f.add(f.base,'orphan','equipment',{containerId:'gone'});
  page=(await read({actor_uuid:f.base.uuid})).result;
  assert.equal(page.sections[0].status,'partial');
  assert.ok(page.sections[0].reasons.includes('containment_cycle'));
  assert.ok(page.sections[0].reasons.includes('container_parent_missing'));
  assert.equal(page.entries.flatMap(e=>e.values).filter(v=>v.concept==='inventory_item').length,3);
});
